"""Tests for the pre_edit Claude Code hook (blocking)."""

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import pytest

from daem0nmcp.database import DatabaseManager
from daem0nmcp.memory import MemoryManager
from daem0nmcp.enforcement import SessionManager


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temp project with initialised database."""
    daem0n_dir = tmp_path / ".daem0nmcp"
    daem0n_dir.mkdir()
    storage = daem0n_dir / "storage"
    storage.mkdir()

    db = DatabaseManager(str(storage))
    asyncio.run(db.init_db())
    asyncio.run(db.close())

    return tmp_path


def _run_hook(env_overrides: dict) -> subprocess.CompletedProcess:
    env = {**os.environ, **env_overrides}
    return subprocess.run(
        [sys.executable, "-m", "daem0nmcp.claude_hooks.pre_edit"],
        capture_output=True,
        text=True,
        timeout=20,
        env=env,
    )


def _add_context_check(project_path: str):
    """Add a fresh context check to the session state."""
    storage = str(project_path / ".daem0nmcp" / "storage") if hasattr(project_path, '__truediv__') else str(project_path + "/.daem0nmcp/storage")
    db = DatabaseManager(storage)

    async def _run():
        await db.init_db()
        mgr = SessionManager(db)
        await mgr.add_context_check(str(project_path), "pre-edit test check")
        await db.close()

    asyncio.run(_run())


def test_blocks_without_preflight(tmp_project):
    tool_input = json.dumps({"file_path": str(tmp_project / "server.py")})
    result = _run_hook({
        "CLAUDE_PROJECT_DIR": str(tmp_project),
        "TOOL_INPUT": tool_input,
    })
    assert result.returncode == 2
    assert "No preflight token" in result.stderr
    assert "consult" in result.stderr


def test_allows_with_preflight(tmp_project):
    _add_context_check(tmp_project)

    tool_input = json.dumps({"file_path": str(tmp_project / "server.py")})
    result = _run_hook({
        "CLAUDE_PROJECT_DIR": str(tmp_project),
        "TOOL_INPUT": tool_input,
    })
    assert result.returncode == 0


def test_permissive_mode_allows_through(tmp_project):
    tool_input = json.dumps({"file_path": str(tmp_project / "server.py")})
    result = _run_hook({
        "CLAUDE_PROJECT_DIR": str(tmp_project),
        "TOOL_INPUT": tool_input,
        "DAEM0N_HOOKS_PERMISSIVE": "1",
    })
    # Permissive mode: exits 0 even without preflight
    assert result.returncode == 0
    assert "No preflight token" in result.stdout


def test_recalls_file_memories(tmp_project):
    # Add a warning memory for a file
    storage = str(tmp_project / ".daem0nmcp" / "storage")
    db = DatabaseManager(storage)

    async def _seed():
        await db.init_db()
        mem = MemoryManager(db)
        await mem.remember(
            category="warning",
            content="This file has a known race condition",
            file_path=str(tmp_project / "server.py"),
            project_path=str(tmp_project),
        )
        await db.close()

    asyncio.run(_seed())

    _add_context_check(tmp_project)

    tool_input = json.dumps({"file_path": str(tmp_project / "server.py")})
    result = _run_hook({
        "CLAUDE_PROJECT_DIR": str(tmp_project),
        "TOOL_INPUT": tool_input,
    })
    assert result.returncode == 0
    assert "race condition" in result.stdout


def test_no_file_path_allows_through(tmp_path):
    daem0n_dir = tmp_path / ".daem0nmcp"
    daem0n_dir.mkdir()

    tool_input = json.dumps({"command": "ls -la"})
    result = _run_hook({
        "CLAUDE_PROJECT_DIR": str(tmp_path),
        "TOOL_INPUT": tool_input,
    })
    assert result.returncode == 0
    assert result.stdout.strip() == ""
