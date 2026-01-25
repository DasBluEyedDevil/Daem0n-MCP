"""
Integration tests for Phase 5: Dynamic Agency.

Tests all AGENCY-* requirements end-to-end:
- AGENCY-01: Context-aware tool masking hides irrelevant tools dynamically
- AGENCY-02: Tool visibility determined by current ritual phase (focus/domain)
- AGENCY-03: execute_python tool provides sandboxed code execution
- AGENCY-04: Sandbox isolation via Firecracker microVMs (E2B)
- AGENCY-05: Capability-scoped access enforces least-privilege

These tests verify the complete Phase 5 Dynamic Agency system works together,
including phase tracking, tool filtering, sandbox execution, and capability
scoping across the full ritual flow.
"""

import inspect
import logging
import os

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from daem0nmcp.agency import (
    AgencyMiddleware,
    CapabilityManager,
    CapabilityScope,
    ExecutionResult,
    PHASE_TOOL_VISIBILITY,
    RitualPhase,
    RitualPhaseTracker,
    SandboxExecutor,
    check_capability,
)


# ============================================================================
# AGENCY-01: Context-aware tool masking hides irrelevant tools dynamically
# ============================================================================


class TestAgency01_ContextAwareToolMasking:
    """
    AGENCY-01: Context-aware tool masking hides irrelevant tools dynamically.

    Tests verify:
    - Tools are filtered based on current phase
    - Filtering happens at list_tools level (reduced action space)
    - Blocked tools return structured error with phase context
    """

    def test_tools_filtered_by_phase(self):
        """Tools visible depend on current ritual phase."""
        # AGENCY-01: Verify tool filtering changes with phase
        tracker = RitualPhaseTracker()

        # Briefing phase - limited tools
        briefing_tools = tracker.get_visible_tools("/test")
        assert "get_briefing" in briefing_tools
        assert "remember" not in briefing_tools
        assert "execute_python" not in briefing_tools

        # Transition to action phase
        tracker.on_tool_called("/test", "remember")
        action_tools = tracker.get_visible_tools("/test")
        assert "remember" in action_tools
        assert "execute_python" in action_tools

    def test_filtering_reduces_action_space(self):
        """Phase filtering reduces action space entropy."""
        # AGENCY-01: Verify filtering reduces available tools
        tracker = RitualPhaseTracker()

        # Count tools in each phase
        briefing_count = len(tracker.get_visible_tools("/test"))

        # Transition to exploration
        tracker.on_tool_called("/test", "context_check")
        exploration_count = len(tracker.get_visible_tools("/test"))

        # Transition to action
        tracker.on_tool_called("/test", "remember")
        action_count = len(tracker.get_visible_tools("/test"))

        # Each phase has different tool count - not monotonically increasing
        # (reflection has fewer tools than action)
        assert briefing_count > 0
        assert exploration_count > briefing_count  # Exploration expands
        assert action_count != exploration_count

    @pytest.mark.asyncio
    async def test_middleware_filters_tool_list(self):
        """Middleware filters tool list based on phase."""
        # AGENCY-01: Verify on_list_tools filtering
        tracker = RitualPhaseTracker()
        middleware = AgencyMiddleware(tracker.get_phase)

        # Mock tools
        mock_tools = [
            MagicMock(name="get_briefing"),
            MagicMock(name="remember"),
            MagicMock(name="execute_python"),
        ]
        for tool in mock_tools:
            tool.name = tool._mock_name

        # Context with project path
        context = MagicMock()
        context.message = MagicMock()
        context.message.arguments = {"project_path": "/test"}

        async def mock_call_next(ctx):
            return mock_tools

        # In briefing phase
        filtered = await middleware.on_list_tools(context, mock_call_next)
        filtered_names = {t.name for t in filtered}

        # Only briefing tools visible
        assert "get_briefing" in filtered_names
        assert "remember" not in filtered_names
        assert "execute_python" not in filtered_names

    @pytest.mark.asyncio
    async def test_middleware_blocks_hidden_tools(self):
        """Middleware blocks calls to tools not visible in current phase."""
        # AGENCY-01: Verify blocked tools return structured error
        tracker = RitualPhaseTracker()
        middleware = AgencyMiddleware(tracker.get_phase)

        # Context for action tool in briefing phase
        context = MagicMock()
        context.message = MagicMock()
        context.message.name = "remember"
        context.message.arguments = {"project_path": "/test"}

        call_next = AsyncMock()

        result = await middleware.on_call_tool(context, call_next)

        # Should be blocked - remember not in briefing phase
        # Check result has violation info (adapts to ToolResult or dict)
        if hasattr(result, "structured_content"):
            violation = result.structured_content
        else:
            violation = result

        assert violation["status"] == "blocked"
        assert violation["violation"] == "TOOL_NOT_VISIBLE"
        assert "available_tools" in violation
        assert "hint" in violation

    @pytest.mark.asyncio
    async def test_blocked_response_includes_available_tools(self):
        """Blocked tool response lists available tools for guidance."""
        # AGENCY-01: Verify helpful error with available tools
        tracker = RitualPhaseTracker()
        middleware = AgencyMiddleware(tracker.get_phase)

        context = MagicMock()
        context.message = MagicMock()
        context.message.name = "execute_python"
        context.message.arguments = {"project_path": "/test"}

        result = await middleware.on_call_tool(context, AsyncMock())

        if hasattr(result, "structured_content"):
            violation = result.structured_content
        else:
            violation = result

        # Available tools should be listed
        assert isinstance(violation["available_tools"], list)
        assert "get_briefing" in violation["available_tools"]


