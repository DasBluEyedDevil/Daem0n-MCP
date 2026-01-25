"""Tests for RitualPhaseTracker - Phase tracking for tool visibility."""

from datetime import datetime, timezone

import pytest

from daem0nmcp.agency import (
    PHASE_TOOL_VISIBILITY,
    RitualPhase,
    RitualPhaseTracker,
)


class TestRitualPhaseEnum:
    """Tests for RitualPhase enum."""

    def test_enum_values(self):
        """Should have all four ritual phases."""
        assert RitualPhase.BRIEFING.value == "briefing"
        assert RitualPhase.EXPLORATION.value == "exploration"
        assert RitualPhase.ACTION.value == "action"
        assert RitualPhase.REFLECTION.value == "reflection"

    def test_enum_count(self):
        """Should have exactly 4 phases."""
        assert len(RitualPhase) == 4


class TestPhaseToolVisibility:
    """Tests for PHASE_TOOL_VISIBILITY mapping."""

    def test_all_phases_have_visibility(self):
        """Each phase should have a tool visibility set."""
        for phase in RitualPhase:
            assert phase.value in PHASE_TOOL_VISIBILITY
            assert isinstance(PHASE_TOOL_VISIBILITY[phase.value], set)

    def test_briefing_tools_minimal(self):
        """Briefing phase should have minimal tools for initial communion."""
        briefing_tools = PHASE_TOOL_VISIBILITY["briefing"]
        assert "get_briefing" in briefing_tools
        assert "health" in briefing_tools
        assert "recall" in briefing_tools
        # Should not include mutation tools
        assert "remember" not in briefing_tools
        assert "remember_batch" not in briefing_tools
        assert "execute_python" not in briefing_tools

    def test_exploration_tools_includes_search(self):
        """Exploration phase should include search and analysis tools."""
        exploration_tools = PHASE_TOOL_VISIBILITY["exploration"]
        assert "context_check" in exploration_tools
        assert "search_memories" in exploration_tools
        assert "find_related" in exploration_tools
        assert "recall_for_file" in exploration_tools
        assert "get_memory_versions" in exploration_tools
        # Should not include mutation tools
        assert "remember" not in exploration_tools
        assert "execute_python" not in exploration_tools

    def test_action_tools_includes_mutations(self):
        """Action phase should include mutation tools."""
        action_tools = PHASE_TOOL_VISIBILITY["action"]
        assert "remember" in action_tools
        assert "remember_batch" in action_tools
        assert "add_rule" in action_tools
        assert "update_rule" in action_tools
        assert "execute_python" in action_tools
        assert "link_memories" in action_tools
        # Should still include base tools
        assert "get_briefing" in action_tools
        assert "health" in action_tools

    def test_reflection_tools_includes_verification(self):
        """Reflection phase should include verification and outcome tools."""
        reflection_tools = PHASE_TOOL_VISIBILITY["reflection"]
        assert "verify_facts" in reflection_tools
        assert "record_outcome" in reflection_tools
        assert "compress_context" in reflection_tools
        assert "get_memory_versions" in reflection_tools
        # Should not include heavy mutation tools
        assert "execute_python" not in reflection_tools
        assert "remember_batch" not in reflection_tools

    def test_common_tools_in_all_phases(self):
        """Core tools should be available in all phases."""
        common_tools = {"get_briefing", "health", "recall"}
        for phase in RitualPhase:
            phase_tools = PHASE_TOOL_VISIBILITY[phase.value]
            for tool in common_tools:
                assert tool in phase_tools, f"{tool} missing in {phase.value}"

    def test_no_empty_phase_visibility(self):
        """Each phase should have at least one tool."""
        for phase in RitualPhase:
            assert len(PHASE_TOOL_VISIBILITY[phase.value]) > 0


