# tests/test_linked_projects.py
"""Tests for linked projects feature."""

import pytest


class TestProjectLinkModel:
    """Test the ProjectLink model exists and has correct fields."""

    def test_project_link_model_exists(self):
        """ProjectLink model should be importable."""
        from daem0nmcp.models import ProjectLink

        assert hasattr(ProjectLink, '__tablename__')
        assert ProjectLink.__tablename__ == "project_links"

    def test_project_link_has_required_fields(self):
        """ProjectLink should have source_path, linked_path, relationship."""
        from daem0nmcp.models import ProjectLink

        # Check columns exist
        columns = {c.name for c in ProjectLink.__table__.columns}
        assert "id" in columns
        assert "source_path" in columns
        assert "linked_path" in columns
        assert "relationship" in columns
        assert "created_at" in columns


class TestProjectLinkMigration:
    """Test the migration creates the project_links table."""

    @pytest.fixture
    def db_manager(self, tmp_path):
        from daem0nmcp.database import DatabaseManager
        return DatabaseManager(str(tmp_path / "storage"))

    @pytest.mark.asyncio
    async def test_migration_creates_project_links_table(self, db_manager):
        """Migration should create project_links table."""
        await db_manager.init_db()

        import sqlite3
        conn = sqlite3.connect(str(db_manager.db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='project_links'"
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None, "project_links table should exist"


class TestLinkManager:
    """Test the LinkManager class."""

    @pytest.fixture
    def db_manager(self, tmp_path):
        from daem0nmcp.database import DatabaseManager
        return DatabaseManager(str(tmp_path / "storage"))

    @pytest.fixture
    def link_manager(self, db_manager):
        from daem0nmcp.links import LinkManager
        return LinkManager(db_manager)

    @pytest.mark.asyncio
    async def test_link_projects(self, db_manager, link_manager):
        """Should create a link between two projects."""
        await db_manager.init_db()

        result = await link_manager.link_projects(
            source_path="/repos/backend",
            linked_path="/repos/client",
            relationship="same-project"
        )

        assert result["status"] == "linked"
        assert result["source_path"] == "/repos/backend"
        assert result["linked_path"] == "/repos/client"

    @pytest.mark.asyncio
    async def test_list_linked_projects(self, db_manager, link_manager):
        """Should list all linked projects."""
        await db_manager.init_db()

        await link_manager.link_projects("/repos/backend", "/repos/client", "same-project")
        await link_manager.link_projects("/repos/backend", "/repos/shared", "upstream")

        links = await link_manager.list_linked_projects("/repos/backend")

        assert len(links) == 2
        paths = {link["linked_path"] for link in links}
        assert "/repos/client" in paths
        assert "/repos/shared" in paths

    @pytest.mark.asyncio
    async def test_unlink_projects(self, db_manager, link_manager):
        """Should remove a link between projects."""
        await db_manager.init_db()

        await link_manager.link_projects("/repos/backend", "/repos/client", "same-project")
        result = await link_manager.unlink_projects("/repos/backend", "/repos/client")

        assert result["status"] == "unlinked"

        links = await link_manager.list_linked_projects("/repos/backend")
        assert len(links) == 0

    @pytest.mark.asyncio
    async def test_duplicate_link_rejected(self, db_manager, link_manager):
        """Should not allow duplicate links."""
        await db_manager.init_db()

        await link_manager.link_projects("/repos/backend", "/repos/client", "same-project")
        result = await link_manager.link_projects("/repos/backend", "/repos/client", "same-project")

        assert result["status"] == "already_linked"


class TestLinkTools:
    """Test the MCP tools for link management."""

    @pytest.fixture
    def db_manager(self, tmp_path):
        from daem0nmcp.database import DatabaseManager
        return DatabaseManager(str(tmp_path / "storage"))

    @pytest.mark.asyncio
    async def test_link_projects_tool(self, db_manager):
        """link_projects MCP tool should create a link."""
        await db_manager.init_db()

        from daem0nmcp import server
        server._project_contexts.clear()

        project_path = str(db_manager.storage_path.parent.parent)

        # Briefing first (for communion)
        await server.get_briefing(project_path=project_path)

        result = await server.link_projects(
            linked_path="/repos/client",
            relationship="same-project",
            project_path=project_path
        )

        assert result["status"] == "linked"

    @pytest.mark.asyncio
    async def test_list_linked_projects_tool(self, db_manager):
        """list_linked_projects MCP tool should return links."""
        await db_manager.init_db()

        from daem0nmcp import server
        server._project_contexts.clear()

        project_path = str(db_manager.storage_path.parent.parent)

        await server.get_briefing(project_path=project_path)
        await server.link_projects(
            linked_path="/repos/client",
            relationship="same-project",
            project_path=project_path
        )

        result = await server.list_linked_projects(project_path=project_path)

        assert len(result["links"]) == 1
        assert result["links"][0]["linked_path"] == "/repos/client"

    @pytest.mark.asyncio
    async def test_unlink_projects_tool(self, db_manager):
        """unlink_projects MCP tool should remove a link."""
        await db_manager.init_db()

        from daem0nmcp import server
        server._project_contexts.clear()

        project_path = str(db_manager.storage_path.parent.parent)

        await server.get_briefing(project_path=project_path)
        await server.link_projects(
            linked_path="/repos/client",
            relationship="same-project",
            project_path=project_path
        )

        result = await server.unlink_projects(
            linked_path="/repos/client",
            project_path=project_path
        )

        assert result["status"] == "unlinked"
