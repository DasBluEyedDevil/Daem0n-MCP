"""Tests for passive capture CLI commands."""

import json
import subprocess
import sys


class TestRememberCLI:
    """Test the remember CLI command."""

    def test_remember_cli_creates_memory(self, tmp_path):
        """CLI remember command should create a memory."""
        result = subprocess.run(
            [
                sys.executable, "-m", "daem0nmcp.cli",
                "--project-path", str(tmp_path),
                "--json",
                "remember",
                "--category", "decision",
                "--content", "Test decision from CLI",
                "--rationale", "Testing CLI interface"
            ],
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL
        )

        assert result.returncode == 0, f"Failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert "id" in data
        assert data["id"] > 0

    def test_remember_cli_with_file_path(self, tmp_path):
        """CLI remember should accept file_path."""
        result = subprocess.run(
            [
                sys.executable, "-m", "daem0nmcp.cli",
                "--project-path", str(tmp_path),
                "--json",
                "remember",
                "--category", "warning",
                "--content", "Don't modify this file carelessly",
                "--file-path", "src/critical.py"
            ],
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data.get("file_path") == "src/critical.py"
