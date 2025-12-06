# tests/test_integration.py
"""
Integration tests for the tool execution system.

Simplified to match the de-bloated architecture.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_full_tool_execution_flow():
    """Test the complete flow from ToolRegistry to execution."""
    from devilmcp.tool_registry import ToolRegistry, ToolConfig

    mock_db = MagicMock()
    mock_db.get_session = MagicMock(return_value=AsyncMock())

    registry = ToolRegistry(mock_db)

    # Register a test tool directly in cache
    registry._tools_cache["test-echo"] = ToolConfig(
        name="test-echo",
        display_name="Test Echo",
        command="echo",
        args=[],
        capabilities=[],
        enabled=True,
        config={},
        command_timeout=10000
    )

    result = await registry.execute_tool("test-echo", "integration", ["test"])

    assert result.success is True
    assert "integration" in result.output or "test" in result.output


@pytest.mark.asyncio
async def test_subprocess_executor_stateless():
    """Test SubprocessExecutor with echo command."""
    from devilmcp.subprocess_executor import SubprocessExecutor
    from devilmcp.tool_registry import ToolConfig

    config = ToolConfig(
        name="echo-test",
        display_name="Echo Test",
        command="echo",
        args=[],
        capabilities=[],
        enabled=True,
        config={},
        command_timeout=10000
    )

    executor = SubprocessExecutor(config)

    result1 = await executor.execute("first", ["execution"])
    assert result1.success is True
    assert "first" in result1.output

    result2 = await executor.execute("second", ["execution"])
    assert result2.success is True
    assert "second" in result2.output

    await executor.cleanup()


@pytest.mark.asyncio
async def test_error_handling_for_unknown_tool():
    """Test that executing an unknown tool returns a proper error."""
    from devilmcp.tool_registry import ToolRegistry

    mock_db = MagicMock()
    mock_db.get_session = MagicMock(return_value=AsyncMock())

    registry = ToolRegistry(mock_db)

    result = await registry.execute_tool("nonexistent-tool", "test", [])

    assert result.success is False
    assert "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_execution_result_contains_all_expected_fields():
    """Test that ExecutionResult from real execution has all expected fields."""
    from devilmcp.tool_registry import ToolRegistry, ToolConfig

    mock_db = MagicMock()
    mock_db.get_session = MagicMock(return_value=AsyncMock())

    registry = ToolRegistry(mock_db)

    registry._tools_cache["echo"] = ToolConfig(
        name="echo",
        display_name="Echo",
        command="echo",
        args=[],
        capabilities=[],
        enabled=True,
        config={},
        command_timeout=10000
    )

    result = await registry.execute_tool("echo", "test", [])

    assert hasattr(result, 'success')
    assert hasattr(result, 'output')
    assert hasattr(result, 'error')
    assert hasattr(result, 'return_code')
    assert hasattr(result, 'timed_out')

    assert result.success is True
    assert result.timed_out is False


@pytest.mark.asyncio
async def test_subprocess_executor_handles_command_failure():
    """Test that SubprocessExecutor properly handles command failures."""
    from devilmcp.subprocess_executor import SubprocessExecutor
    from devilmcp.tool_registry import ToolConfig

    config = ToolConfig(
        name="python-test",
        display_name="Python Test",
        command="python",
        args=["-c"],
        capabilities=[],
        enabled=True,
        config={},
        command_timeout=10000
    )

    executor = SubprocessExecutor(config)

    result = await executor.execute("exit(42)", [])

    assert result.success is False
    assert result.return_code == 42

    await executor.cleanup()


@pytest.mark.asyncio
async def test_subprocess_executor_handles_missing_command():
    """Test that SubprocessExecutor handles missing commands gracefully."""
    from devilmcp.subprocess_executor import SubprocessExecutor
    from devilmcp.tool_registry import ToolConfig

    config = ToolConfig(
        name="nonexistent",
        display_name="Nonexistent",
        command="definitely-not-a-real-command-12345",
        args=[],
        capabilities=[],
        enabled=True,
        config={},
        command_timeout=10000
    )

    executor = SubprocessExecutor(config)

    result = await executor.execute("test", [])

    assert result.success is False
    assert "not found" in result.error.lower()

    await executor.cleanup()
