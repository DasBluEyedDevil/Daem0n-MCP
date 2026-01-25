"""
Tests for AgencyMiddleware - Phase-based tool visibility filtering.

Tests verify:
1. on_list_tools filtering - Correct tools shown per phase
2. on_call_tool blocking - Hidden tools return structured violation
3. Integration with RitualPhaseTracker - get_phase callback works
4. Edge cases - No project_path defaults to briefing
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Any, Dict, List, Optional


# ============================================================================
# Test AgencyMiddleware Import
# ============================================================================

@pytest.mark.asyncio
async def test_agency_middleware_exists():
    """Verify AgencyMiddleware can be imported."""
    from daem0nmcp.agency import AgencyMiddleware
    assert AgencyMiddleware is not None


@pytest.mark.asyncio
async def test_agency_middleware_init():
    """Verify AgencyMiddleware initializes with get_phase callback."""
    from daem0nmcp.agency import AgencyMiddleware

    def mock_get_phase(project_path: str) -> str:
        return "briefing"

    middleware = AgencyMiddleware(get_phase=mock_get_phase)
    assert middleware._get_phase == mock_get_phase


@pytest.mark.asyncio
async def test_agency_middleware_repr():
    """Verify AgencyMiddleware has useful repr."""
    from daem0nmcp.agency import AgencyMiddleware

    def mock_get_phase(project_path: str) -> str:
        return "briefing"

    middleware = AgencyMiddleware(get_phase=mock_get_phase)
    assert "AgencyMiddleware" in repr(middleware)
    assert "mock_get_phase" in repr(middleware)


# ============================================================================
# Test on_list_tools Filtering
# ============================================================================

class MockTool:
    """Mock tool object with name attribute."""
    def __init__(self, name: str):
        self.name = name


def create_mock_context(project_path: Optional[str] = None) -> MagicMock:
    """Create a mock MiddlewareContext with optional project_path."""
    context = MagicMock()
    context.message = MagicMock()
    context.message.arguments = {"project_path": project_path} if project_path else {}
    return context


def create_mock_tools() -> List[MockTool]:
    """Create a list of mock tools covering all phases."""
    return [
        # Briefing phase tools
        MockTool("get_briefing"),
        MockTool("health"),
        MockTool("recall"),
        MockTool("list_rules"),
        MockTool("get_graph"),
        # Exploration phase tools
        MockTool("context_check"),
        MockTool("recall_for_file"),
        MockTool("search_memories"),
        MockTool("find_related"),
        MockTool("check_rules"),
        MockTool("find_code"),
        MockTool("analyze_impact"),
        # Action phase tools
        MockTool("remember"),
        MockTool("remember_batch"),
        MockTool("add_rule"),
        MockTool("record_outcome"),
        MockTool("link_memories"),
        MockTool("execute_python"),
        # Reflection phase tools
        MockTool("verify_facts"),
        MockTool("compress_context"),
        # Tool not in any phase
        MockTool("unknown_tool"),
    ]


@pytest.mark.asyncio
async def test_on_list_tools_briefing_phase():
    """Briefing phase shows only briefing tools."""
    from daem0nmcp.agency import AgencyMiddleware, PHASE_TOOL_VISIBILITY

    def mock_get_phase(project_path: str) -> str:
        return "briefing"

    middleware = AgencyMiddleware(get_phase=mock_get_phase)

    context = create_mock_context(project_path="/test/project")
    all_tools = create_mock_tools()

    async def mock_call_next(ctx):
        return all_tools

    filtered = await middleware.on_list_tools(context, mock_call_next)

    # Check only briefing tools returned
    briefing_tools = PHASE_TOOL_VISIBILITY["briefing"]
    filtered_names = {tool.name for tool in filtered}

    assert filtered_names == briefing_tools
    assert "get_briefing" in filtered_names
    assert "health" in filtered_names
    assert "recall" in filtered_names
    # Action tools should be excluded
    assert "remember" not in filtered_names
    assert "execute_python" not in filtered_names


@pytest.mark.asyncio
async def test_on_list_tools_exploration_phase():
    """Exploration phase shows exploration tools."""
    from daem0nmcp.agency import AgencyMiddleware, PHASE_TOOL_VISIBILITY

    def mock_get_phase(project_path: str) -> str:
        return "exploration"

    middleware = AgencyMiddleware(get_phase=mock_get_phase)

    context = create_mock_context(project_path="/test/project")
    all_tools = create_mock_tools()

    async def mock_call_next(ctx):
        return all_tools

    filtered = await middleware.on_list_tools(context, mock_call_next)

    filtered_names = {tool.name for tool in filtered}

    # Exploration includes briefing tools plus more
    assert "get_briefing" in filtered_names
    assert "context_check" in filtered_names
    assert "recall_for_file" in filtered_names
    assert "find_code" in filtered_names
    # Action tools should be excluded
    assert "remember" not in filtered_names


@pytest.mark.asyncio
async def test_on_list_tools_action_phase():
    """Action phase shows action tools."""
    from daem0nmcp.agency import AgencyMiddleware, PHASE_TOOL_VISIBILITY

    def mock_get_phase(project_path: str) -> str:
        return "action"

    middleware = AgencyMiddleware(get_phase=mock_get_phase)

    context = create_mock_context(project_path="/test/project")
    all_tools = create_mock_tools()

    async def mock_call_next(ctx):
        return all_tools

    filtered = await middleware.on_list_tools(context, mock_call_next)

    filtered_names = {tool.name for tool in filtered}

    # Action includes mutation tools
    assert "remember" in filtered_names
    assert "remember_batch" in filtered_names
    assert "add_rule" in filtered_names
    assert "execute_python" in filtered_names
    # Exploration-only tools should be excluded
    assert "find_code" not in filtered_names


@pytest.mark.asyncio
async def test_on_list_tools_reflection_phase():
    """Reflection phase shows reflection tools."""
    from daem0nmcp.agency import AgencyMiddleware, PHASE_TOOL_VISIBILITY

    def mock_get_phase(project_path: str) -> str:
        return "reflection"

    middleware = AgencyMiddleware(get_phase=mock_get_phase)

    context = create_mock_context(project_path="/test/project")
    all_tools = create_mock_tools()

    async def mock_call_next(ctx):
        return all_tools

    filtered = await middleware.on_list_tools(context, mock_call_next)

    filtered_names = {tool.name for tool in filtered}

    # Reflection includes evaluation tools
    assert "verify_facts" in filtered_names
    assert "record_outcome" in filtered_names
    assert "compress_context" in filtered_names
    # Action tools should be excluded
    assert "remember" not in filtered_names
    assert "execute_python" not in filtered_names


@pytest.mark.asyncio
async def test_on_list_tools_no_project_path():
    """Without project_path, defaults to briefing phase."""
    from daem0nmcp.agency import AgencyMiddleware, PHASE_TOOL_VISIBILITY

    def mock_get_phase(project_path: str) -> str:
        # This should not be called when no project_path
        return "action"

    middleware = AgencyMiddleware(get_phase=mock_get_phase)

    # No project_path in context
    context = create_mock_context(project_path=None)
    all_tools = create_mock_tools()

    async def mock_call_next(ctx):
        return all_tools

    filtered = await middleware.on_list_tools(context, mock_call_next)

    # Should default to briefing tools
    briefing_tools = PHASE_TOOL_VISIBILITY["briefing"]
    filtered_names = {tool.name for tool in filtered}

    assert filtered_names == briefing_tools


# ============================================================================
# Test on_call_tool Blocking
# ============================================================================

@pytest.mark.asyncio
async def test_on_call_tool_allows_phase_visible():
    """Tool calls allowed in current phase should pass through."""
    from daem0nmcp.agency import AgencyMiddleware

    def mock_get_phase(project_path: str) -> str:
        return "action"

    middleware = AgencyMiddleware(get_phase=mock_get_phase)

    context = MagicMock()
    context.message = MagicMock()
    context.message.name = "remember"  # Allowed in action phase
    context.message.arguments = {"project_path": "/test/project"}

    expected_result = {"status": "success", "id": 123}

    async def mock_call_next(ctx):
        return expected_result

    result = await middleware.on_call_tool(context, mock_call_next)

    assert result == expected_result


@pytest.mark.asyncio
async def test_on_call_tool_blocks_hidden():
    """Tool calls not visible in current phase should be blocked."""
    from daem0nmcp.agency import AgencyMiddleware
    from daem0nmcp.agency.middleware import _FASTMCP_MIDDLEWARE_AVAILABLE

    def mock_get_phase(project_path: str) -> str:
        return "briefing"  # remember not visible in briefing

    middleware = AgencyMiddleware(get_phase=mock_get_phase)

    context = MagicMock()
    context.message = MagicMock()
    context.message.name = "remember"  # NOT allowed in briefing phase
    context.message.arguments = {"project_path": "/test/project"}

    async def mock_call_next(ctx):
        return {"status": "success", "id": 123}

    result = await middleware.on_call_tool(context, mock_call_next)

    # Should return a violation
    if _FASTMCP_MIDDLEWARE_AVAILABLE:
        # Result is a ToolResult with structured_content
        violation = result.structured_content
    else:
        # Direct dict return
        violation = result

    assert violation["status"] == "blocked"
    assert violation["violation"] == "TOOL_NOT_VISIBLE"
    assert violation["current_phase"] == "briefing"
    assert "remember" in violation["message"]
    assert "available_tools" in violation


@pytest.mark.asyncio
async def test_on_call_tool_includes_phase_hint():
    """Blocked tool response includes hint about correct phase."""
    from daem0nmcp.agency import AgencyMiddleware
    from daem0nmcp.agency.middleware import _FASTMCP_MIDDLEWARE_AVAILABLE

    def mock_get_phase(project_path: str) -> str:
        return "briefing"

    middleware = AgencyMiddleware(get_phase=mock_get_phase)

    context = MagicMock()
    context.message = MagicMock()
    context.message.name = "execute_python"  # Available in action phase
    context.message.arguments = {"project_path": "/test/project"}

    async def mock_call_next(ctx):
        return {"status": "success"}

    result = await middleware.on_call_tool(context, mock_call_next)

    if _FASTMCP_MIDDLEWARE_AVAILABLE:
        violation = result.structured_content
    else:
        violation = result

    # Should include hint about action phase
    assert "action" in violation["hint"]
    assert "execute_python" in violation["hint"]


@pytest.mark.asyncio
async def test_on_call_tool_no_project_path_allows():
    """Without project_path, tool call passes through."""
    from daem0nmcp.agency import AgencyMiddleware

    def mock_get_phase(project_path: str) -> str:
        return "briefing"

    middleware = AgencyMiddleware(get_phase=mock_get_phase)

    context = MagicMock()
    context.message = MagicMock()
    context.message.name = "remember"  # Would be blocked with project_path
    context.message.arguments = {}  # No project_path

    expected_result = {"status": "success", "id": 123}

    async def mock_call_next(ctx):
        return expected_result

    result = await middleware.on_call_tool(context, mock_call_next)

    # Should pass through without blocking
    assert result == expected_result


# ============================================================================
# Test Integration with RitualPhaseTracker
# ============================================================================

@pytest.mark.asyncio
async def test_integration_with_tracker():
    """AgencyMiddleware works with RitualPhaseTracker.get_phase."""
    from daem0nmcp.agency import AgencyMiddleware, RitualPhaseTracker, PHASE_TOOL_VISIBILITY

    tracker = RitualPhaseTracker()

    # Start in briefing
    assert tracker.get_phase("/test/project") == "briefing"

    middleware = AgencyMiddleware(get_phase=tracker.get_phase)

    context = create_mock_context(project_path="/test/project")
    all_tools = create_mock_tools()

    async def mock_call_next(ctx):
        return all_tools

    # Initially briefing phase - only briefing tools should pass through
    filtered = await middleware.on_list_tools(context, mock_call_next)
    briefing_names = {tool.name for tool in filtered}
    # All filtered tools must be in briefing phase
    assert briefing_names.issubset(PHASE_TOOL_VISIBILITY["briefing"])
    # Core briefing tools should be present
    assert "get_briefing" in briefing_names
    assert "recall" in briefing_names

    # Transition to exploration
    tracker.on_tool_called("/test/project", "context_check")
    assert tracker.get_phase("/test/project") == "exploration"

    filtered = await middleware.on_list_tools(context, mock_call_next)
    exploration_names = {tool.name for tool in filtered}
    # All filtered tools must be in exploration phase
    assert exploration_names.issubset(PHASE_TOOL_VISIBILITY["exploration"])
    # Exploration-specific tools should be present
    assert "context_check" in exploration_names
    assert "find_code" in exploration_names

    # Transition to action
    tracker.on_tool_called("/test/project", "remember")
    assert tracker.get_phase("/test/project") == "action"

    filtered = await middleware.on_list_tools(context, mock_call_next)
    action_names = {tool.name for tool in filtered}
    # All filtered tools must be in action phase
    assert action_names.issubset(PHASE_TOOL_VISIBILITY["action"])
    # Action-specific tools should be present
    assert "remember" in action_names
    assert "execute_python" in action_names


@pytest.mark.asyncio
async def test_integration_tracker_multiple_projects():
    """Middleware handles multiple projects with different phases."""
    from daem0nmcp.agency import AgencyMiddleware, RitualPhaseTracker, PHASE_TOOL_VISIBILITY

    tracker = RitualPhaseTracker()
    middleware = AgencyMiddleware(get_phase=tracker.get_phase)

    all_tools = create_mock_tools()

    async def mock_call_next(ctx):
        return all_tools

    # Project A in exploration
    tracker.on_tool_called("/project/a", "context_check")

    # Project B in action
    tracker.on_tool_called("/project/b", "remember")

    # Project C defaults to briefing

    # Check Project A - exploration phase
    context_a = create_mock_context(project_path="/project/a")
    filtered_a = await middleware.on_list_tools(context_a, mock_call_next)
    names_a = {t.name for t in filtered_a}
    assert names_a.issubset(PHASE_TOOL_VISIBILITY["exploration"])
    assert "context_check" in names_a  # Exploration-specific

    # Check Project B - action phase
    context_b = create_mock_context(project_path="/project/b")
    filtered_b = await middleware.on_list_tools(context_b, mock_call_next)
    names_b = {t.name for t in filtered_b}
    assert names_b.issubset(PHASE_TOOL_VISIBILITY["action"])
    assert "remember" in names_b  # Action-specific

    # Check Project C - default briefing
    context_c = create_mock_context(project_path="/project/c")
    filtered_c = await middleware.on_list_tools(context_c, mock_call_next)
    names_c = {t.name for t in filtered_c}
    assert names_c.issubset(PHASE_TOOL_VISIBILITY["briefing"])
    assert "get_briefing" in names_c  # Briefing-specific


# ============================================================================
# Test Edge Cases
# ============================================================================

@pytest.mark.asyncio
async def test_unknown_phase_defaults_to_briefing():
    """Unknown phase from get_phase defaults to briefing tools."""
    from daem0nmcp.agency import AgencyMiddleware, PHASE_TOOL_VISIBILITY

    def mock_get_phase(project_path: str) -> str:
        return "unknown_phase"  # Not in PHASE_TOOL_VISIBILITY

    middleware = AgencyMiddleware(get_phase=mock_get_phase)

    context = create_mock_context(project_path="/test/project")
    all_tools = create_mock_tools()

    async def mock_call_next(ctx):
        return all_tools

    filtered = await middleware.on_list_tools(context, mock_call_next)

    # Should default to briefing (all filtered tools in briefing set)
    filtered_names = {tool.name for tool in filtered}
    assert filtered_names.issubset(PHASE_TOOL_VISIBILITY["briefing"])
    assert "get_briefing" in filtered_names


@pytest.mark.asyncio
async def test_custom_extract_project_path():
    """Custom extract_project_path callback works."""
    from daem0nmcp.agency import AgencyMiddleware, PHASE_TOOL_VISIBILITY

    def mock_get_phase(project_path: str) -> str:
        if project_path == "/custom/path":
            return "action"
        return "briefing"

    def custom_extract(args: Dict[str, Any]) -> Optional[str]:
        # Extract from nested path
        return args.get("nested", {}).get("path")

    middleware = AgencyMiddleware(
        get_phase=mock_get_phase,
        extract_project_path=custom_extract,
    )

    # Context with nested project path
    context = MagicMock()
    context.message = MagicMock()
    context.message.arguments = {"nested": {"path": "/custom/path"}}

    all_tools = create_mock_tools()

    async def mock_call_next(ctx):
        return all_tools

    filtered = await middleware.on_list_tools(context, mock_call_next)

    # Should be action phase because of custom extraction
    filtered_names = {tool.name for tool in filtered}
    assert filtered_names.issubset(PHASE_TOOL_VISIBILITY["action"])
    # Action-specific tools should be present
    assert "remember" in filtered_names
    assert "execute_python" in filtered_names


@pytest.mark.asyncio
async def test_get_phase_hint_unknown_tool():
    """_get_phase_hint handles unknown tools."""
    from daem0nmcp.agency import AgencyMiddleware

    def mock_get_phase(project_path: str) -> str:
        return "briefing"

    middleware = AgencyMiddleware(get_phase=mock_get_phase)

    hint = middleware._get_phase_hint("briefing", "completely_unknown_tool")
    assert "not recognized" in hint


@pytest.mark.asyncio
async def test_get_phase_hint_known_tool():
    """_get_phase_hint finds the phase for known tools."""
    from daem0nmcp.agency import AgencyMiddleware

    def mock_get_phase(project_path: str) -> str:
        return "briefing"

    middleware = AgencyMiddleware(get_phase=mock_get_phase)

    # execute_python is in action phase
    hint = middleware._get_phase_hint("briefing", "execute_python")
    assert "action" in hint
    assert "execute_python" in hint


@pytest.mark.asyncio
async def test_empty_tools_list():
    """Middleware handles empty tool list gracefully."""
    from daem0nmcp.agency import AgencyMiddleware

    def mock_get_phase(project_path: str) -> str:
        return "briefing"

    middleware = AgencyMiddleware(get_phase=mock_get_phase)

    context = create_mock_context(project_path="/test/project")

    async def mock_call_next(ctx):
        return []  # No tools

    filtered = await middleware.on_list_tools(context, mock_call_next)

    assert filtered == []


@pytest.mark.asyncio
async def test_context_extraction_error():
    """Middleware handles errors in project_path extraction."""
    from daem0nmcp.agency import AgencyMiddleware, PHASE_TOOL_VISIBILITY

    def mock_get_phase(project_path: str) -> str:
        return "action"

    middleware = AgencyMiddleware(get_phase=mock_get_phase)

    # Create context that will cause extraction error
    context = MagicMock()
    context.message = MagicMock()
    context.message.arguments = None  # This will cause .get() to fail

    all_tools = create_mock_tools()

    async def mock_call_next(ctx):
        return all_tools

    # Should not raise, should default to briefing
    filtered = await middleware.on_list_tools(context, mock_call_next)

    # Should default to briefing due to extraction error
    briefing_tools = PHASE_TOOL_VISIBILITY["briefing"]
    filtered_names = {tool.name for tool in filtered}

    assert filtered_names == briefing_tools


# ============================================================================
# Test PHASE_TOOL_VISIBILITY Consistency
# ============================================================================

def test_phase_tool_visibility_has_all_phases():
    """PHASE_TOOL_VISIBILITY has all four phases."""
    from daem0nmcp.agency import PHASE_TOOL_VISIBILITY

    assert "briefing" in PHASE_TOOL_VISIBILITY
    assert "exploration" in PHASE_TOOL_VISIBILITY
    assert "action" in PHASE_TOOL_VISIBILITY
    assert "reflection" in PHASE_TOOL_VISIBILITY


def test_briefing_phase_tools():
    """Briefing phase has expected tools."""
    from daem0nmcp.agency import PHASE_TOOL_VISIBILITY

    briefing = PHASE_TOOL_VISIBILITY["briefing"]

    # Core briefing tools
    assert "get_briefing" in briefing
    assert "health" in briefing
    assert "recall" in briefing

    # Should NOT have mutation tools
    assert "remember" not in briefing
    assert "add_rule" not in briefing


def test_exploration_phase_tools():
    """Exploration phase has expected tools."""
    from daem0nmcp.agency import PHASE_TOOL_VISIBILITY

    exploration = PHASE_TOOL_VISIBILITY["exploration"]

    # Should include briefing tools
    assert "get_briefing" in exploration
    assert "recall" in exploration

    # Plus exploration-specific tools
    assert "context_check" in exploration
    assert "recall_for_file" in exploration
    assert "find_related" in exploration

    # Should NOT have mutation tools
    assert "remember" not in exploration


def test_action_phase_tools():
    """Action phase has expected mutation tools."""
    from daem0nmcp.agency import PHASE_TOOL_VISIBILITY

    action = PHASE_TOOL_VISIBILITY["action"]

    # Mutation tools
    assert "remember" in action
    assert "remember_batch" in action
    assert "add_rule" in action
    assert "execute_python" in action

    # Core tools still available
    assert "get_briefing" in action
    assert "recall" in action


def test_reflection_phase_tools():
    """Reflection phase has expected evaluation tools."""
    from daem0nmcp.agency import PHASE_TOOL_VISIBILITY

    reflection = PHASE_TOOL_VISIBILITY["reflection"]

    # Reflection tools
    assert "verify_facts" in reflection
    assert "record_outcome" in reflection
    assert "compress_context" in reflection

    # Core tools still available
    assert "get_briefing" in reflection
    assert "recall" in reflection

    # Should NOT have action tools
    assert "remember" not in reflection
    assert "execute_python" not in reflection


def test_get_briefing_available_in_all_phases():
    """get_briefing is available in all phases."""
    from daem0nmcp.agency import PHASE_TOOL_VISIBILITY

    for phase_name, tools in PHASE_TOOL_VISIBILITY.items():
        assert "get_briefing" in tools, f"get_briefing missing from {phase_name}"


def test_health_available_in_all_phases():
    """health is available in all phases."""
    from daem0nmcp.agency import PHASE_TOOL_VISIBILITY

    for phase_name, tools in PHASE_TOOL_VISIBILITY.items():
        assert "health" in tools, f"health missing from {phase_name}"