# ============================================================================
# AGENCY-02: Tool visibility determined by current ritual phase (focus/domain)
# ============================================================================


class TestAgency02_PhaseBasedVisibility:
    """
    AGENCY-02: Tool visibility determined by current ritual phase (focus/domain).

    Tests verify:
    - Each phase has appropriate tool set
    - Phase transitions change visibility
    - Tool categorization matches Sacred Covenant flow
    """

    def test_briefing_phase_tools(self):
        """Briefing phase shows only entry and query tools."""
        # AGENCY-02: Verify briefing tool set
        briefing_tools = PHASE_TOOL_VISIBILITY["briefing"]
        assert "get_briefing" in briefing_tools
        assert "health" in briefing_tools
        assert "recall" in briefing_tools
        # No mutations
        assert "remember" not in briefing_tools
        assert "add_rule" not in briefing_tools
        assert "execute_python" not in briefing_tools

    def test_exploration_phase_tools(self):
        """Exploration phase shows read/search tools."""
        # AGENCY-02: Verify exploration tool set
        exploration_tools = PHASE_TOOL_VISIBILITY["exploration"]
        assert "context_check" in exploration_tools
        assert "search_memories" in exploration_tools
        assert "find_related" in exploration_tools
        assert "recall_hierarchical" in exploration_tools
        assert "find_code" in exploration_tools
        assert "analyze_impact" in exploration_tools
        # No mutations
        assert "remember" not in exploration_tools
        assert "execute_python" not in exploration_tools

    def test_action_phase_tools(self):
        """Action phase shows mutation tools including execute_python."""
        # AGENCY-02: Verify action tool set
        action_tools = PHASE_TOOL_VISIBILITY["action"]
        assert "remember" in action_tools
        assert "remember_batch" in action_tools
        assert "add_rule" in action_tools
        assert "execute_python" in action_tools
        assert "link_memories" in action_tools
        assert "pin_memory" in action_tools

    def test_reflection_phase_tools(self):
        """Reflection phase shows verification and compression tools."""
        # AGENCY-02: Verify reflection tool set
        reflection_tools = PHASE_TOOL_VISIBILITY["reflection"]
        assert "verify_facts" in reflection_tools
        assert "compress_context" in reflection_tools
        assert "record_outcome" in reflection_tools
        # No heavy mutations
        assert "remember" not in reflection_tools
        assert "execute_python" not in reflection_tools

    def test_phase_transitions_change_visibility(self):
        """Phase transitions update which tools are visible."""
        # AGENCY-02: Verify transitions change tool visibility
        tracker = RitualPhaseTracker()

        # Start in briefing
        assert tracker.get_phase("/test") == "briefing"
        tools1 = tracker.get_visible_tools("/test")

        # Transition to exploration
        tracker.on_tool_called("/test", "context_check")
        assert tracker.get_phase("/test") == "exploration"
        tools2 = tracker.get_visible_tools("/test")

        # Different tool sets
        assert tools1 != tools2
        assert "search_memories" in tools2
        assert "search_memories" not in tools1

    def test_core_tools_always_available(self):
        """Core tools (get_briefing, health, recall) available in all phases."""
        # AGENCY-02: Verify core tools in all phases
        core_tools = {"get_briefing", "health", "recall"}

        for phase_name, tools in PHASE_TOOL_VISIBILITY.items():
            for core in core_tools:
                assert core in tools, f"{core} missing from {phase_name}"

    def test_ritual_phase_enum_values(self):
        """RitualPhase enum has correct values."""
        # AGENCY-02: Verify phase enum
        assert RitualPhase.BRIEFING.value == "briefing"
        assert RitualPhase.EXPLORATION.value == "exploration"
        assert RitualPhase.ACTION.value == "action"
        assert RitualPhase.REFLECTION.value == "reflection"

    def test_phase_tracker_default_is_briefing(self):
        """New projects start in briefing phase."""
        # AGENCY-02: Verify default phase
        tracker = RitualPhaseTracker()
        assert tracker.get_phase("/new/project") == "briefing"
        assert tracker.get_phase_enum("/new/project") == RitualPhase.BRIEFING


