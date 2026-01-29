"""Tests for the pre_bash Claude Code hook (blocking)."""

import asyncio
import json
import os
import subprocess
import sys

import pytest

from daem0nmcp.database import DatabaseManager
from daem0nmcp.rules import RulesEngine


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
        [sys.executable, "-m", "daem0nmcp.claude_hooks.pre_bash"],
        capture_output=True,
        text=True,
        timeout=20,
        env=env,
    )


def _add_rule(project_path, trigger, must_not=None, warnings=None):
    """Add a rule to the project database."""
    storage = str(project_path / ".daem0nmcp" / "storage")
    db = DatabaseManager(storage)

    async def _run():
        await db.init_db()
        engine = RulesEngine(db)
        await engine.add_rule(
            trigger=trigger,
            must_not=must_not or [],
            warnings=warnings or [],
        )
        await db.close()

    asyncio.run(_run())


def test_no_rules_allows_through(tmp_project):
    tool_input = json.dumps({"command": "git status"})
    result = _run_hook({
        "CLAUDE_PROJECT_DIR": str(tmp_project),
        "TOOL_INPUT": tool_input,
    })
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_blocks_on_must_not(tmp_project):
    _add_rule(
        tmp_project,
        trigger="executing bash dangerous database command",
        must_not=["Never run DROP TABLE in production"],
    )

    tool_input = json.dumps({"command": "psql -c 'DROP TABLE users' database"})
    result = _run_hook({
        "CLAUDE_PROJECT_DIR": str(tmp_project),
        "TOOL_INPUT": tool_input,
    })
    assert result.returncode == 2
    assert "Daem0n blocks" in result.stderr
    assert "MUST NOT" in result.stderr


def test_warns_on_soft_rule(tmp_project):
    _add_rule(
        tmp_project,
        trigger="executing bash git push command",
        warnings=["Always verify branch before pushing"],
    )

    tool_input = json.dumps({"command": "git push origin main"})
    result = _run_hook({
        "CLAUDE_PROJECT_DIR": str(tmp_project),
        "TOOL_INPUT": tool_input,
    })
    assert result.returncode == 0
    assert "Daem0n warns" in result.stdout


def test_permissive_mode(tmp_project):
    _add_rule(
        tmp_project,
        trigger="executing bash dangerous database command",
        must_not=["Never run DROP TABLE"],
    )

    tool_input = json.dumps({"command": "psql -c 'DROP TABLE users' database"})
    result = _run_hook({
        "CLAUDE_PROJECT_DIR": str(tmp_project),
        "TOOL_INPUT": tool_input,
        "DAEM0N_HOOKS_PERMISSIVE": "1",
    })
    # Permissive: exits 0 even with must_not
    assert result.returncode == 0


def test_no_project_exits_clean(tmp_path):
    tool_input = json.dumps({"command": "ls"})
    result = _run_hook({
        "CLAUDE_PROJECT_DIR": str(tmp_path),
        "TOOL_INPUT": tool_input,
    })
    assert result.returncode == 0
    assert result.stdout.strip() == ""
