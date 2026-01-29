"""Tests for the session_start Claude Code hook."""

import asyncio
import subprocess
import sys

import pytest

from daem0nmcp.database import DatabaseManager
from daem0nmcp.memory import MemoryManager
from daem0nmcp.enforcement import SessionManager


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project with .daem0nmcp storage and seeded data."""
    daem0n_dir = tmp_path / ".daem0nmcp"
    daem0n_dir.mkdir()
    storage = daem0n_dir / "storage"
    storage.mkdir()

    db = DatabaseManager(str(storage))

    async def _seed():
        await db.init_db()
        memory = MemoryManager(db)
        await memory.remember(category="decision", content="Use Redis for caching", project_path=str(tmp_path))
        await memory.remember(category="pattern", content="Always use dependency injection", project_path=str(tmp_path))
        await memory.remember(category="warning", content="SQLite locks under heavy load", project_path=str(tmp_path))
        await db.close()

    asyncio.run(_seed())

    return tmp_path


def test_session_start_outputs_briefing(tmp_project):
    result = subprocess.run(
        [sys.executable, "-m", "daem0nmcp.claude_hooks.session_start"],
        capture_output=True,
        text=True,
        timeout=10,
        env={**__import__("os").environ, "CLAUDE_PROJECT_DIR": str(tmp_project)},
    )
    assert result.returncode == 0
    assert "[Daem0n Briefing]" in result.stdout
    assert "3 memories" in result.stdout
    assert "Commune complete." in result.stdout


def test_session_start_marks_briefed(tmp_project):
    subprocess.run(
        [sys.executable, "-m", "daem0nmcp.claude_hooks.session_start"],
        capture_output=True,
        text=True,
        timeout=10,
        env={**__import__("os").environ, "CLAUDE_PROJECT_DIR": str(tmp_project)},
    )

    # Verify session was marked as briefed
    db = DatabaseManager(str(tmp_project / ".daem0nmcp" / "storage"))

    async def _check():
        await db.init_db()
        session_mgr = SessionManager(db)
        state = await session_mgr.get_session_state(str(tmp_project))
        await db.close()
        return state

    state = asyncio.run(_check())
    assert state is not None
    assert state["briefed"] is True


def test_session_start_no_daem0n_exits_clean(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "daem0nmcp.claude_hooks.session_start"],
        capture_output=True,
        text=True,
        timeout=10,
        env={**__import__("os").environ, "CLAUDE_PROJECT_DIR": str(tmp_path)},
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""