class TestRitualPhaseTrackerInitialization:
    """Tests for RitualPhaseTracker initialization."""

    def test_new_tracker_empty(self):
        """New tracker should have no tracked projects."""
        tracker = RitualPhaseTracker()
        assert repr(tracker) == "RitualPhaseTracker(projects=0)"

    def test_unknown_project_returns_briefing(self):
        """Unknown project path should default to BRIEFING phase."""
        tracker = RitualPhaseTracker()
        assert tracker.get_phase("/unknown/project") == "briefing"

    def test_get_phase_enum_for_unknown(self):
        """get_phase_enum should return RitualPhase.BRIEFING for unknown."""
        tracker = RitualPhaseTracker()
        assert tracker.get_phase_enum("/unknown") == RitualPhase.BRIEFING


class TestRitualPhaseTransitions:
    """Tests for phase transitions based on tool calls."""

    def test_get_briefing_transitions_to_briefing(self):
        """Calling get_briefing should transition to BRIEFING phase."""
        tracker = RitualPhaseTracker()
        tracker.on_tool_called("/project", "context_check")  # First move to exploration
        assert tracker.get_phase("/project") == "exploration"

        tracker.on_tool_called("/project", "get_briefing")
        assert tracker.get_phase("/project") == "briefing"

    def test_context_check_transitions_to_exploration(self):
        """Calling context_check should transition to EXPLORATION phase."""
        tracker = RitualPhaseTracker()
        tracker.on_tool_called("/project", "context_check")
        assert tracker.get_phase("/project") == "exploration"

    def test_remember_transitions_to_action(self):
        """Calling remember should transition to ACTION phase."""
        tracker = RitualPhaseTracker()
        tracker.on_tool_called("/project", "remember")
        assert tracker.get_phase("/project") == "action"

    def test_remember_batch_transitions_to_action(self):
        """Calling remember_batch should transition to ACTION phase."""
        tracker = RitualPhaseTracker()
        tracker.on_tool_called("/project", "remember_batch")
        assert tracker.get_phase("/project") == "action"

    def test_add_rule_transitions_to_action(self):
        """Calling add_rule should transition to ACTION phase."""
        tracker = RitualPhaseTracker()
        tracker.on_tool_called("/project", "add_rule")
        assert tracker.get_phase("/project") == "action"

    def test_update_rule_transitions_to_action(self):
        """Calling update_rule should transition to ACTION phase."""
        tracker = RitualPhaseTracker()
        tracker.on_tool_called("/project", "update_rule")
        assert tracker.get_phase("/project") == "action"

    def test_execute_python_transitions_to_action(self):
        """Calling execute_python should transition to ACTION phase."""
        tracker = RitualPhaseTracker()
        tracker.on_tool_called("/project", "execute_python")
        assert tracker.get_phase("/project") == "action"

    def test_record_outcome_transitions_to_reflection(self):
        """Calling record_outcome should transition to REFLECTION phase."""
        tracker = RitualPhaseTracker()
        tracker.on_tool_called("/project", "record_outcome")
        assert tracker.get_phase("/project") == "reflection"

    def test_verify_facts_transitions_to_reflection(self):
        """Calling verify_facts should transition to REFLECTION phase."""
        tracker = RitualPhaseTracker()
        tracker.on_tool_called("/project", "verify_facts")
        assert tracker.get_phase("/project") == "reflection"

    def test_non_transition_tool_no_change(self):
        """Tools not in transition logic should not change phase."""
        tracker = RitualPhaseTracker()
        tracker.on_tool_called("/project", "context_check")  # Move to exploration
        assert tracker.get_phase("/project") == "exploration"

        # Call non-transition tools
        tracker.on_tool_called("/project", "search_memories")
        assert tracker.get_phase("/project") == "exploration"

        tracker.on_tool_called("/project", "find_related")
        assert tracker.get_phase("/project") == "exploration"

        tracker.on_tool_called("/project", "health")
        assert tracker.get_phase("/project") == "exploration"

    def test_action_tool_from_briefing(self):
        """Calling action tool from briefing should transition correctly."""
        tracker = RitualPhaseTracker()
        assert tracker.get_phase("/project") == "briefing"

        # Jump directly to action
        tracker.on_tool_called("/project", "remember")
        assert tracker.get_phase("/project") == "action"