# ============================================================================
# AGENCY-03: execute_python tool provides sandboxed code execution
# ============================================================================


class TestAgency03_SandboxedExecution:
    """
    AGENCY-03: execute_python tool provides sandboxed code execution.

    Tests verify:
    - SandboxExecutor exists and is importable
    - ExecutionResult has required fields
    - Graceful degradation when unavailable
    """

    def test_sandbox_executor_exists(self):
        """SandboxExecutor class exists and is importable."""
        # AGENCY-03: Verify SandboxExecutor available
        executor = SandboxExecutor()
        assert executor is not None

    def test_execution_result_structure(self):
        """ExecutionResult has required fields."""
        # AGENCY-03: Verify result dataclass structure
        result = ExecutionResult(
            success=True,
            output="hello",
            error=None,
            execution_time_ms=100,
            logs=["log1"],
        )
        assert result.success is True
        assert result.output == "hello"
        assert result.error is None
        assert result.execution_time_ms == 100
        assert result.logs == ["log1"]

    def test_execution_result_defaults(self):
        """ExecutionResult has sensible defaults."""
        # AGENCY-03: Verify defaults
        result = ExecutionResult(success=False, output="")
        assert result.error is None
        assert result.execution_time_ms == 0
        assert result.logs == []

    @pytest.mark.asyncio
    async def test_unavailable_returns_error(self):
        """When sandbox unavailable, returns error (not exception)."""
        # AGENCY-03: Verify graceful degradation
        executor = SandboxExecutor()
        executor._sandbox_available = False

        result = await executor.execute("print('test')")

        assert result.success is False
        assert "not available" in result.error.lower()

    def test_sandbox_available_property(self):
        """Sandbox has available property for runtime check."""
        # AGENCY-03: Verify availability check
        executor = SandboxExecutor()
        assert isinstance(executor.available, bool)

    @pytest.mark.asyncio
    async def test_execute_returns_execution_result(self):
        """execute() always returns ExecutionResult."""
        # AGENCY-03: Verify return type
        executor = SandboxExecutor()
        executor._sandbox_available = False

        result = await executor.execute("any code")
        assert isinstance(result, ExecutionResult)


