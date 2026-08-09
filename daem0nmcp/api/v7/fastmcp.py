"""Pinned FastMCP 3.0.0b2 adapter for the manifest-owned v7 surface."""

from __future__ import annotations

import inspect
import json
import logging
from collections.abc import Mapping
from importlib import metadata
from typing import Annotated, Any

from pydantic import BaseModel, Field, TypeAdapter

from ... import __version__
from .errors import ErrorCode
from .registry import ToolSpec, V7Manifest
from .responses import ResponseFactory
from .tasks import (
    TaskExecutionError,
    run_sync_fallback,
    task_admission_only_var,
    validate_sync_timeout_seconds,
)


PINNED_FASTMCP_VERSION = "3.0.0b2"
_REDACTED_LOG_VALUE = "<redacted>"
_FASTMCP_OPERATION_LOGGER = "fastmcp.server.mixins.mcp_operations"


class FastMCPCompatibilityError(RuntimeError):
    """Raised when the installed framework cannot honor the v7 contract."""


def _redact_log_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: (
                _REDACTED_LOG_VALUE
                if isinstance(key, str) and key.casefold() == "preflight_token"
                else _redact_log_value(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return tuple(_redact_log_value(item) for item in value)
    if isinstance(value, list):
        return [_redact_log_value(item) for item in value]
    return value


class _FrameworkArgumentRedactionFilter(logging.Filter):
    """Copy-redact bearer handles from FastMCP's pre-dispatch DEBUG record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.args = _redact_log_value(record.args)
        return True


_FRAMEWORK_ARGUMENT_REDACTION_FILTER = _FrameworkArgumentRedactionFilter()


def _install_framework_log_redaction() -> None:
    logger = logging.getLogger(_FASTMCP_OPERATION_LOGGER)
    if _FRAMEWORK_ARGUMENT_REDACTION_FILTER not in logger.filters:
        logger.addFilter(_FRAMEWORK_ARGUMENT_REDACTION_FILTER)


def ensure_fastmcp_compatibility(version: str) -> None:
    """Require the one framework release covered by protocol conformance."""
    if version != PINNED_FASTMCP_VERSION:
        raise FastMCPCompatibilityError(
            "FastMCP 3.0.0b2 is required by the MCP v7 wire contract"
        )


def _installed_fastmcp() -> tuple[type[Any], str]:
    try:
        from fastmcp import FastMCP

        version = metadata.version("fastmcp")
    except (ImportError, metadata.PackageNotFoundError) as exc:
        raise FastMCPCompatibilityError(
            "FastMCP 3.0.0b2 is not installed"
        ) from exc
    ensure_fastmcp_compatibility(version)
    return FastMCP, version


def _task_config_class() -> type[Any]:
    try:
        from fastmcp.server.tasks import TaskConfig
    except ImportError as exc:
        raise FastMCPCompatibilityError(
            "FastMCP task support is unavailable; install the reviewed tasks extra"
        ) from exc
    return TaskConfig


def _parameter_default(field: Any) -> Any:
    if field.is_required():
        return inspect.Parameter.empty
    if field.default_factory is not None:
        # Pydantic model schemas intentionally omit a concrete ``default`` for
        # factories.  Preserve that contract in the synthetic callable instead
        # of materializing a mutable value during server construction.
        return inspect.Parameter.empty
    return field.get_default(call_default_factory=True)


def _parameter_annotation(field: Any) -> Any:
    metadata_items = tuple(field.metadata)
    if field.default_factory is not None:
        metadata_items = (
            Field(default_factory=field.default_factory),
            *metadata_items,
        )
    if not metadata_items:
        return field.annotation
    return Annotated[field.annotation, *metadata_items]


def _titled_callable_schema(schema: Any, *, title: str) -> Any:
    """Add the model-root title without changing callable validation."""

    if not isinstance(schema, dict):
        raise FastMCPCompatibilityError("callable schema is unavailable")
    result = dict(schema)
    call_schema = result
    if result.get("type") == "definitions":
        nested = result.get("schema")
        if not isinstance(nested, dict):
            raise FastMCPCompatibilityError("callable schema is malformed")
        call_schema = dict(nested)
        result["schema"] = call_schema
    if call_schema.get("type") != "call":
        raise FastMCPCompatibilityError("callable schema is malformed")
    schema_metadata = dict(call_schema.get("metadata") or {})
    updates = dict(schema_metadata.get("pydantic_js_updates") or {})
    updates["title"] = title
    schema_metadata["pydantic_js_updates"] = updates
    call_schema["metadata"] = schema_metadata
    return result


_TASK_FAILURE_MESSAGES = {
    "TASK_REQUIRED": "This operation requires negotiated task support.",
    "TASKS_UNAVAILABLE": "Task execution is unavailable.",
    "DEADLINE_EXCEEDED": "The operation exceeded its synchronous deadline.",
    "CANCELLED": "The operation was cancelled.",
}


def _tool_adapter(
    spec: ToolSpec,
    *,
    tasks_enabled: bool,
    sync_timeout_seconds: float,
):
    async def invoke(**arguments: Any) -> dict[str, Any]:
        request = spec.input_model.model_validate(arguments)

        async def execute() -> Any:
            result = spec.handler(**request.model_dump())
            if inspect.isawaitable(result):
                result = await result
            return result

        try:
            if spec.task_mode == "optional" and not tasks_enabled:
                admission_aware = bool(
                    getattr(
                        spec.handler,
                        "__daem0nmcp_admission_aware__",
                        False,
                    )
                )
                reviewed_fallback = (
                    getattr(
                        spec.handler,
                        "__daem0nmcp_sync_fallback_safe__",
                        False,
                    )
                    is True
                )
                if reviewed_fallback:
                    result = await run_sync_fallback(
                        execute,
                        estimated_to_fit=True,
                        timeout_seconds=sync_timeout_seconds,
                    )
                elif admission_aware:
                    admission = task_admission_only_var.set(True)
                    try:
                        result = await execute()
                    finally:
                        task_admission_only_var.reset(admission)
                else:
                    result = await run_sync_fallback(
                        execute,
                        estimated_to_fit=False,
                        timeout_seconds=sync_timeout_seconds,
                    )
            else:
                result = await execute()
        except TaskExecutionError as exc:
            workspace_id = getattr(request, "workspace_id", None)
            error_code = (
                "TASKS_UNAVAILABLE"
                if exc.code == "TASK_REQUIRED" and not tasks_enabled
                else exc.code
            )
            result = ResponseFactory().begin(workspace_id).failure(
                ErrorCode(error_code),
                _TASK_FAILURE_MESSAGES[error_code],
            )
        response = spec.output_model.model_validate(result)
        return response.model_dump(mode="json")

    invoke.__name__ = f"v7_{spec.name}"
    invoke.__qualname__ = invoke.__name__
    invoke.__doc__ = spec.description
    parameters = []
    for name, field in spec.input_model.model_fields.items():
        parameters.append(
            inspect.Parameter(
                name,
                inspect.Parameter.KEYWORD_ONLY,
                default=_parameter_default(field),
                annotation=_parameter_annotation(field),
            )
        )
    signature = inspect.Signature(
        parameters=parameters,
        return_annotation=spec.output_model,
    )
    invoke.__signature__ = signature  # type: ignore[attr-defined]
    # Pydantic's callable schema parser combines ``inspect.signature`` with
    # ``get_type_hints``.  Once we replace the wrapper's **arguments signature,
    # its annotations must describe those same public parameters or FastMCP's
    # FunctionTool construction fails before the server can start.
    invoke.__annotations__ = {
        name: parameter.annotation
        for name, parameter in signature.parameters.items()
    }
    invoke.__annotations__["return"] = signature.return_annotation
    callable_schema = _titled_callable_schema(
        TypeAdapter(invoke).core_schema,
        title=spec.input_schema["title"],
    )

    def manifest_callable_schema(_source: Any, _handler: Any) -> Any:
        return callable_schema

    # FastMCP 3.0.0b2 asks Pydantic for the callable schema at registration.
    # Keep its validation as a real call schema while making the advertised
    # root metadata byte-for-byte equal to the manifest-owned input model.
    invoke.__get_pydantic_core_schema__ = manifest_callable_schema  # type: ignore[attr-defined]
    return invoke


def _resource_adapter(spec: Any):
    async def read(workspace_id: str) -> str:
        result = spec.handler(workspace_id=workspace_id)
        if inspect.isawaitable(result):
            result = await result
        response = spec.output_model.model_validate(result)
        return json.dumps(
            response.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    read.__name__ = f"v7_resource_{spec.name}"
    read.__qualname__ = read.__name__
    read.__doc__ = spec.description
    return read


def build_fastmcp_server(
    manifest: V7Manifest,
    *,
    fastmcp_cls: type[Any] | None = None,
    distribution_version: str | None = None,
    task_config_cls: type[Any] | None = None,
    tasks_enabled: bool = False,
    auth: Any | None = None,
    middleware: tuple[Any, ...] = (),
    lifespan: Any | None = None,
    sync_timeout_seconds: int | float = 15,
) -> Any:
    """Create a fresh, fail-closed FastMCP instance from one manifest."""
    if fastmcp_cls is None:
        fastmcp_cls, installed_version = _installed_fastmcp()
        version = distribution_version or installed_version
    else:
        if distribution_version is None:
            raise FastMCPCompatibilityError(
                "an injected FastMCP class requires an explicit version"
            )
        version = distribution_version
    ensure_fastmcp_compatibility(version)
    validated_sync_timeout = validate_sync_timeout_seconds(
        sync_timeout_seconds
    )
    _install_framework_log_redaction()

    if tasks_enabled:
        raise FastMCPCompatibilityError(
            "FastMCP 3.0.0b2 has no reviewed task acceptance seam"
        )

    server = fastmcp_cls(
        "Daem0nMCP",
        version=__version__,
        strict_input_validation=True,
        mask_error_details=True,
        # Task eligibility is component-owned.  A server-wide True default
        # would silently make every forbidden tool and resource task-capable.
        tasks=False,
        on_duplicate="error",
        auth=auth,
        lifespan=lifespan,
    )
    for item in middleware:
        server.add_middleware(item)

    for spec in manifest.tools:
        registration: dict[str, Any] = {
            "name": spec.name,
            "description": spec.description,
            "tags": set(spec.tags),
            "annotations": dict(spec.annotations),
            "meta": dict(spec.meta),
            "version": spec.version,
            "output_schema": spec.output_schema,
        }
        if spec.task_mode == "optional" and tasks_enabled:
            assert task_config_cls is not None
            registration["task"] = task_config_cls(mode="optional")
        else:
            registration["task"] = False
        server.tool(**registration)(
            _tool_adapter(
                spec,
                tasks_enabled=tasks_enabled,
                sync_timeout_seconds=validated_sync_timeout,
            )
        )

    for spec in manifest.resources:
        server.resource(
            spec.uri_template,
            name=spec.name,
            description=spec.description,
            mime_type=spec.mime_type,
            version=spec.version,
            meta={"daem0nmcp/apiVersion": "7"},
            task=False,
        )(_resource_adapter(spec))

    return server


__all__ = [
    "FastMCPCompatibilityError",
    "PINNED_FASTMCP_VERSION",
    "build_fastmcp_server",
    "ensure_fastmcp_compatibility",
]