class TestLastActivityTracking:
    """Tests for last activity timestamp tracking."""

    def test_last_activity_none_initially(self):
        """Last activity should be None for unknown projects."""
        tracker = RitualPhaseTracker()
        assert tracker.get_last_activity("/unknown") is None

    def test_last_activity_set_on_tool_call(self):
        """Last activity should be set when tool is called."""
        tracker = RitualPhaseTracker()
        before = datetime.now(timezone.utc)
        tracker.on_tool_called("/project", "get_briefing")
        after = datetime.now(timezone.utc)

        last_activity = tracker.get_last_activity("/project")
        assert last_activity is not None
        assert before <= last_activity <= after

    def test_last_activity_updates_on_each_call(self):
        """Last activity should update on each tool call."""
        tracker = RitualPhaseTracker()
        tracker.on_tool_called("/project", "get_briefing")
        first_activity = tracker.get_last_activity("/project")

        tracker.on_tool_called("/project", "context_check")
        second_activity = tracker.get_last_activity("/project")

        assert second_activity >= first_activity


class TestMultiProjectIsolation:
    """Tests for multi-project phase isolation."""

    def test_independent_project_phases(self):
        """Different projects should have independent phases."""
        tracker = RitualPhaseTracker()

        # Project A in exploration
        tracker.on_tool_called("/project/a", "context_check")
        # Project B in action
        tracker.on_tool_called("/project/b", "remember")
        # Project C in reflection
        tracker.on_tool_called("/project/c", "record_outcome")

        assert tracker.get_phase("/project/a") == "exploration"
        assert tracker.get_phase("/project/b") == "action"
        assert tracker.get_phase("/project/c") == "reflection"

    def test_project_phase_does_not_affect_others(self):
        """Changing one project's phase should not affect others."""
        tracker = RitualPhaseTracker()

        tracker.on_tool_called("/project/a", "context_check")
        tracker.on_tool_called("/project/b", "context_check")

        assert tracker.get_phase("/project/a") == "exploration"
        assert tracker.get_phase("/project/b") == "exploration"

        # Change project A only
        tracker.on_tool_called("/project/a", "remember")

        assert tracker.get_phase("/project/a") == "action"
        assert tracker.get_phase("/project/b") == "exploration"


class TestPhaseReset:
    """Tests for phase reset functionality."""

    def test_reset_returns_to_briefing(self):
        """reset_phase should return project to BRIEFING."""
        tracker = RitualPhaseTracker()
        tracker.on_tool_called("/project", "remember")  # Move to action
        assert tracker.get_phase("/project") == "action"

        tracker.reset_phase("/project")
        assert tracker.get_phase("/project") == "briefing"

    def test_reset_clears_last_activity(self):
        """reset_phase should clear last activity timestamp."""
        tracker = RitualPhaseTracker()
        tracker.on_tool_called("/project", "get_briefing")
        assert tracker.get_last_activity("/project") is not None

        tracker.reset_phase("/project")
        assert tracker.get_last_activity("/project") is None

    def test_reset_unknown_project_no_error(self):
        """reset_phase on unknown project should not raise error."""
        tracker = RitualPhaseTracker()
        # Should not raise
        tracker.reset_phase("/unknown/project")
        assert tracker.get_phase("/unknown/project") == "briefing"


class TestProjectClearing:
    """Tests for project state clearing."""

    def test_clear_project_removes_state(self):
        """clear_project should remove all state for a project."""
        tracker = RitualPhaseTracker()
        tracker.on_tool_called("/project", "remember")

        tracker.clear_project("/project")

        # Should be back to default (briefing via get_phase)
        assert tracker.get_phase("/project") == "briefing"
        assert tracker.get_last_activity("/project") is None

    def test_clear_unknown_project_no_error(self):
        """clear_project on unknown project should not raise error."""
        tracker = RitualPhaseTracker()
        # Should not raise
        tracker.clear_project("/unknown/project")