# ============================================================================
# AGENCY-04: Sandbox isolation via Firecracker microVMs (E2B)
# ============================================================================


class TestAgency04_SandboxIsolation:
    """
    AGENCY-04: Sandbox isolation via rootless container or Wasm (E2B).

    Tests verify:
    - Sandbox implementation uses E2B Code Interpreter
    - Timeout enforcement
    - No host access
    """

    def test_sandbox_uses_e2b(self):
        """Sandbox implementation uses E2B Code Interpreter."""
        # AGENCY-04: Verify E2B integration
        import daem0nmcp.agency.sandbox as sandbox_module

        source = inspect.getsource(sandbox_module)
        assert "e2b_code_interpreter" in source
        assert "Sandbox" in source

    def test_sandbox_timeout_configurable(self):
        """Sandbox timeout is configurable."""
        # AGENCY-04: Verify timeout configuration
        executor = SandboxExecutor(timeout_seconds=60)
        assert executor.timeout_seconds == 60

        executor2 = SandboxExecutor(timeout_seconds=10)
        assert executor2.timeout_seconds == 10

    def test_default_timeout(self):
        """Default timeout is reasonable."""
        # AGENCY-04: Verify default timeout
        executor = SandboxExecutor()
        assert executor.timeout_seconds == 30

    @pytest.mark.asyncio
    async def test_timeout_passed_to_execution(self):
        """Timeout is passed to E2B execution."""
        # AGENCY-04: Verify timeout enforcement
        mock_execution = MagicMock()
        mock_execution.text = "ok"
        mock_execution.logs = []
        mock_execution.error = None

        mock_sandbox = MagicMock()
        mock_sandbox.run_code.return_value = mock_execution
        mock_sandbox.__enter__ = MagicMock(return_value=mock_sandbox)
        mock_sandbox.__exit__ = MagicMock(return_value=False)

        mock_sandbox_class = MagicMock(return_value=mock_sandbox)
        mock_module = MagicMock()
        mock_module.Sandbox = mock_sandbox_class

        with patch.dict("sys.modules", {"e2b_code_interpreter": mock_module}):
            executor = SandboxExecutor(api_key="test-key", timeout_seconds=45)
            executor._sandbox_available = True

            await executor.execute("print('test')")

        # Verify timeout was passed
        mock_sandbox.run_code.assert_called_once_with("print('test')", timeout=45)

    def test_api_key_required_for_availability(self):
        """Sandbox requires API key to be available."""
        # AGENCY-04: Verify API key requirement
        # Clear environment
        env_copy = os.environ.copy()
        env_copy.pop("E2B_API_KEY", None)

        with patch.dict(os.environ, env_copy, clear=True):
            executor = SandboxExecutor()
            assert not executor.available

    @pytest.mark.skipif(
        not os.environ.get("E2B_API_KEY"),
        reason="E2B_API_KEY not set",
    )
    @pytest.mark.asyncio
    async def test_sandbox_isolation_live(self):
        """Live test: sandbox cannot access host environment."""
        # AGENCY-04: Live isolation test
        os.environ["TEST_SECRET_VALUE"] = "should_not_be_visible"

        executor = SandboxExecutor()
        result = await executor.execute(
            "import os; print(os.environ.get('TEST_SECRET_VALUE', 'NOT_FOUND'))"
        )

        assert result.success
        assert "NOT_FOUND" in result.output


# ============================================================================
# AGENCY-05: Capability-scoped access enforces least-privilege
# ============================================================================


