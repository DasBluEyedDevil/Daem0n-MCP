# tests/test_subprocess_executor.py
import pytest
from unittest.mock import MagicMock
from devilmcp.subprocess_executor import SubprocessExecutor
from devilmcp.tool_registry import ToolConfig, ToolCapability

@pytest.fixture
def stateless_config():
    """Config without prompt_patterns = stateless mode."""
    return ToolConfig(
        name="echo-test",
        display_name="Echo Test",
        command="echo",
        args=[],
        capabilities=[],
        enabled=True,
        config={},
        prompt_patterns=[],  # Empty = stateless
        init_timeout=5000,
        command_timeout=10000,
        max_context_size=None,
        supports_streaming=False
    )

@pytest.mark.asyncio
async def test_stateless_executor_echo(stateless_config):
    executor = SubprocessExecutor(stateless_config)
    result = await executor.execute("echo", ["hello", "world"])

    assert result.success is True
    assert "hello world" in result.output
    assert result.executor_type == "subprocess-stateless"
    assert result.timed_out is False

    await executor.cleanup()

@pytest.mark.asyncio
async def test_stateless_executor_returns_exit_code(stateless_config):
    executor = SubprocessExecutor(stateless_config)
    # Run a command that fails
    result = await executor.execute("python", ["-c", "exit(42)"])

    assert result.success is False
    assert result.return_code == 42

    await executor.cleanup()

@pytest.mark.asyncio
async def test_stateless_executor_captures_stderr(stateless_config):
    executor = SubprocessExecutor(stateless_config)
    result = await executor.execute("python", ["-c", "import sys; sys.stderr.write('error msg')"])

    assert "error msg" in result.error or "error msg" in result.output

    await executor.cleanup()

@pytest.fixture
def stateful_config():
    """Config with prompt_patterns = stateful mode."""
    return ToolConfig(
        name="python-repl",
        display_name="Python REPL",
        command="python",
        args=["-i"],
        capabilities=[],
        enabled=True,
        config={},
        prompt_patterns=[">>> "],  # Has patterns = stateful
        init_timeout=5000,
        command_timeout=10000,
        max_context_size=None,
        supports_streaming=False
    )

@pytest.mark.asyncio
async def test_stateful_executor_python_repl(stateful_config):
    executor = SubprocessExecutor(stateful_config)

    # First command
    result = await executor.execute("print('hello')", [])
    assert "hello" in result.output
    assert result.executor_type == "subprocess-stateful"

    # Second command in same session
    result2 = await executor.execute("print('world')", [])
    assert "world" in result2.output

    await executor.cleanup()

@pytest.mark.asyncio
async def test_stateful_executor_maintains_state(stateful_config):
    executor = SubprocessExecutor(stateful_config)

    # Set a variable
    await executor.execute("x = 42", [])

    # Read it back
    result = await executor.execute("print(x)", [])
    assert "42" in result.output

    await executor.cleanup()

@pytest.mark.asyncio
async def test_stateful_executor_sentinel_not_in_output(stateful_config):
    executor = SubprocessExecutor(stateful_config)

    result = await executor.execute("print('test')", [])

    # Sentinel should be stripped from output
    assert "__DEVILMCP_END_" not in result.output

    await executor.cleanup()
