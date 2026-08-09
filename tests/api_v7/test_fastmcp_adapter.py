from __future__ import annotations

import asyncio
import io
import logging
import pathlib
import unittest
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from daem0nmcp import __version__
from daem0nmcp.covenant import CovenantLevel


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    workspace_id: str
    limit: Annotated[int, Field(ge=1, le=9)] = 5


class _Output(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    value: str


async def _handler(workspace_id: str, limit: int = 5) -> _Output:
    return _Output(value=f"{workspace_id}:{limit}")


async def _resource_handler(workspace_id: str) -> _Output:
    return _Output(value=workspace_id)


class _FakeFastMCP:
    def __init__(self, name: str, **kwargs):
        self.name = name
        self.kwargs = kwargs
        self.tools = []
        self.resources = []
        self.middleware = []

    def tool(self, **metadata):
        def register(handler):
            self.tools.append((metadata, handler))
            return handler

        return register

    def resource(self, uri_template: str, **metadata):
        def register(handler):
            self.resources.append((uri_template, metadata, handler))
            return handler

        return register

    def add_middleware(self, middleware):
        self.middleware.append(middleware)


class _ExplodingFastMCP(_FakeFastMCP):
    def tool(self, **metadata):
        del metadata
        raise RuntimeError("registration failed")


@dataclass(frozen=True)
class _FakeTaskConfig:
    mode: str


class FastMCPAdapterTests(unittest.TestCase):
    def _manifest(
        self,
        *,
        task_mode: str = "forbidden",
        with_resource=True,
        read_only: bool = True,
        enveloped: bool = False,
    ):
        from daem0nmcp.api.v7.registry import (
            ResourceSpec,
            ToolSpec,
            V7Manifest,
        )

        output_model = _Output
        if enveloped:
            from daem0nmcp.api.v7.models import ApiResponse

            output_model = ApiResponse[_Output]
        tool = ToolSpec(
            name="session_brief",
            description="Return a bounded session response.",
            handler=_handler,
            input_model=_Input,
            output_model=output_model,
            category="session",
            tags=("session",),
            covenant=CovenantLevel.EXEMPT,
            task_mode=task_mode,
            annotations={
                "readOnlyHint": read_only,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
            pinned=True,
        )
        resources = (
            (
                ResourceSpec(
                    uri_template="memory://workspaces/{workspace_id}/warnings",
                    name="workspace_warnings",
                    description="Newest active warnings.",
                    handler=_resource_handler,
                    output_model=_Output,
                ),
            )
            if with_resource
            else ()
        )
        return V7Manifest(
            tools=(tool,),
            resources=resources,
            policy={"session_brief": CovenantLevel.EXEMPT},
            require_full_surface=False,
        )

    def test_exact_pinned_version_gate(self) -> None:
        from daem0nmcp.api.v7.fastmcp import (
            FastMCPCompatibilityError,
            ensure_fastmcp_compatibility,
        )

        ensure_fastmcp_compatibility("3.0.0b2")
        for version in ("3.0.0b1", "3.0.0", "3.0.1", "2.13.0"):
            with self.subTest(version=version):
                with self.assertRaises(FastMCPCompatibilityError):
                    ensure_fastmcp_compatibility(version)

    def test_project_declares_exact_framework_and_optional_tasks_extra(self) -> None:
        import tomllib

        project = tomllib.loads(pathlib.Path("pyproject.toml").read_text("utf-8"))[
            "project"
        ]
        self.assertIn("fastmcp==3.0.0b2", project["dependencies"])
        self.assertEqual(
            project["optional-dependencies"]["tasks"],
            ["fastmcp[tasks]==3.0.0b2"],
        )

    def test_builds_fresh_strict_stateful_server_from_manifest(self) -> None:
        from daem0nmcp.api.v7.fastmcp import build_fastmcp_server

        server = build_fastmcp_server(
            self._manifest(),
            fastmcp_cls=_FakeFastMCP,
            distribution_version="3.0.0b2",
            tasks_enabled=False,
            auth="auth-provider",
        )

        self.assertEqual(server.name, "Daem0nMCP")
        self.assertEqual(server.kwargs["version"], __version__)
        self.assertTrue(server.kwargs["strict_input_validation"])
        self.assertTrue(server.kwargs["mask_error_details"])
        self.assertNotIn("stateless_http", server.kwargs)
        self.assertFalse(server.kwargs["tasks"])
        self.assertEqual(server.kwargs["on_duplicate"], "error")
        self.assertEqual(server.kwargs["auth"], "auth-provider")
        self.assertEqual(len(server.tools), 1)
        metadata, handler = server.tools[0]
        self.assertEqual(metadata["name"], "session_brief")
        self.assertEqual(metadata["version"], __version__)
        self.assertEqual(metadata["output_schema"]["type"], "object")
        self.assertEqual(metadata["meta"]["daem0nmcp/apiVersion"], "7")
        self.assertIs(metadata["task"], False)
        wire_limit = handler.__signature__.parameters["limit"].annotation
        self.assertEqual(
            {"minimum": 1, "maximum": 9},
            {
                key: TypeAdapter(wire_limit).json_schema()[key]
                for key in ("minimum", "maximum")
            },
        )
        result = asyncio.run(handler(workspace_id="ws_test", limit=3))
        self.assertEqual(result, {"value": "ws_test:3"})
        self.assertEqual(len(server.resources), 1)
        self.assertIs(server.resources[0][1]["task"], False)

    def test_synthetic_callable_annotations_match_the_wire_signature(self) -> None:
        from daem0nmcp.api.v7.fastmcp import build_fastmcp_server

        server = build_fastmcp_server(
            self._manifest(with_resource=False),
            fastmcp_cls=_FakeFastMCP,
            distribution_version="3.0.0b2",
            tasks_enabled=False,
        )
        _, handler = server.tools[0]

        signature = handler.__signature__
        self.assertEqual(
            handler.__annotations__,
            {
                name: parameter.annotation
                for name, parameter in signature.parameters.items()
            }
            | {"return": signature.return_annotation},
        )
        schema = TypeAdapter(handler).json_schema()
        self.assertEqual(schema["type"], "object")
        self.assertEqual(schema["properties"]["limit"]["minimum"], 1)
        self.assertEqual(schema["properties"]["limit"]["maximum"], 9)

    def test_all_callable_input_schemas_equal_the_manifest_authority(self) -> None:
        from daem0nmcp.api.v7.fastmcp import _tool_adapter
        from daem0nmcp.api.v7.policy import V7_TOOL_LEVELS
        from daem0nmcp.api.v7.tools import build_tool_specs

        async def handler(**arguments):
            return arguments

        specs = build_tool_specs(
            {name: handler for name in V7_TOOL_LEVELS}
        )
        for spec in specs:
            with self.subTest(tool=spec.name):
                adapter = _tool_adapter(
                    spec,
                    tasks_enabled=False,
                    sync_timeout_seconds=15,
                )
                self.assertEqual(
                    TypeAdapter(adapter).json_schema(),
                    spec.input_schema,
                )

    def test_framework_debug_logging_redacts_preflight_handles(self) -> None:
        from daem0nmcp.api.v7.fastmcp import build_fastmcp_server

        build_fastmcp_server(
            self._manifest(with_resource=False),
            fastmcp_cls=_FakeFastMCP,
            distribution_version="3.0.0b2",
            tasks_enabled=False,
        )
        logger = logging.getLogger("fastmcp.server.mixins.mcp_operations")
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        previous_level = logger.level
        previous_propagate = logger.propagate
        token = "cap_this_is_a_live_bearer_handle"
        arguments = {
            "workspace_id": "ws_test",
            "nested": {"preflight_token": token},
        }
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        try:
            logger.debug(
                "[Daem0nMCP] Handler called: call_tool %s with %s",
                "memory_store",
                arguments,
            )
        finally:
            logger.removeHandler(handler)
            logger.setLevel(previous_level)
            logger.propagate = previous_propagate

        rendered = stream.getvalue()
        self.assertNotIn(token, rendered)
        self.assertIn("<redacted>", rendered)
        self.assertEqual(arguments["nested"]["preflight_token"], token)

    def test_passes_the_owned_lifespan_to_the_framework(self) -> None:
        from daem0nmcp.api.v7.fastmcp import build_fastmcp_server

        entered: list[str] = []

        @asynccontextmanager
        async def lifespan(_server):
            entered.append("start")
            try:
                yield {"ready": True}
            finally:
                entered.append("stop")

        server = build_fastmcp_server(
            self._manifest(with_resource=False),
            fastmcp_cls=_FakeFastMCP,
            distribution_version="3.0.0b2",
            tasks_enabled=False,
            lifespan=lifespan,
        )

        self.assertIs(server.kwargs["lifespan"], lifespan)

        async def exercise() -> None:
            async with server.kwargs["lifespan"](server) as state:
                self.assertEqual(state, {"ready": True})

        asyncio.run(exercise())
        self.assertEqual(entered, ["start", "stop"])

    def test_task_enabled_profile_fails_closed_before_registration(self) -> None:
        from daem0nmcp.api.v7.fastmcp import (
            FastMCPCompatibilityError,
            build_fastmcp_server,
        )

        with self.assertRaisesRegex(
            FastMCPCompatibilityError,
            "acceptance seam",
        ):
            build_fastmcp_server(
                self._manifest(task_mode="optional", with_resource=False),
                fastmcp_cls=_FakeFastMCP,
                distribution_version="3.0.0b2",
                task_config_cls=_FakeTaskConfig,
                tasks_enabled=True,
            )

    def test_optional_tool_uses_bounded_fallback_without_task_support(self) -> None:
        from daem0nmcp.api.v7.fastmcp import build_fastmcp_server

        calls: list[tuple[bool, int | float]] = []

        async def fallback(operation, *, estimated_to_fit, timeout_seconds):
            calls.append((estimated_to_fit, timeout_seconds))
            return await operation()

        _handler.__daem0nmcp_sync_fallback_safe__ = True
        try:
            with patch(
                "daem0nmcp.api.v7.fastmcp.run_sync_fallback",
                side_effect=fallback,
            ):
                server = build_fastmcp_server(
                    self._manifest(task_mode="optional", with_resource=False),
                    fastmcp_cls=_FakeFastMCP,
                    distribution_version="3.0.0b2",
                    tasks_enabled=False,
                    sync_timeout_seconds=7,
                )
                metadata, handler = server.tools[0]
                result = asyncio.run(handler(workspace_id="ws_test", limit=2))
        finally:
            del _handler.__daem0nmcp_sync_fallback_safe__

        self.assertEqual(result, {"value": "ws_test:2"})
        self.assertEqual(calls, [(True, 7)])
        self.assertNotIn("timeout", metadata)

        calls.clear()
        with patch(
            "daem0nmcp.api.v7.fastmcp.run_sync_fallback",
            side_effect=fallback,
        ):
            server = build_fastmcp_server(
                self._manifest(
                    task_mode="optional",
                    with_resource=False,
                    read_only=False,
                ),
                fastmcp_cls=_FakeFastMCP,
                distribution_version="3.0.0b2",
                tasks_enabled=False,
                sync_timeout_seconds=7,
            )
            _, handler = server.tools[0]
            asyncio.run(handler(workspace_id="ws_test", limit=2))
        self.assertEqual(calls, [(False, 7)])

        for timeout in (0, 61, True, 10**400):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    build_fastmcp_server(
                        self._manifest(task_mode="optional", with_resource=False),
                        fastmcp_cls=_FakeFastMCP,
                        distribution_version="3.0.0b2",
                        tasks_enabled=False,
                        sync_timeout_seconds=timeout,
                    )

    def test_read_only_hint_cannot_admit_an_unreviewed_sync_fallback(self) -> None:
        from daem0nmcp.api.v7.errors import ErrorCode
        from daem0nmcp.api.v7.fastmcp import build_fastmcp_server
        from daem0nmcp.api.v7.models import ApiResponse

        server = build_fastmcp_server(
            self._manifest(
                task_mode="optional",
                with_resource=False,
                read_only=True,
                enveloped=True,
            ),
            fastmcp_cls=_FakeFastMCP,
            distribution_version="3.0.0b2",
            tasks_enabled=False,
        )
        metadata, handler = server.tools[0]
        result = asyncio.run(
            handler(workspace_id="ws_" + "a" * 24, limit=2)
        )

        response = ApiResponse[_Output].model_validate(result)
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code, ErrorCode.TASKS_UNAVAILABLE)
        self.assertNotIn("timeout", metadata)

    def test_optional_write_reports_tasks_unavailable_without_backend(self) -> None:
        from daem0nmcp.api.v7.errors import ErrorCode
        from daem0nmcp.api.v7.fastmcp import build_fastmcp_server
        from daem0nmcp.api.v7.models import ApiResponse

        server = build_fastmcp_server(
            self._manifest(
                task_mode="optional",
                with_resource=False,
                read_only=False,
                enveloped=True,
            ),
            fastmcp_cls=_FakeFastMCP,
            distribution_version="3.0.0b2",
            tasks_enabled=False,
        )
        _, handler = server.tools[0]

        result = asyncio.run(
            handler(workspace_id="ws_" + "a" * 24, limit=2)
        )

        response = ApiResponse[_Output].model_validate(result)
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code, ErrorCode.TASKS_UNAVAILABLE)

    def test_registration_failure_is_not_suppressed(self) -> None:
        from daem0nmcp.api.v7.fastmcp import build_fastmcp_server

        with self.assertRaisesRegex(RuntimeError, "registration failed"):
            build_fastmcp_server(
                self._manifest(with_resource=False),
                fastmcp_cls=_ExplodingFastMCP,
                distribution_version="3.0.0b2",
                tasks_enabled=False,
            )


if __name__ == "__main__":
    unittest.main()