class TestAgency05_CapabilityScopedAccess:
    """
    AGENCY-05: Capability-scoped access enforces least-privilege.

    Tests verify:
    - Default capabilities granted
    - Capabilities can be revoked
    - check_capability returns violation when denied
    - Per-project capability tracking
    """

    def test_default_capabilities_granted(self):
        """Default capabilities include EXECUTE_CODE."""
        # AGENCY-05: Verify default capabilities
        manager = CapabilityManager()
        assert manager.has_capability("/test", CapabilityScope.EXECUTE_CODE)

    def test_capability_can_be_revoked(self):
        """Capabilities can be revoked per project."""
        # AGENCY-05: Verify revocation
        manager = CapabilityManager()
        manager.revoke_capability("/test", CapabilityScope.EXECUTE_CODE)
        assert not manager.has_capability("/test", CapabilityScope.EXECUTE_CODE)

    def test_capability_can_be_granted(self):
        """Capabilities can be granted per project."""
        # AGENCY-05: Verify granting
        manager = CapabilityManager()
        manager.revoke_capability("/test", CapabilityScope.EXECUTE_CODE)
        assert not manager.has_capability("/test", CapabilityScope.EXECUTE_CODE)

        manager.grant_capability("/test", CapabilityScope.EXECUTE_CODE)
        assert manager.has_capability("/test", CapabilityScope.EXECUTE_CODE)

    def test_revoked_capability_blocks_check(self):
        """check_capability returns violation when capability revoked."""
        # AGENCY-05: Verify check_capability behavior
        manager = CapabilityManager()
        manager.revoke_capability("/test", CapabilityScope.EXECUTE_CODE)

        violation = check_capability("/test", CapabilityScope.EXECUTE_CODE, manager)

        assert violation is not None
        assert violation["violation"] == "CAPABILITY_DENIED"
        assert violation["required_capability"] == "EXECUTE_CODE"

    def test_granted_capability_passes_check(self):
        """check_capability returns None when capability granted."""
        # AGENCY-05: Verify successful check
        manager = CapabilityManager()

        violation = check_capability("/test", CapabilityScope.EXECUTE_CODE, manager)

        assert violation is None

    def test_different_projects_independent(self):
        """Capabilities are tracked per project."""
        # AGENCY-05: Verify project isolation
        manager = CapabilityManager()
        manager.revoke_capability("/project1", CapabilityScope.EXECUTE_CODE)

        # Project 1 blocked
        assert not manager.has_capability("/project1", CapabilityScope.EXECUTE_CODE)
        # Project 2 still has default
        assert manager.has_capability("/project2", CapabilityScope.EXECUTE_CODE)

    def test_capability_scope_enum_values(self):
        """CapabilityScope enum has expected values."""
        # AGENCY-05: Verify capability scopes
        assert CapabilityScope.EXECUTE_CODE is not None
        assert CapabilityScope.NETWORK_ACCESS is not None
        assert CapabilityScope.FILE_WRITE is not None

    def test_reset_capabilities(self):
        """reset_capabilities restores defaults."""
        # AGENCY-05: Verify reset
        manager = CapabilityManager()
        manager.revoke_capability("/test", CapabilityScope.EXECUTE_CODE)
        assert not manager.has_capability("/test", CapabilityScope.EXECUTE_CODE)

        manager.reset_capabilities("/test")
        assert manager.has_capability("/test", CapabilityScope.EXECUTE_CODE)

    def test_check_capability_without_manager(self):
        """check_capability allows when no manager provided."""
        # AGENCY-05: Backwards compatibility
        violation = check_capability("/test", CapabilityScope.EXECUTE_CODE, None)
        assert violation is None


# ============================================================================
# Full Integration Tests
# ============================================================================


