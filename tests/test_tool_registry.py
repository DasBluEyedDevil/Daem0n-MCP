# tests/test_tool_registry.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from devilmcp.tool_registry import ToolRegistry, ToolConfig, ToolCapability
from devilmcp.executor import ExecutionResult
from devilmcp.subprocess_executor import SubprocessExecutor

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.get_session = MagicMock(return_value=AsyncMock())
    return db

@pytest.fixture
def sample_tool_config():
    return ToolConfig(
        name="echo",
        display_name="Echo",
        command="echo",
        args=[],
        capabilities=[],
        enabled=True,
        config={},
        prompt_patterns=[],
        init_timeout=5000,
        command_timeout=10000,
        max_context_size=None,
        supports_streaming=False
    )

@pytest.mark.asyncio
async def test_get_executor_returns_subprocess_by_default(mock_db, sample_tool_config):
    registry = ToolRegistry(mock_db)
    registry._tools_cache["echo"] = sample_tool_config

    executor = await registry.get_executor("echo")

    assert isinstance(executor, SubprocessExecutor)

@pytest.mark.asyncio
async def test_get_executor_caches_executors(mock_db, sample_tool_config):
    registry = ToolRegistry(mock_db)
    registry._tools_cache["echo"] = sample_tool_config

    executor1 = await registry.get_executor("echo")
    executor2 = await registry.get_executor("echo")

    assert executor1 is executor2  # Same instance

@pytest.mark.asyncio
async def test_execute_tool_routes_correctly(mock_db, sample_tool_config):
    registry = ToolRegistry(mock_db)
    registry._tools_cache["echo"] = sample_tool_config

    result = await registry.execute_tool("echo", "echo", ["hello"])

    assert result.success is True
    assert "hello" in result.output

@pytest.mark.asyncio
async def test_execute_tool_unknown_tool(mock_db):
    registry = ToolRegistry(mock_db)

    result = await registry.execute_tool("nonexistent", "test", [])

    assert result.success is False
    assert "not found" in result.error.lower()
