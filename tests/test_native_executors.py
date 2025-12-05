# tests/test_native_executors.py
import pytest
import tempfile
import os
from pathlib import Path
from devilmcp.native_executors.git import GitNativeExecutor

@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary git repository."""
    import subprocess
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_path, capture_output=True)

    # Create a file and commit
    (repo_path / "test.txt").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_path, capture_output=True)

    return repo_path

@pytest.mark.asyncio
async def test_git_executor_status(git_repo):
    executor = GitNativeExecutor(str(git_repo))
    result = await executor.execute("status", [])

    assert result.success is True
    assert "nothing to commit" in result.output or "clean" in result.output
    assert result.executor_type == "native-git"

    await executor.cleanup()

@pytest.mark.asyncio
async def test_git_executor_log(git_repo):
    executor = GitNativeExecutor(str(git_repo))
    result = await executor.execute("log", ["--oneline", "-1"])

    assert result.success is True
    assert "initial" in result.output

    await executor.cleanup()

@pytest.mark.asyncio
async def test_git_executor_diff(git_repo):
    # Modify the file
    (git_repo / "test.txt").write_text("modified")

    executor = GitNativeExecutor(str(git_repo))
    result = await executor.execute("diff", [])

    assert result.success is True
    assert "modified" in result.output or "-hello" in result.output

    await executor.cleanup()

@pytest.mark.asyncio
async def test_git_executor_unsupported_command(git_repo):
    executor = GitNativeExecutor(str(git_repo))
    result = await executor.execute("unsupported-command", [])

    assert result.success is False
    assert "not supported" in result.error.lower() or "unsupported" in result.error.lower()

    await executor.cleanup()

def test_git_executor_supported_commands(git_repo):
    executor = GitNativeExecutor(str(git_repo))
    commands = executor.get_supported_commands()

    assert "status" in commands
    assert "diff" in commands
    assert "log" in commands