class TestAgencyIntegration:
    """
    Full integration tests for Phase 5 Dynamic Agency.

    Tests verify end-to-end flows across all AGENCY requirements.
    """

    def test_all_tools_mapped_to_phases(self):
        """All key tools should be in at least one phase."""
        # Integration: Verify tool mapping coverage
        all_phase_tools = set()
        for tools in PHASE_TOOL_VISIBILITY.values():
            all_phase_tools.update(tools)

        # Check key tools are mapped
        expected_tools = [
            "get_briefing",
            "recall",
            "remember",
            "verify_facts",
            "compress_context",
            "execute_python",
            "context_check",
            "health",
            "add_rule",
            "record_outcome",
        ]
        for tool in expected_tools:
            assert tool in all_phase_tools, f"{tool} not mapped to any phase"

    def test_execute_python_only_in_action_phase(self):
        """execute_python should only be visible in action phase."""
        # Integration: Verify execute_python restriction
        for phase, tools in PHASE_TOOL_VISIBILITY.items():
            if phase == "action":
                assert "execute_python" in tools
            else:
                assert (
                    "execute_python" not in tools
                ), f"execute_python in {phase} phase"

    def test_full_ritual_flow(self):
        """Test complete ritual phase flow."""
        # Integration: Full flow test
        tracker = RitualPhaseTracker()

        # Start: briefing
        assert tracker.get_phase("/test") == "briefing"

        # Commune with daemon
        tracker.on_tool_called("/test", "get_briefing")
        assert tracker.get_phase("/test") == "briefing"

        # Seek counsel
        tracker.on_tool_called("/test", "context_check")
        assert tracker.get_phase("/test") == "exploration"

        # Take action
        tracker.on_tool_called("/test", "remember")
        assert tracker.get_phase("/test") == "action"

        # Reflect
        tracker.on_tool_called("/test", "record_outcome")
        assert tracker.get_phase("/test") == "reflection"

    def test_multi_project_isolation(self):
        """Different projects have independent phase tracking."""
        # Integration: Project isolation test
        tracker = RitualPhaseTracker()

        # Project 1 in action
        tracker.on_tool_called("/project1", "remember")
        # Project 2 starts fresh
        assert tracker.get_phase("/project1") == "action"
        assert tracker.get_phase("/project2") == "briefing"

    def test_phase_and_capability_combined(self):
        """Phase visibility and capability scoping work together."""
        # Integration: Combined AGENCY-02 + AGENCY-05
        tracker = RitualPhaseTracker()
        cap_manager = CapabilityManager()

        # Move to action phase
        tracker.on_tool_called("/test", "remember")
        assert tracker.get_phase("/test") == "action"

        # execute_python visible in action
        tools = tracker.get_visible_tools("/test")
        assert "execute_python" in tools

        # But capability can be revoked
        cap_manager.revoke_capability("/test", CapabilityScope.EXECUTE_CODE)
        violation = check_capability("/test", CapabilityScope.EXECUTE_CODE, cap_manager)
        assert violation is not None
        assert violation["violation"] == "CAPABILITY_DENIED"

    @pytest.mark.asyncio
    async def test_middleware_and_tracker_integration(self):
        """Middleware uses tracker phases correctly."""
        # Integration: AGENCY-01 + AGENCY-02
        tracker = RitualPhaseTracker()
        middleware = AgencyMiddleware(tracker.get_phase)

        # Mock tools
        mock_tools = [
            MagicMock(name="get_briefing"),
            MagicMock(name="remember"),
            MagicMock(name="execute_python"),
        ]
        for t in mock_tools:
            t.name = t._mock_name

        context = MagicMock()
        context.message = MagicMock()
        context.message.arguments = {"project_path": "/test"}

        async def mock_call_next(ctx):
            return mock_tools

        # Phase 1: briefing
        filtered = await middleware.on_list_tools(context, mock_call_next)
        assert len(filtered) == 1  # Only get_briefing

        # Transition to action
        tracker.on_tool_called("/test", "remember")

        # Phase 2: action - more tools visible
        filtered = await middleware.on_list_tools(context, mock_call_next)
        assert len(filtered) == 3  # All three tools


# ============================================================================
# Security Logging Tests
# ============================================================================


