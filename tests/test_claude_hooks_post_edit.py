"""Tests for the post_edit Claude Code hook."""

import json
import subprocess
import sys
import os

import pytest


def _run_hook(env_overrides: dict) -> subprocess.CompletedProcess:
    env = {**os.environ, **env_overrides}
    return subprocess.run(
        [sys.executable, "-m", "daem0nmcp.claude_hooks.post_edit"],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


def test_significant_change_outputs_suggestion(tmp_path):
    daem0n_dir = tmp_path / ".daem0nmcp"
    daem0n_dir.mkdir()

    tool_input = json.dumps({
        "file_path": str(tmp_path / "server.py"),
        "old_string": "",
        "new_string": "class UserAuthService:\n    def __init__(self):\n        pass\n",
    })

    result = _run_hook({
        "CLAUDE_PROJECT_DIR": str(tmp_path),
        "TOOL_INPUT": tool_input,
    })

    assert result.returncode == 0
    assert "[Daem0n suggests]" in result.stdout
    assert "server.py" in result.stdout


def test_trivial_change_no_output(tmp_path):
    daem0n_dir = tmp_path / ".daem0nmcp"
    daem0n_dir.mkdir()

    tool_input = json.dumps({
        "file_path": str(tmp_path / "notes.txt"),
        "old_string": "hello",
        "new_string": "world",
    })

    result = _run_hook({
        "CLAUDE_PROJECT_DIR": str(tmp_path),
        "TOOL_INPUT": tool_input,
    })

    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_large_change_is_significant(tmp_path):
    daem0n_dir = tmp_path / ".daem0nmcp"
    daem0n_dir.mkdir()

    tool_input = json.dumps({
        "file_path": str(tmp_path / "big.py"),
        "old_string": "",
        "new_string": "x = 1\n" * 200,  # large change
    })

    result = _run_hook({
        "CLAUDE_PROJECT_DIR": str(tmp_path),
        "TOOL_INPUT": tool_input,
    })

    assert result.returncode == 0
    assert "[Daem0n suggests]" in result.stdout


def test_no_file_path_exits_clean(tmp_path):
    daem0n_dir = tmp_path / ".daem0nmcp"
    daem0n_dir.mkdir()

    tool_input = json.dumps({"command": "ls"})

    result = _run_hook({
        "CLAUDE_PROJECT_DIR": str(tmp_path),
        "TOOL_INPUT": tool_input,
    })

    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_no_project_exits_clean(tmp_path):
    tool_input = json.dumps({
        "file_path": str(tmp_path / "server.py"),
        "old_string": "",
        "new_string": "class Foo: pass",
    })

    result = _run_hook({
        "CLAUDE_PROJECT_DIR": str(tmp_path),
        "TOOL_INPUT": tool_input,
    })

    assert result.returncode == 0
    assert result.stdout.strip() == ""