class TestToolVisibilityRetrieval:
    """Tests for get_visible_tools method."""

    def test_visible_tools_for_briefing(self):
        """Should return briefing tools for new project."""
        tracker = RitualPhaseTracker()
        tools = tracker.get_visible_tools("/project")
        assert tools == PHASE_TOOL_VISIBILITY["briefing"]

    def test_visible_tools_for_exploration(self):
        """Should return exploration tools after context_check."""
        tracker = RitualPhaseTracker()
        tracker.on_tool_called("/project", "context_check")
        tools = tracker.get_visible_tools("/project")
        assert tools == PHASE_TOOL_VISIBILITY["exploration"]

    def test_visible_tools_for_action(self):
        """Should return action tools after remember."""
        tracker = RitualPhaseTracker()
        tracker.on_tool_called("/project", "remember")
        tools = tracker.get_visible_tools("/project")
        assert tools == PHASE_TOOL_VISIBILITY["action"]

    def test_visible_tools_for_reflection(self):
        """Should return reflection tools after record_outcome."""
        tracker = RitualPhaseTracker()
        tracker.on_tool_called("/project", "record_outcome")
        tools = tracker.get_visible_tools("/project")
        assert tools == PHASE_TOOL_VISIBILITY["reflection"]

    def test_visible_tools_different_per_project(self):
        """Different projects should have different visible tools."""
        tracker = RitualPhaseTracker()
        tracker.on_tool_called("/project/a", "context_check")
        tracker.on_tool_called("/project/b", "remember")

        tools_a = tracker.get_visible_tools("/project/a")
        tools_b = tracker.get_visible_tools("/project/b")

        assert tools_a != tools_b
        assert tools_a == PHASE_TOOL_VISIBILITY["exploration"]
        assert tools_b == PHASE_TOOL_VISIBILITY["action"]


class TestRepr:
    """Tests for string representation."""

    def test_repr_empty(self):
        """Should show zero projects initially."""
        tracker = RitualPhaseTracker()
        assert repr(tracker) == "RitualPhaseTracker(projects=0)"

    def test_repr_with_projects(self):
        """Should show correct project count."""
        tracker = RitualPhaseTracker()
        tracker.on_tool_called("/project/a", "get_briefing")
        tracker.on_tool_called("/project/b", "context_check")

        assert repr(tracker) == "RitualPhaseTracker(projects=2)"


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_project_path(self):
        """Empty project path should still work."""
        tracker = RitualPhaseTracker()
        tracker.on_tool_called("", "context_check")
        assert tracker.get_phase("") == "exploration"

    def test_same_tool_repeated(self):
        """Calling same transition tool repeatedly should be stable."""
        tracker = RitualPhaseTracker()
        for _ in range(10):
            tracker.on_tool_called("/project", "remember")
        assert tracker.get_phase("/project") == "action"

    def test_rapid_phase_changes(self):
        """Rapid phase changes should work correctly."""
        tracker = RitualPhaseTracker()

        tracker.on_tool_called("/project", "get_briefing")
        assert tracker.get_phase("/project") == "briefing"

        tracker.on_tool_called("/project", "context_check")
        assert tracker.get_phase("/project") == "exploration"

        tracker.on_tool_called("/project", "remember")
        assert tracker.get_phase("/project") == "action"

        tracker.on_tool_called("/project", "record_outcome")
        assert tracker.get_phase("/project") == "reflection"

        tracker.on_tool_called("/project", "get_briefing")
        assert tracker.get_phase("/project") == "briefing"

    def test_phase_cycle_complete_flow(self):
        """Complete Sacred Covenant flow should work."""
        tracker = RitualPhaseTracker()
        project = "/sacred/project"

        # 1. COMMUNION: Start with briefing
        tracker.on_tool_called(project, "get_briefing")
        assert tracker.get_phase(project) == "briefing"

        # 2. SEEK COUNSEL: Move to exploration
        tracker.on_tool_called(project, "context_check")
        assert tracker.get_phase(project) == "exploration"

        # 3. INSCRIBE: Move to action
        tracker.on_tool_called(project, "remember")
        assert tracker.get_phase(project) == "action"

        # 4. SEAL: Move to reflection
        tracker.on_tool_called(project, "record_outcome")
        assert tracker.get_phase(project) == "reflection"

        # 5. Back to start: New communion
        tracker.on_tool_called(project, "get_briefing")
        assert tracker.get_phase(project) == "briefing"
