"""Transport-derived invocation context for the v7 MCP boundary.

This middleware establishes identity and workspace scope only.  Tool policy
admission remains in the typed v7 handlers, so this layer cannot accidentally
authorize a legacy operation or duplicate one-use capability consumption.
"""

from __future__ import annotations

import inspect
import secrets
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Literal, Protocol, TypeVar, cast
from urllib.parse import urlsplit

from pydantic import TypeAdapter

from ...covenant import (
    CovenantGate,
    InvocationScope,
    admitted_call_var,
    covenant_gate_var,
    invocation_scope_var,
    workspace_resolver_var,
)
from ...workspace import Workspace
from .models import WorkspaceId


try:  # The base/model-free install must remain importable without FastMCP.
    from fastmcp.exceptions import ResourceError as _ResourceErrorBase
    from fastmcp.exceptions import ToolError as _ToolErrorBase
    from fastmcp.server.middleware import Middleware as _MiddlewareBase

    FASTMCP_MIDDLEWARE_AVAILABLE = True
except ImportError:
    FASTMCP_MIDDLEWARE_AVAILABLE = False

    class _MiddlewareBase:
        pass

    class _ToolErrorBase(RuntimeError):
        pass

    class _ResourceErrorBase(RuntimeError):
        pass


TransportMode = Literal["stdio", "streamable-http"]
RESOURCE_SUFFIXES = frozenset(
    {"warnings", "failures", "rules", "active-context"}
)
WORKSPACE_OPTIONAL_TOOLS = frozenset({"system_health"})

_WORKSPACE_ID_ADAPTER = TypeAdapter(WorkspaceId)
_ADMISSION_FAILURE = object()
_PROCESS_PRINCIPAL = f"process:{secrets.token_urlsafe(24)}"


class ToolInvocationContextError(_ToolErrorBase):
    """Sanitized failure to establish a tool invocation scope."""

    def __init__(self) -> None:
        super().__init__("Invocation unavailable")


class ResourceInvocationContextError(_ResourceErrorBase):
    """Sanitized failure to establish a resource invocation scope."""

    def __init__(self) -> None:
        super().__init__("Resource unavailable")


class ResourceAuthorizationError(_ResourceErrorBase):
    """Sanitized Communion or exact-scope resource authorization failure."""

    def __init__(self) -> None:
        super().__init__("Resource unavailable")


class WorkspaceResolver(Protocol):
    def resolve(self, workspace_id: str) -> Workspace | Awaitable[Workspace]: ...


R = TypeVar("R")


def _capture(operation: Callable[[], R]) -> R | object:
    """Discard private exception objects before returning a failure sentinel."""

    try:
        return operation()
    except Exception:
        return _ADMISSION_FAILURE


async def _capture_async(operation: Callable[[], Awaitable[R]]) -> R | object:
    """Async capture that deliberately leaves cancellation untouched."""

    try:
        return await operation()
    except Exception:
        return _ADMISSION_FAILURE


async def _resolve_awaitable(value: object) -> object:
    if inspect.isawaitable(value):
        return await value
    return value


def _resource_workspace_id(uri: object) -> WorkspaceId:
    if not isinstance(uri, str):
        uri = str(uri)
    parsed = urlsplit(uri)
    segments = parsed.path.split("/")
    if (
        parsed.scheme != "memory"
        or parsed.netloc != "workspaces"
        or parsed.query
        or parsed.fragment
        or len(segments) != 3
        or segments[0] != ""
        or segments[2] not in RESOURCE_SUFFIXES
    ):
        raise ValueError("resource URI is not a v7 workspace resource")
    return _WORKSPACE_ID_ADAPTER.validate_python(segments[1], strict=True)


