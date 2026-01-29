"""Tests for the CLI integration of install/uninstall-claude-hooks commands."""

import json
import subprocess
import sys

import pytest


def test_cli_install_claude_hooks_dry_run():
    result = subprocess.run(
        [sys.executable, "-m", "daem0nmcp.cli", "install-claude-hooks", "--dry-run"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "[dry-run]" in result.stdout
    assert "SessionStart" in result.stdout


def test_cli_install_claude_hooks_json():
    result = subprocess.run(
        [sys.executable, "-m", "daem0nmcp.cli", "--json", "install-claude-hooks", "--dry-run"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["success"] is True


def test_cli_uninstall_claude_hooks_dry_run():
    result = subprocess.run(
        [sys.executable, "-m", "daem0nmcp.cli", "uninstall-claude-hooks", "--dry-run"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    # Either "No Daem0n hooks found" or "[dry-run]"
    assert "Daem0n" in result.stdout or "dry-run" in result.stdout
