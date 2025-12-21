"""Tests for operational tools."""

import pytest


class TestHealthTool:
    """Test health and version reporting."""

    @pytest.mark.asyncio
    async def test_health_returns_version(self):
        """Verify health tool returns version info."""
        from daem0nmcp import __version__
        from daem0nmcp.server import health

        result = await health(project_path="/tmp/test")

        assert "version" in result
        assert result["version"] == __version__
        assert "status" in result

    @pytest.mark.asyncio
    async def test_health_returns_statistics(self):
        """Verify health tool returns memory statistics."""
        import tempfile
        import shutil
        from daem0nmcp.server import health, get_project_context, _project_contexts

        temp_dir = tempfile.mkdtemp()
        try:
            result = await health(project_path=temp_dir)

            assert "memories_count" in result
            assert "rules_count" in result
            assert "storage_path" in result
        finally:
            # Close the database connection before cleanup
            if temp_dir in _project_contexts:
                await _project_contexts[temp_dir].db_manager.close()
                del _project_contexts[temp_dir]
            shutil.rmtree(temp_dir, ignore_errors=True)
