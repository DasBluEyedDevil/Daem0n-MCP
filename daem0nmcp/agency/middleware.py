"""
AgencyMiddleware - Phase-aware tool visibility filtering.

Filters tools based on the current ritual phase using FastMCP's middleware hooks.
This reduces action space entropy by showing only relevant tools per phase.

Integration with CovenantMiddleware:
- CovenantMiddleware checks communion/counsel requirements
- AgencyMiddleware filters tools by ritual phase
- Both run in sequence; AgencyMiddleware registered after CovenantMiddleware
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Set

from .phase_tracker import RitualPhaseTracker, PHASE_TOOL_VISIBILITY

logger = logging.getLogger(__name__)

# Check if FastMCP middleware is available
try:
    from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
    from fastmcp.tools import ToolResult
    from mcp import types as mt
    _FASTMCP_MIDDLEWARE_AVAILABLE = True
except ImportError:
    _FASTMCP_MIDDLEWARE_AVAILABLE = False
    Middleware = object
    MiddlewareContext = Any
    CallNext = Any
    ToolResult = Any


class AgencyMiddleware(Middleware if _FASTMCP_MIDDLEWARE_AVAILABLE else object):
    """
    FastMCP middleware for phase-based tool visibility.

    Filters tools via on_list_tools() and blocks execution via on_call_tool()
    based on the current ritual phase for each project.

    Usage:
        tracker = RitualPhaseTracker()
        middleware = AgencyMiddleware(tracker.get_phase)
        mcp.add_middleware(middleware)
    """

    def __init__(
        self,
        get_phase: Callable[[str], str],
        extract_project_path: Optional[Callable[[Dict[str, Any]], Optional[str]]] = None,
    ):
        """
        Initialize AgencyMiddleware.

        Args:
            get_phase: Callback that takes project_path and returns current phase string
            extract_project_path: Optional callback to extract project_path from tool args
                                  Defaults to args.get("project_path")
        """
        if _FASTMCP_MIDDLEWARE_AVAILABLE:
            super().__init__()

        self._get_phase = get_phase
        self._extract_project_path = extract_project_path or (lambda args: args.get("project_path"))

    def _get_project_path_from_context(self, context: "MiddlewareContext") -> Optional[str]:
        """Extract project_path from middleware context."""
        try:
            args = context.message.arguments or {}
            return self._extract_project_path(args)
        except Exception:
            return None

    async def on_list_tools(
        self,
        context: "MiddlewareContext",
        call_next: "CallNext",
    ) -> List:
        """
        Filter tool list based on ritual phase.

        Tools not in the current phase's visibility set are excluded from the list.
        This prevents the model from even seeing irrelevant tools, reducing token cost.
        """
        # Get all tools first
        all_tools = await call_next(context)

        # Try to get project path from context
        # Note: on_list_tools may not have project_path in context
        # For now, default to briefing phase if no project context
        project_path = self._get_project_path_from_context(context)

        if project_path is None:
            # No project context - show ALL tools so Claude Code can discover them
            # Execution is restricted to briefing-phase tools via on_call_tool()
            logger.debug("AgencyMiddleware: No project context, showing all tools for discovery")
            return all_tools

        phase = self._get_phase(project_path)
        allowed_tools = PHASE_TOOL_VISIBILITY.get(phase, PHASE_TOOL_VISIBILITY["briefing"])

        filtered = [tool for tool in all_tools if tool.name in allowed_tools]

        logger.debug(
            f"AgencyMiddleware: Phase '{phase}' - {len(filtered)}/{len(all_tools)} tools visible"
        )

        return filtered

    async def on_call_tool(
        self,
        context: "MiddlewareContext[mt.CallToolRequestParams]",
        call_next: "CallNext[mt.CallToolRequestParams, ToolResult]",
    ) -> "ToolResult":
        """
        Block tool calls not visible in current phase.

        Defense in depth: even if a tool is called directly (bypassing on_list_tools),
        this ensures the tool cannot execute if not allowed in the current phase.
        """
        tool_name = context.message.name
        project_path = self._get_project_path_from_context(context)

        if project_path is None:
            # No project path - enforce briefing phase (restrictive default)
            phase = "briefing"
        else:
            phase = self._get_phase(project_path)
        allowed_tools = PHASE_TOOL_VISIBILITY.get(phase, PHASE_TOOL_VISIBILITY["briefing"])

        if tool_name not in allowed_tools:
            logger.info(
                f"AgencyMiddleware: Blocked '{tool_name}' in phase '{phase}'"
            )
            return ToolResult(structured_content={
                "status": "blocked",
                "violation": "TOOL_NOT_VISIBLE",
                "message": (
                    f"The tool '{tool_name}' is not available in the {phase} phase. "
                    f"The daemon reveals only the tools needed for each ritual phase."
                ),
                "current_phase": phase,
                "available_tools": sorted(allowed_tools),
                "hint": self._get_phase_hint(phase, tool_name),
            })

        return await call_next(context)

    def _get_phase_hint(self, current_phase: str, requested_tool: str) -> str:
        """Get hint about which phase contains the requested tool."""
        for phase, tools in PHASE_TOOL_VISIBILITY.items():
            if requested_tool in tools:
                return f"Tool '{requested_tool}' is available in the '{phase}' phase."
        return f"Tool '{requested_tool}' is not recognized."

    def __repr__(self) -> str:
        return f"AgencyMiddleware(get_phase={self._get_phase.__name__})"
