"""Tests for the stop Claude Code hook."""

import asyncio
import json
import os
import subprocess
import sys

import pytest

from daem0nmcp.database import DatabaseManager
from daem0nmcp.memory import MemoryManager


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temp project with initialised database."""
    daem0n_dir = tmp_path / ".daem0nmcp"
    daem0n_dir.mkdir()
    storage = daem0n_dir / "storage"
    storage.mkdir()

    db = DatabaseManager(str(storage))
    asyncio.run(db.init_db())
    # Close to release the file for subprocess access
    asyncio.run(db.close())

    return tmp_path


def _make_transcript(tmp_path, messages: list[dict]):
    """Write a JSONL transcript file and return its path."""
    transcript = tmp_path / "transcript.jsonl"
    lines = [json.dumps(m) for m in messages]
    transcript.write_text("\n".join(lines), encoding="utf-8")
    return str(transcript)


def _run_hook(env_overrides: dict) -> subprocess.CompletedProcess:
    env = {**os.environ, **env_overrides}
    # Clear anti-loop state
    env.setdefault("CLAUDE_SESSION_ID", "test-stop-hook")
    return subprocess.run(
        [sys.executable, "-m", "daem0nmcp.claude_hooks.stop"],
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )


def _clean_state():
    """Remove anti-loop state files for the test session."""
    from pathlib import Path
    state = Path.home() / ".daem0nmcp" / "hook_state" / "stop_test-stop-hook.json"
    state.unlink(missing_ok=True)


def test_completion_signal_triggers_reminder(tmp_project, tmp_path):
    _clean_state()
    transcript_path = _make_transcript(tmp_path, [
        {"role": "user", "content": "Implement the login feature"},
        {"role": "assistant", "content": "I've successfully implemented the login feature. All tasks complete."},
    ])

    result = _run_hook({
        "CLAUDE_PROJECT_DIR": str(tmp_project),
        "CLAUDE_TRANSCRIPT_PATH": transcript_path,
    })

    assert result.returncode == 0
    assert "Daem0n" in result.stdout


def test_no_completion_no_output(tmp_project, tmp_path):
    _clean_state()
    transcript_path = _make_transcript(tmp_path, [
        {"role": "user", "content": "What does this function do?"},
        {"role": "assistant", "content": "Let me explain the function. The code is doing X."},
    ])

    result = _run_hook({
        "CLAUDE_PROJECT_DIR": str(tmp_project),
        "CLAUDE_TRANSCRIPT_PATH": transcript_path,
    })

    assert result.returncode == 0
    # Exploration-only or no completion -> no output
    assert result.stdout.strip() == ""


def test_auto_captures_decisions(tmp_project, tmp_path):
    _clean_state()
    transcript_path = _make_transcript(tmp_path, [
        {"role": "user", "content": "Add caching to the API"},
        {"role": "assistant", "content": (
            "I'll use Redis for caching because it provides fast in-memory storage "
            "with persistence options. Implementation is complete and all tasks are done."
        )},
    ])

    result = _run_hook({
        "CLAUDE_PROJECT_DIR": str(tmp_project),
        "CLAUDE_TRANSCRIPT_PATH": transcript_path,
    })

    assert result.returncode == 0
    out = result.stdout
    assert "auto-captured" in out or "Daem0n" in out

    # Verify memory was actually created
    db = DatabaseManager(str(tmp_project / ".daem0nmcp" / "storage"))

    async def _check():
        await db.init_db()
        mem = MemoryManager(db)
        stats = await mem.get_statistics()
        await db.close()
        return stats

    stats = asyncio.run(_check())
    assert stats["total_memories"] > 0


def test_anti_loop_prevents_spam(tmp_project, tmp_path):
    _clean_state()
    transcript_path = _make_transcript(tmp_path, [
        {"role": "user", "content": "Do something"},
        {"role": "assistant", "content": "All tasks are complete."},
    ])

    env = {
        "CLAUDE_PROJECT_DIR": str(tmp_project),
        "CLAUDE_TRANSCRIPT_PATH": transcript_path,
        "CLAUDE_SESSION_ID": "test-anti-loop",
    }

    # Clear state for this specific session
    from pathlib import Path
    state_file = Path.home() / ".daem0nmcp" / "hook_state" / "stop_test-anti-loop.json"
    state_file.unlink(missing_ok=True)

    # First run should produce output
    r1 = _run_hook(env)
    assert r1.returncode == 0

    # Second run should produce output (reminder_count goes to 2)
    r2 = _run_hook(env)
    assert r2.returncode == 0

    # Third run should be suppressed (reminder_count >= 2)
    r3 = _run_hook(env)
    assert r3.returncode == 0
    assert r3.stdout.strip() == ""

    # Cleanup
    state_file.unlink(missing_ok=True)


def test_no_transcript_exits_clean(tmp_project):
    result = _run_hook({
        "CLAUDE_PROJECT_DIR": str(tmp_project),
        "CLAUDE_TRANSCRIPT_PATH": "",
    })
    assert result.returncode == 0
    assert result.stdout.strip() == ""
