"""Tests for Iteration 3: Incremental Indexing."""

import pytest
from datetime import datetime, timezone


class TestFileHashModel:
    """Test FileHash model."""

    def test_file_hash_has_required_fields(self):
        """FileHash should have all required fields."""
        from daem0nmcp.models import FileHash

        fh = FileHash(
            project_path="/test/project",
            file_path="src/main.py",
            content_hash="abc123"
        )

        assert fh.project_path == "/test/project"
        assert fh.file_path == "src/main.py"
        assert fh.content_hash == "abc123"
