# tests/test_executor.py
import pytest
from devilmcp.executor import ExecutionResult


def test_execution_result_success():
    result = ExecutionResult(success=True, output="hello world")
    assert result.success is True
    assert result.output == "hello world"
    assert result.error is None
    assert result.return_code is None
    assert result.timed_out is False


def test_execution_result_failure():
    result = ExecutionResult(
        success=False,
        output="",
        error="Command not found",
        return_code=127,
        timed_out=False
    )
    assert result.success is False
    assert result.return_code == 127
    assert result.error == "Command not found"


def test_execution_result_timeout():
    result = ExecutionResult(
        success=False,
        output="partial output",
        error="Timeout",
        timed_out=True
    )
    assert result.timed_out is True
    assert result.output == "partial output"
