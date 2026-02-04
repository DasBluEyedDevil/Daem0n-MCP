"""Tests for the CLI integration of install/uninstall-claude-hooks commands."""

import json

import pytest

from daem0nmcp.claude_hooks.install import install_claude_hooks, uninstall_claude_hooks


@pytest.fixture
def fake_settings(tmp_path, monkeypatch):
    """Redirect settings to a temp dir and return the settings file path."""
    settings_dir = tmp_path / ".claude"
    settings_dir.mkdir()
    settings_file = settings_dir / "settings.json"

    monkeypatch.setattr(
        "daem0nmcp.claude_hooks.install._settings_path",
        lambda: settings_file,
    )
    return settings_file


def test_cli_install_claude_hooks_dry_run(fake_settings):
    ok, msg = install_claude_hooks(dry_run=True)
    assert ok
    assert "[dry-run]" in msg
    assert "PreToolUse" in msg


def test_cli_install_claude_hooks_json(fake_settings):
    ok, msg = install_claude_hooks(dry_run=True)
    assert ok
    output = json.dumps({"success": ok, "message": msg})
    data = json.loads(output)
    assert data["success"] is True


def test_cli_uninstall_claude_hooks_dry_run(fake_settings):
    # Nothing installed -> "No Daem0n hooks found"
    fake_settings.write_text(json.dumps({"hooks": {}}))
    ok, msg = uninstall_claude_hooks(dry_run=True)
    assert ok
    assert "No Daem0n hooks found" in msg