class V7InvocationMiddleware(_MiddlewareBase):
    """Install a transport-authenticated scope around v7 tools and resources."""

    def __init__(
        self,
        *,
        gate: CovenantGate,
        workspace_resolver: WorkspaceResolver,
        transport_mode: TransportMode,
        access_token_provider: Callable[[], object] | None = None,
        process_principal: str | None = None,
        session_id_factory: Callable[[], str] | None = None,
        allow_unauthenticated_loopback: bool = False,
    ) -> None:
        if FASTMCP_MIDDLEWARE_AVAILABLE:
            super().__init__()
        if transport_mode not in {"stdio", "streamable-http"}:
            raise ValueError("v7 middleware supports stdio or streamable-http")
        if gate is None:
            raise ValueError("a v7 Covenant gate is required")
        resolver = getattr(workspace_resolver, "resolve", None)
        if not callable(resolver):
            raise ValueError("an explicit workspace resolver is required")
        principal = process_principal or _PROCESS_PRINCIPAL
        if not isinstance(principal, str) or not principal.strip():
            raise ValueError("the process principal must be non-empty")
        if access_token_provider is not None and not callable(access_token_provider):
            raise ValueError("the access-token provider must be callable")
        if not isinstance(allow_unauthenticated_loopback, bool):
            raise ValueError("loopback identity policy must be boolean")
        if allow_unauthenticated_loopback and transport_mode != "streamable-http":
            raise ValueError("loopback identity applies only to Streamable HTTP")

        self._gate = gate
        self._workspace_resolver = workspace_resolver
        self._resolver = resolver
        self._transport_mode = transport_mode
        self._access_token_provider = access_token_provider
        self._process_principal = principal.strip()
        self._allow_unauthenticated_loopback = allow_unauthenticated_loopback
        self._session_id_factory = session_id_factory or (
            lambda: secrets.token_urlsafe(24)
        )
        self._stdio_session_id: str | None = None

    @property
    def stdio_session_id(self) -> str | None:
        return self._stdio_session_id

    async def on_initialize(self, context: Any, call_next: Callable[[Any], Any]) -> Any:
        """Issue a server-owned stdio session only after initialization succeeds."""

        result = call_next(context)
        result = await _resolve_awaitable(result)
        if self._transport_mode == "stdio":
            session_id = self._session_id_factory()
            if not isinstance(session_id, str) or not session_id.strip():
                raise ToolInvocationContextError()
            self._stdio_session_id = session_id.strip()
        return result

    def _default_access_token(self) -> object:
        from fastmcp.server.dependencies import get_access_token

        return get_access_token()

    async def _resolve_workspace(self, workspace_id: WorkspaceId) -> Workspace:
        resolved = self._resolver(workspace_id)
        resolved = await _resolve_awaitable(resolved)
        if not isinstance(resolved, Workspace) or resolved.workspace_id != workspace_id:
            raise ValueError("workspace resolution did not preserve the opaque ID")
        return resolved

    async def _remote_identity(self, context: Any) -> tuple[str, str]:
        fastmcp_context = context.fastmcp_context
        if fastmcp_context.request_context is None:
            raise ValueError("MCP request context is unavailable")
        session_id = fastmcp_context.session_id
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("MCP session is unavailable")

        provider = self._access_token_provider or self._default_access_token
        access_token = provider()
        access_token = await _resolve_awaitable(access_token)
        if access_token is None and self._allow_unauthenticated_loopback:
            return self._process_principal, f"mcp-session:{session_id.strip()}"
        claims = getattr(access_token, "claims", None)
        if not isinstance(claims, Mapping):
            raise ValueError("authenticated OAuth claims are unavailable")
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            raise ValueError("authenticated OAuth subject is unavailable")
        principal = f"oauth-sub:{subject.strip()}"
        return principal, f"mcp-session:{session_id.strip()}"

    async def _scope(self, context: Any, workspace: Workspace) -> InvocationScope:
        if self._transport_mode == "stdio":
            if self._stdio_session_id is None:
                raise ValueError("stdio initialization session is unavailable")
            principal = self._process_principal
            session_id = f"mcp-session:{self._stdio_session_id}"
        else:
            principal, session_id = await self._remote_identity(context)
        return InvocationScope(principal, session_id, str(workspace.root))

    async def _admit_tool(self, context: Any) -> InvocationScope | None:
        message = context.message
        name = message.name
        arguments = message.arguments or {}
        if not isinstance(name, str) or not isinstance(arguments, Mapping):
            raise ValueError("tool invocation is malformed")
        raw_workspace_id = arguments.get("workspace_id")
        if raw_workspace_id is None and name in WORKSPACE_OPTIONAL_TOOLS:
            return None
        workspace_id = _WORKSPACE_ID_ADAPTER.validate_python(
            raw_workspace_id,
            strict=True,
        )
        workspace = await self._resolve_workspace(workspace_id)
        return await self._scope(context, workspace)

    async def _admit_resource(self, context: Any) -> InvocationScope:
        workspace_id = _resource_workspace_id(context.message.uri)
        workspace = await self._resolve_workspace(workspace_id)
        return await self._scope(context, workspace)

    async def _dispatch(
        self,
        context: Any,
        call_next: Callable[[Any], Any],
        scope: InvocationScope | None,
    ) -> Any:
        scope_token = invocation_scope_var.set(scope)
        gate_token = covenant_gate_var.set(self._gate)
        resolver_token = workspace_resolver_var.set(self._resolver)
        admission_token = admitted_call_var.set(None)
        try:
            result = call_next(context)
            return await _resolve_awaitable(result)
        finally:
            admitted_call_var.reset(admission_token)
            workspace_resolver_var.reset(resolver_token)
            covenant_gate_var.reset(gate_token)
            invocation_scope_var.reset(scope_token)

    async def on_call_tool(self, context: Any, call_next: Callable[[Any], Any]) -> Any:
        """Establish tool context without performing handler-level admission."""

        captured = await _capture_async(lambda: self._admit_tool(context))
        if captured is _ADMISSION_FAILURE:
            # Tool handlers own the typed v7 error envelope.  Dispatch with no
            # scope so Covenant admission returns IDENTITY_UNAVAILABLE instead
            # of turning an authentication failure into a framework exception.
            return await self._dispatch(context, call_next, None)
        return await self._dispatch(
            context,
            call_next,
            cast(InvocationScope | None, captured),
        )

    async def on_read_resource(
        self,
        context: Any,
        call_next: Callable[[Any], Any],
    ) -> Any:
        """Establish exact workspace context around a v7 resource read."""

        captured = await _capture_async(lambda: self._admit_resource(context))
        if captured is _ADMISSION_FAILURE:
            raise ResourceInvocationContextError()
        return await self._dispatch(
            context,
            call_next,
            cast(InvocationScope, captured),
        )