class TestSecurityLogging:
    """Verify security logging for anomaly detection."""

    def test_sandbox_logs_unavailable(self, caplog):
        """SandboxExecutor logs when unavailable."""
        # Security logging for availability
        caplog.set_level(logging.WARNING)

        # Force unavailable by clearing API key
        env_copy = os.environ.copy()
        env_copy.pop("E2B_API_KEY", None)

        with patch.dict(os.environ, env_copy, clear=True):
            _ = SandboxExecutor()

        # Should log warning about unavailability (could be API key or package)
        assert any(
            "unavailable" in record.message.lower() or "not set" in record.message.lower()
            for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_sandbox_logs_execution(self, caplog):
        """SandboxExecutor logs execution attempts."""
        # Security logging for execution
        caplog.set_level(logging.INFO)

        mock_execution = MagicMock()
        mock_execution.text = "result"
        mock_execution.logs = []
        mock_execution.error = None

        mock_sandbox = MagicMock()
        mock_sandbox.run_code.return_value = mock_execution
        mock_sandbox.__enter__ = MagicMock(return_value=mock_sandbox)
        mock_sandbox.__exit__ = MagicMock(return_value=False)

        mock_sandbox_class = MagicMock(return_value=mock_sandbox)
        mock_module = MagicMock()
        mock_module.Sandbox = mock_sandbox_class

        with patch.dict("sys.modules", {"e2b_code_interpreter": mock_module}):
            executor = SandboxExecutor(api_key="test-key")
            executor._sandbox_available = True

            await executor.execute("print('test')")

        # Should log execution info
        assert any(
            "execution" in record.message.lower() for record in caplog.records
        )

    def test_capability_logs_grant(self, caplog):
        """CapabilityManager logs capability grants."""
        caplog.set_level(logging.INFO)

        manager = CapabilityManager()
        manager.grant_capability("/test", CapabilityScope.NETWORK_ACCESS)

        assert any(
            "granted" in record.message.lower() for record in caplog.records
        )

    def test_capability_logs_revoke(self, caplog):
        """CapabilityManager logs capability revocations."""
        caplog.set_level(logging.INFO)

        manager = CapabilityManager()
        manager.revoke_capability("/test", CapabilityScope.EXECUTE_CODE)

        assert any(
            "revoked" in record.message.lower() for record in caplog.records
        )


# ============================================================================
# Edge Case Tests
# ============================================================================


class TestAgencyEdgeCases:
    """Edge case tests for robustness."""

    def test_tracker_handles_unknown_tools(self):
        """Tracker ignores unknown tools for phase transitions."""
        tracker = RitualPhaseTracker()

        # Call unknown tool
        tracker.on_tool_called("/test", "unknown_tool_xyz")

        # Should remain in briefing (no transition)
        assert tracker.get_phase("/test") == "briefing"

    def test_tracker_clear_project(self):
        """Tracker can clear all state for a project."""
        tracker = RitualPhaseTracker()

        # Set state
        tracker.on_tool_called("/test", "remember")
        assert tracker.get_phase("/test") == "action"

        # Clear
        tracker.clear_project("/test")

        # Back to default
        assert tracker.get_phase("/test") == "briefing"

    def test_tracker_reset_phase(self):
        """Tracker can reset phase to briefing."""
        tracker = RitualPhaseTracker()

        tracker.on_tool_called("/test", "remember")
        assert tracker.get_phase("/test") == "action"

        tracker.reset_phase("/test")
        assert tracker.get_phase("/test") == "briefing"

    def test_tracker_last_activity(self):
        """Tracker records last activity timestamp."""
        tracker = RitualPhaseTracker()

        # No activity yet
        assert tracker.get_last_activity("/test") is None

        # Call a tool
        tracker.on_tool_called("/test", "get_briefing")

        # Now has activity
        assert tracker.get_last_activity("/test") is not None

    def test_capability_manager_get_capabilities(self):
        """CapabilityManager returns capability set."""
        manager = CapabilityManager()

        caps = manager.get_capabilities("/test")

        assert isinstance(caps, set)
        assert CapabilityScope.EXECUTE_CODE in caps

    def test_execution_result_with_all_fields(self):
        """ExecutionResult works with all fields populated."""
        result = ExecutionResult(
            success=True,
            output="Hello\nWorld",
            error=None,
            execution_time_ms=1500,
            logs=["Log 1", "Log 2", "Log 3"],
        )

        assert result.success
        assert "World" in result.output
        assert result.execution_time_ms == 1500
        assert len(result.logs) == 3
