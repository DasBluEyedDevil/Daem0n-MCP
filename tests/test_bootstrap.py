"""Tests for enhanced bootstrap functionality."""
import json
import tempfile
from pathlib import Path

import pytest

from daem0nmcp.server import _extract_project_identity, _extract_architecture


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
