"""Tests for enhanced bootstrap functionality."""
import json
import tempfile
from pathlib import Path

import pytest

from daem0nmcp.server import _extract_project_identity, _extract_architecture, _extract_conventions, _extract_entry_points, _scan_todos_for_bootstrap


class TestExtractProjectIdentity:
    """Tests for _extract_project_identity extractor."""

    def test_extracts_package_json(self, tmp_path):
        """Should extract name, description, and dependencies from package.json."""
        package = {
            "name": "my-app",
            "version": "1.0.0",
            "description": "A test application",
            "scripts": {"test": "jest", "build": "webpack"},
            "dependencies": {"react": "^18.0.0", "lodash": "^4.17.0"}
        }
        (tmp_path / "package.json").write_text(json.dumps(package))

        result = _extract_project_identity(str(tmp_path))

        assert result is not None
        assert "my-app" in result
        assert "A test application" in result
        assert "react" in result

    def test_extracts_pyproject_toml(self, tmp_path):
        """Should extract project info from pyproject.toml."""
        pyproject = '''
[project]
name = "my-python-app"
version = "2.0.0"
description = "A Python application"
dependencies = ["fastapi", "sqlalchemy"]
'''
        (tmp_path / "pyproject.toml").write_text(pyproject)

        result = _extract_project_identity(str(tmp_path))

        assert result is not None
        assert "my-python-app" in result
        assert "A Python application" in result

    def test_returns_none_when_no_manifest(self, tmp_path):
        """Should return None when no manifest file exists."""
        result = _extract_project_identity(str(tmp_path))
        assert result is None

    def test_package_json_takes_priority(self, tmp_path):
        """When multiple manifests exist, package.json wins."""
        (tmp_path / "package.json").write_text('{"name": "node-app"}')
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "python-app"')

        result = _extract_project_identity(str(tmp_path))

        assert "node-app" in result


class TestExtractArchitecture:
    """Tests for _extract_architecture extractor."""

    def test_extracts_readme_content(self, tmp_path):
        """Should extract first 2000 chars from README.md."""
        readme = "# My Project\n\nThis is a test project.\n\n## Features\n- Feature 1\n- Feature 2"
        (tmp_path / "README.md").write_text(readme)

        result = _extract_architecture(str(tmp_path))

        assert result is not None
        assert "My Project" in result
        assert "Feature 1" in result

    def test_includes_directory_structure(self, tmp_path):
        """Should include top-level directory structure."""
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        (tmp_path / "docs").mkdir()
        (tmp_path / "README.md").write_text("# Test")

        result = _extract_architecture(str(tmp_path))

        assert "src" in result
        assert "tests" in result

    def test_excludes_noise_directories(self, tmp_path):
        """Should exclude node_modules, .git, etc."""
        (tmp_path / "src").mkdir()
        (tmp_path / "node_modules").mkdir()
        (tmp_path / ".git").mkdir()

        result = _extract_architecture(str(tmp_path))

        assert result is not None
        assert "node_modules" not in result
        assert ".git" not in result

    def test_returns_structure_only_without_readme(self, tmp_path):
        """Should return directory structure even without README."""
        (tmp_path / "src").mkdir()
        (tmp_path / "lib").mkdir()

        result = _extract_architecture(str(tmp_path))

        assert result is not None
        assert "src" in result


class TestExtractConventions:
    """Tests for _extract_conventions extractor."""

    def test_extracts_contributing_guidelines(self, tmp_path):
        """Should extract content from CONTRIBUTING.md."""
        contributing = "# Contributing\n\n## Code Style\nUse 4 spaces for indentation."
        (tmp_path / "CONTRIBUTING.md").write_text(contributing)

        result = _extract_conventions(str(tmp_path))

        assert result is not None
        assert "Code Style" in result

    def test_detects_eslint_config(self, tmp_path):
        """Should detect ESLint configuration."""
        (tmp_path / ".eslintrc.json").write_text('{"extends": "airbnb"}')

        result = _extract_conventions(str(tmp_path))

        assert result is not None
        assert "eslint" in result.lower()

    def test_detects_ruff_config(self, tmp_path):
        """Should detect Ruff configuration."""
        (tmp_path / "ruff.toml").write_text('[tool.ruff]\nline-length = 88')

        result = _extract_conventions(str(tmp_path))

        assert result is not None
        assert "ruff" in result.lower()

    def test_returns_none_when_no_configs(self, tmp_path):
        """Should return None when no convention configs found."""
        result = _extract_conventions(str(tmp_path))
        assert result is None


class TestExtractEntryPoints:
    """Tests for _extract_entry_points extractor."""

    def test_finds_python_entry_points(self, tmp_path):
        """Should find main.py, app.py, etc."""
        (tmp_path / "main.py").write_text("# main")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("# app")

        result = _extract_entry_points(str(tmp_path))

        assert result is not None
        assert "main.py" in result

    def test_finds_node_entry_points(self, tmp_path):
        """Should find index.js, index.ts."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "index.ts").write_text("// index")

        result = _extract_entry_points(str(tmp_path))

        assert result is not None
        assert "index.ts" in result

    def test_finds_cli_entry_points(self, tmp_path):
        """Should find cli.py, __main__.py."""
        (tmp_path / "myapp").mkdir()
        (tmp_path / "myapp" / "__main__.py").write_text("# main")
        (tmp_path / "myapp" / "cli.py").write_text("# cli")

        result = _extract_entry_points(str(tmp_path))

        assert result is not None
        assert "__main__.py" in result

    def test_returns_none_when_no_entry_points(self, tmp_path):
        """Should return None when no entry points found."""
        (tmp_path / "utils.py").write_text("# utils")

        result = _extract_entry_points(str(tmp_path))

        assert result is None


class TestScanTodosForBootstrap:
    """Tests for _scan_todos_for_bootstrap extractor."""

    def test_finds_todo_comments(self, tmp_path):
        """Should find TODO comments in code files."""
        (tmp_path / "code.py").write_text("# TODO: Fix this later\nx = 1")

        result = _scan_todos_for_bootstrap(str(tmp_path))

        assert result is not None
        assert "TODO" in result
        assert "Fix this later" in result

    def test_finds_fixme_comments(self, tmp_path):
        """Should find FIXME comments."""
        (tmp_path / "code.py").write_text("# FIXME: This is broken\nx = 1")

        result = _scan_todos_for_bootstrap(str(tmp_path))

        assert result is not None
        assert "FIXME" in result

    def test_limits_results(self, tmp_path):
        """Should limit to 20 items."""
        code = "\n".join(f"# TODO: Item {i}" for i in range(30))
        (tmp_path / "code.py").write_text(code)

        result = _scan_todos_for_bootstrap(str(tmp_path), limit=20)

        # Count TODOs in result
        assert result.count("TODO:") <= 20

    def test_returns_none_when_no_todos(self, tmp_path):
        """Should return None when no TODOs found."""
        (tmp_path / "code.py").write_text("x = 1\ny = 2")

        result = _scan_todos_for_bootstrap(str(tmp_path))

        assert result is None
