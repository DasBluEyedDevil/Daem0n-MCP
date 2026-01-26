"""
RitualPhaseTracker - Track ritual phases per project for tool visibility.

The daemon must know which ritual phase the agent is in:
- BRIEFING: Initial communion, gathering context
- EXPLORATION: Seeking counsel, reading/searching
- ACTION: Inscribing memories, making changes
- REFLECTION: Evaluating outcomes, self-critique

Phase transitions are triggered by tool calls, and each phase exposes
different tools to guide agents through the Sacred Covenant flow.

This bridges Phase 3's Reflexion state machine to Phase 5's tool visibility system.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Set


class RitualPhase(Enum):
    """Ritual phases representing agent workflow stages."""

    BRIEFING = "briefing"       # Initial communion, gathering context
    EXPLORATION = "exploration"  # Seeking counsel, reading/searching
    ACTION = "action"           # Inscribing memories, making changes
    REFLECTION = "reflection"   # Evaluating outcomes, self-critique


# Tool visibility per phase - which tools are allowed in each phase
# This mapping ensures agents follow the Sacred Covenant flow
PHASE_TOOL_VISIBILITY: Dict[str, Set[str]] = {
    "briefing": {
        "get_briefing",
        "health",
        "recall",
        "list_rules",
        "get_graph",
        # context_check is an entry point - must be visible in briefing to allow
        # transition to exploration phase (fixes Catch-22 phase-lock bug)
        "context_check",
    },
    "exploration": {
        "get_briefing",
        "health",
        "recall",
        "recall_for_file",
        "search_memories",
        "find_related",
        "check_rules",
        "list_rules",
        "find_code",
        "analyze_impact",
        "get_graph",
        "trace_chain",
        "context_check",
        "recall_hierarchical",
        "list_communities",
        "get_community_details",
        "recall_by_entity",
        "list_entities",
        "get_memory_versions",
        "get_memory_at_time",
    },
    "action": {
        "get_briefing",
        "health",
        "recall",
        "recall_for_file",
        "context_check",
        "remember",
        "remember_batch",
        "add_rule",
        "update_rule",
        "record_outcome",
        "link_memories",
        "unlink_memories",
        "pin_memory",
        "archive_memory",
        "execute_python",
        "set_active_context",
        "remove_from_active_context",
        "clear_active_context",
    },
    "reflection": {
        "get_briefing",
        "health",
        "recall",
        "verify_facts",
        "record_outcome",
        "compress_context",
        "search_memories",
        "find_related",
        "get_memory_versions",
    },
}


class RitualPhaseTracker:
    """
    Track ritual phase per project based on tool calls.

    The tracker maintains per-project phase state and triggers transitions
    based on tool semantics. Different projects can be in different phases
    simultaneously, enabling concurrent session handling.

    Usage:
        tracker = RitualPhaseTracker()

        # Get current phase (defaults to BRIEFING)
        phase = tracker.get_phase("/my/project")  # "briefing"

        # Transition on tool call
        tracker.on_tool_called("/my/project", "context_check")
        phase = tracker.get_phase("/my/project")  # "exploration"

        # Get visible tools for current phase
        tools = tracker.get_visible_tools("/my/project")
    """

    def __init__(self) -> None:
        """Initialize the phase tracker with empty state."""
        self._phases: Dict[str, RitualPhase] = {}
        self._last_activity: Dict[str, datetime] = {}

    def get_phase(self, project_path: str) -> str:
        """
        Get current ritual phase for a project.

        Args:
            project_path: The project path to query

        Returns:
            Phase value string: "briefing", "exploration", "action", or "reflection"
        """
        return self._phases.get(project_path, RitualPhase.BRIEFING).value

    def get_phase_enum(self, project_path: str) -> RitualPhase:
        """
        Get current ritual phase as enum for a project.

        Args:
            project_path: The project path to query

        Returns:
            RitualPhase enum value
        """
        return self._phases.get(project_path, RitualPhase.BRIEFING)

    def on_tool_called(self, project_path: str, tool_name: str) -> None:
        """
        Update phase based on tool call.

        Tool calls trigger phase transitions based on their semantics:
        - get_briefing -> BRIEFING (communion entry point)
        - context_check -> EXPLORATION (seeking counsel)
        - remember/add_rule/execute_python -> ACTION (inscribing)
        - record_outcome/verify_facts -> REFLECTION (evaluating)

        Args:
            project_path: The project path being accessed
            tool_name: The name of the tool being called
        """
        self._last_activity[project_path] = datetime.now(timezone.utc)

        # Phase transition logic based on tool semantics
        if tool_name == "get_briefing":
            self._phases[project_path] = RitualPhase.BRIEFING
        elif tool_name == "context_check":
            self._phases[project_path] = RitualPhase.EXPLORATION
        elif tool_name in {
            "remember",
            "remember_batch",
            "add_rule",
            "update_rule",
            "execute_python",
        }:
            self._phases[project_path] = RitualPhase.ACTION
        elif tool_name in {"record_outcome", "verify_facts"}:
            self._phases[project_path] = RitualPhase.REFLECTION

    def get_visible_tools(self, project_path: str) -> Set[str]:
        """
        Get tools visible for current phase.

        Args:
            project_path: The project path to query

        Returns:
            Set of tool names available in the current phase
        """
        phase = self.get_phase(project_path)
        return PHASE_TOOL_VISIBILITY.get(phase, PHASE_TOOL_VISIBILITY["briefing"])

    def get_last_activity(self, project_path: str) -> datetime | None:
        """
        Get the timestamp of last activity for a project.

        Args:
            project_path: The project path to query

        Returns:
            UTC datetime of last tool call, or None if no activity
        """
        return self._last_activity.get(project_path)

    def reset_phase(self, project_path: str) -> None:
        """
        Reset to briefing phase (e.g., on session timeout).

        Args:
            project_path: The project path to reset
        """
        self._phases[project_path] = RitualPhase.BRIEFING
        self._last_activity.pop(project_path, None)

    def clear_project(self, project_path: str) -> None:
        """
        Remove all state for a project.

        Args:
            project_path: The project path to clear
        """
        self._phases.pop(project_path, None)
        self._last_activity.pop(project_path, None)

    def __repr__(self) -> str:
        """String representation showing tracked projects."""
        projects = list(self._phases.keys())
        return f"RitualPhaseTracker(projects={len(projects)})"