class ResourceCommunionAuthorizer:
    """Require briefing for the exact resource scope installed by middleware."""

    def __init__(self, *, expected_gate: CovenantGate | None = None) -> None:
        self._expected_gate = expected_gate

    def _authorize(self, *, workspace: Workspace, resource_uri: str) -> None:
        scope = invocation_scope_var.get()
        gate = covenant_gate_var.get()
        resolver = workspace_resolver_var.get()
        if scope is None or gate is None or resolver is None:
            raise ValueError("resource invocation context is unavailable")
        if self._expected_gate is not None and gate is not self._expected_gate:
            raise ValueError("resource gate scope does not match")
        workspace_id = _resource_workspace_id(resource_uri)
        if not isinstance(workspace, Workspace) or workspace.workspace_id != workspace_id:
            raise ValueError("resource workspace ID does not match")
        candidate = InvocationScope(
            scope.principal_id,
            scope.transport_session_id,
            str(workspace.root),
        )
        if candidate != scope:
            raise ValueError("resource workspace scope does not match")
        state_store = getattr(gate, "state_store", None)
        if state_store is None or not state_store.is_briefed(scope):
            raise PermissionError("resource Communion is required")

    def authorize(self, *, workspace: Workspace, resource_uri: str) -> None:
        captured = _capture(
            lambda: self._authorize(
                workspace=workspace,
                resource_uri=resource_uri,
            )
        )
        if captured is _ADMISSION_FAILURE:
            raise ResourceAuthorizationError()


__all__ = [
    "FASTMCP_MIDDLEWARE_AVAILABLE",
    "RESOURCE_SUFFIXES",
    "ResourceAuthorizationError",
    "ResourceCommunionAuthorizer",
    "ResourceInvocationContextError",
    "ToolInvocationContextError",
    "TransportMode",
    "V7InvocationMiddleware",
    "WORKSPACE_OPTIONAL_TOOLS",
    "WorkspaceResolver",
]
