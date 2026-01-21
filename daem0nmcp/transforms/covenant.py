"""
CovenantTransform - FastMCP 3.0 Transform for Sacred Covenant Enforcement.

This transform implements middleware-style interception of MCP tool calls
to enforce the Sacred Covenant protocol:

    COMMUNE (get_briefing) -> SEEK COUNSEL (context_check) -> INSCRIBE (remember) -> SEAL (record_outcome)

The transform can be used in two ways:
1. Standalone: Call check_tool_access() directly to validate tool calls
2. FastMCP Middleware: Use on_call_tool() hook when integrated with FastMCP 3.0

The Sacred Covenant flow ensures:
- AI agents commune with the Daem0n before any work (get briefing context)
- AI agents seek counsel before mutations (check for conflicts/duplicates)
- Decisions are inscribed with proper context
- Outcomes are sealed to track what worked/failed
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, Optional, Set

logger = logging.getLogger(__name__)

# TTL for context checks (5 minutes default, same as existing covenant.py)
COUNSEL_TTL_SECONDS = 300


# ============================================================================
# TOOL CLASSIFICATION
# ============================================================================

# Tools exempt from all covenant enforcement (entry points and diagnostics)
COVENANT_EXEMPT_TOOLS: Set[str] = {
    "get_briefing",      # Entry point - starts communion
    "health",            # Diagnostic - always available
    "context_check",     # Part of the covenant flow
    "recall",            # Read-only query
    "recall_for_file",   # Read-only query
    "search_memories",   # Read-only query
    "find_related",      # Read-only query
    "check_rules",       # Read-only query
    "list_rules",        # Read-only query
    "find_code",         # Read-only query
    "analyze_impact",    # Read-only analysis
    "export_data",       # Read-only export
    "scan_todos",        # Read-only scan (unless auto_remember=True)
    "propose_refactor",  # Read-only analysis
    "get_graph",         # Read-only query
    "trace_chain",       # Read-only query
    "recall_hierarchical",  # Read-only query
    "list_communities",     # Read-only query
    "get_community_details",  # Read-only query
    "recall_by_entity",     # Read-only query
    "list_entities",        # Read-only query
    "get_memory_versions",  # Read-only query
    "get_memory_at_time",   # Read-only query
    "list_context_triggers",  # Read-only query
    "check_context_triggers",  # Read-only query
    "get_active_context",   # Read-only query
    "list_linked_projects",  # Read-only query
}

# Tools that REQUIRE communion (must call get_briefing first)
# These are all mutating tools - they change state
COMMUNION_REQUIRED_TOOLS: Set[str] = {
    "remember",
    "remember_batch",
    "add_rule",
    "update_rule",
    "record_outcome",
    "link_memories",
    "unlink_memories",
    "pin_memory",
    "archive_memory",
    "prune_memories",
    "cleanup_memories",
    "compact_memories",
    "import_data",
    "rebuild_index",
    "index_project",
    "ingest_doc",
    "set_active_context",
    "remove_from_active_context",
    "clear_active_context",
    "link_projects",
    "unlink_projects",
    "consolidate_linked_databases",
    "rebuild_communities",
    "backfill_entities",
    "add_context_trigger",
    "remove_context_trigger",
}

# Tools that REQUIRE counsel (must call context_check before mutating)
# These are the most important mutations that could cause conflicts
COUNSEL_REQUIRED_TOOLS: Set[str] = {
    "remember",
    "remember_batch",
    "add_rule",
    "update_rule",
    "prune_memories",
    "cleanup_memories",
    "compact_memories",
    "import_data",
    "ingest_doc",
}


# ============================================================================
# COVENANT VIOLATION RESPONSES
# ============================================================================

class CovenantViolation:
    """
    Standard violation response structures for covenant breaches.

    Returns structured dicts that block tool execution and guide
    the AI toward proper covenant adherence. The responses include
    clear explanations and remedies.
    """

    @staticmethod
    def communion_required(project_path: str) -> Dict[str, Any]:
        """
        Response when tool is called without prior get_briefing().

        The Sacred Covenant demands communion before any meaningful work.
        This ensures the AI has context about existing memories, warnings,
        and rules before making changes.

        Args:
            project_path: The project path being accessed

        Returns:
            Blocking response with remedy instructions
        """
        return {
            "status": "blocked",
            "violation": "COMMUNION_REQUIRED",
            "message": (
                "The Sacred Covenant demands communion before work begins. "
                "You must first call get_briefing() to commune with the Daem0n "
                "and receive context about this realm's memories, warnings, and rules."
            ),
            "project_path": project_path,
            "remedy": {
                "tool": "get_briefing",
                "args": {"project_path": project_path},
                "description": "Begin communion with the Daem0n",
            },
        }

    @staticmethod
    def counsel_required(tool_name: str, project_path: str) -> Dict[str, Any]:
        """
        Response when mutating tool is called without prior context_check().

        Before inscribing new memories, one must seek counsel on what
        already exists to avoid contradictions and duplications.

        Args:
            tool_name: The tool that was blocked
            project_path: The project path being accessed

        Returns:
            Blocking response with remedy instructions
        """
        return {
            "status": "blocked",
            "violation": "COUNSEL_REQUIRED",
            "message": (
                f"The Sacred Covenant requires seeking counsel before using '{tool_name}'. "
                f"You must first call context_check() to understand existing memories "
                f"and rules related to your intended action. This prevents contradictions "
                f"and honors the wisdom already inscribed."
            ),
            "project_path": project_path,
            "tool_blocked": tool_name,
            "remedy": {
                "tool": "context_check",
                "args": {
                    "description": f"About to use {tool_name}",
                    "project_path": project_path,
                },
                "description": f"Seek counsel before {tool_name}",
            },
        }

    @staticmethod
    def counsel_expired(tool_name: str, project_path: str, age_seconds: int) -> Dict[str, Any]:
        """
        Response when context_check was done but has expired.

        Counsel becomes stale after COUNSEL_TTL_SECONDS (default 5 minutes).
        The context may have changed, requiring fresh consultation.

        Args:
            tool_name: The tool that was blocked
            project_path: The project path being accessed
            age_seconds: How old the most recent counsel is

        Returns:
            Blocking response with remedy instructions
        """
        return {
            "status": "blocked",
            "violation": "COUNSEL_EXPIRED",
            "message": (
                f"Your counsel has grown stale ({age_seconds}s old, limit is {COUNSEL_TTL_SECONDS}s). "
                f"The context may have changed. Please seek fresh counsel before '{tool_name}'."
            ),
            "project_path": project_path,
            "tool_blocked": tool_name,
            "remedy": {
                "tool": "context_check",
                "args": {
                    "description": f"Refreshing counsel before {tool_name}",
                    "project_path": project_path,
                },
                "description": "Seek fresh counsel",
            },
        }


# ============================================================================
# COVENANT TRANSFORM
# ============================================================================

class CovenantTransform:
    """
    FastMCP 3.0 Transform for Sacred Covenant enforcement.

    This transform intercepts tool calls to enforce the covenant protocol:
    1. Exempt tools (health, get_briefing, read-only) always pass
    2. Communion-required tools block until get_briefing() is called
    3. Counsel-required tools block until context_check() is called

    The transform tracks state per-project, allowing multiple projects
    to be served concurrently with independent covenant states.

    Usage (standalone):
        transform = CovenantTransform()

        result = transform.check_tool_access(
            tool_name="remember",
            project_path="/my/project",
            get_state=lambda p: {"briefed": True, "context_checks": [...]}
        )

        if result is not None:
            return result  # Blocked, return violation response
        # Otherwise proceed with tool execution

    Usage (FastMCP middleware):
        # Will be implemented in Task 2.2 when integrating with server.py
    """

    def __init__(
        self,
        counsel_ttl_seconds: int = COUNSEL_TTL_SECONDS,
        exempt_tools: Optional[Set[str]] = None,
        communion_required_tools: Optional[Set[str]] = None,
        counsel_required_tools: Optional[Set[str]] = None,
    ):
        """
        Initialize the CovenantTransform.

        Args:
            counsel_ttl_seconds: How long context_check remains valid
            exempt_tools: Override the default exempt tools set
            communion_required_tools: Override the default communion tools set
            counsel_required_tools: Override the default counsel tools set
        """
        self.counsel_ttl_seconds = counsel_ttl_seconds
        self.exempt_tools = exempt_tools or COVENANT_EXEMPT_TOOLS
        self.communion_required_tools = communion_required_tools or COMMUNION_REQUIRED_TOOLS
        self.counsel_required_tools = counsel_required_tools or COUNSEL_REQUIRED_TOOLS

    def check_tool_access(
        self,
        tool_name: str,
        project_path: Optional[str],
        get_state: Callable[[Optional[str]], Optional[Dict[str, Any]]],
    ) -> Optional[Dict[str, Any]]:
        """
        Check if a tool call is allowed under the Sacred Covenant.

        This is the main enforcement method. It checks tool classification
        and session state to determine if the call should proceed.

        Args:
            tool_name: Name of the tool being called
            project_path: Project root path (may be None for some tools)
            get_state: Callback to get session state for a project path.
                      Should return dict with 'briefed' (bool) and
                      'context_checks' (list of dicts with 'timestamp')

        Returns:
            None if tool is allowed, or a violation dict if blocked.
            The violation dict includes status, violation type, message,
            and remedy instructions.
        """
        # Step 1: Check if tool is exempt
        if tool_name in self.exempt_tools:
            logger.debug(f"Tool '{tool_name}' is exempt from covenant enforcement")
            return None  # Allowed

        # Step 2: Get session state
        state = get_state(project_path)

        # Step 3: Check communion requirement
        if tool_name in self.communion_required_tools:
            if state is None or not state.get("briefed", False):
                logger.info(f"Communion required for tool '{tool_name}' on project '{project_path}'")
                return CovenantViolation.communion_required(project_path or "unknown")

        # Step 4: Check counsel requirement
        if tool_name in self.counsel_required_tools:
            # Must first check communion (counsel implies communion)
            if state is None or not state.get("briefed", False):
                logger.info(f"Communion required before counsel for tool '{tool_name}'")
                return CovenantViolation.communion_required(project_path or "unknown")

            # Check for fresh counsel
            context_checks = state.get("context_checks", [])

            if not context_checks:
                logger.info(f"Counsel required for tool '{tool_name}'")
                return CovenantViolation.counsel_required(tool_name, project_path or "unknown")

            # Find the most recent context check with a valid timestamp
            most_recent_age = self._get_freshest_counsel_age(context_checks)

            if most_recent_age is None:
                # No valid timestamped checks
                logger.info(f"No valid timestamped counsel found for '{tool_name}'")
                return CovenantViolation.counsel_required(tool_name, project_path or "unknown")

            if most_recent_age > self.counsel_ttl_seconds:
                logger.info(f"Counsel expired ({most_recent_age:.0f}s old) for '{tool_name}'")
                return CovenantViolation.counsel_expired(
                    tool_name,
                    project_path or "unknown",
                    int(most_recent_age)
                )

        # All checks passed
        logger.debug(f"Tool '{tool_name}' allowed under covenant")
        return None

    def _get_freshest_counsel_age(
        self,
        context_checks: list,
    ) -> Optional[float]:
        """
        Find the age of the most recent valid context check.

        Args:
            context_checks: List of context check entries

        Returns:
            Age in seconds of the freshest check, or None if no valid checks
        """
        now = datetime.now(timezone.utc)
        most_recent_age: Optional[float] = None

        for check in context_checks:
            if isinstance(check, dict) and "timestamp" in check:
                try:
                    check_time = datetime.fromisoformat(check["timestamp"])
                    # Handle timezone-naive timestamps
                    if check_time.tzinfo is None:
                        check_time = check_time.replace(tzinfo=timezone.utc)
                    age = (now - check_time).total_seconds()
                    if most_recent_age is None or age < most_recent_age:
                        most_recent_age = age
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid timestamp in context check: {e}")
                    continue
            elif isinstance(check, str):
                # Legacy format - treat as valid (backwards compatibility)
                return 0.0  # Age 0 = always fresh for legacy

        return most_recent_age

    def __repr__(self) -> str:
        return (
            f"CovenantTransform("
            f"counsel_ttl={self.counsel_ttl_seconds}s, "
            f"exempt={len(self.exempt_tools)}, "
            f"communion={len(self.communion_required_tools)}, "
            f"counsel={len(self.counsel_required_tools)}"
            f")"
        )
