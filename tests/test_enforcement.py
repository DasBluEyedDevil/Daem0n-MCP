"""Tests for enforcement models and session tracking."""

import pytest
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from daem0nmcp.models import SessionState, EnforcementBypassLog
from daem0nmcp.migrations import run_migrations, MIGRATIONS


class TestEnforcementModels:
    """Test the enforcement-related database models."""

    def test_session_state_model_exists(self):
        """SessionState model should exist with required fields."""
        session = SessionState(
            session_id="abc123-2025010112",
            project_path="/path/to/project",
            briefed=True,
            context_checks=["auth.py", "database"],
            pending_decisions=[1, 2, 3],
        )
        assert session.session_id == "abc123-2025010112"
        assert session.project_path == "/path/to/project"
        assert session.briefed is True
        assert session.context_checks == ["auth.py", "database"]
        assert session.pending_decisions == [1, 2, 3]

    def test_enforcement_bypass_log_model_exists(self):
        """EnforcementBypassLog model should exist with required fields."""
        log = EnforcementBypassLog(
            pending_decisions=[42, 43],
            staged_files_with_warnings=["src/auth.py"],
            reason="Emergency hotfix",
        )
        assert log.pending_decisions == [42, 43]
        assert log.staged_files_with_warnings == ["src/auth.py"]
        assert log.reason == "Emergency hotfix"


class TestEnforcementMigration:
    """Test that enforcement tables are created by migration."""

    def test_session_state_migration_exists(self):
        """Migration 8 should create session_state table."""
        migration_versions = [m[0] for m in MIGRATIONS]
        assert 8 in migration_versions, "Migration 8 should exist"

        migration_8 = next(m for m in MIGRATIONS if m[0] == 8)
        assert "session_state" in migration_8[1].lower() or any(
            "session_state" in sql for sql in migration_8[2]
        )

    def test_migration_creates_tables(self, tmp_path):
        """Running migrations should create enforcement tables."""
        db_path = tmp_path / "test.db"

        # Create a minimal database with schema_version table
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Pretend we're at version 7 (before enforcement)
        conn.execute("INSERT INTO schema_version (version) VALUES (7)")
        # Create memories table (required for foreign keys)
        conn.execute("""
            CREATE TABLE memories (
                id INTEGER PRIMARY KEY,
                category TEXT,
                content TEXT
            )
        """)
        conn.commit()
        conn.close()

        # Run migrations
        count, applied = run_migrations(str(db_path))

        # Verify tables exist
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='session_state'")
        assert cursor.fetchone() is not None, "session_state table should exist"

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='enforcement_bypass_log'")
        assert cursor.fetchone() is not None, "enforcement_bypass_log table should exist"

        conn.close()


class TestSessionManager:
    """Test session state management."""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """Create a test database manager."""
        from daem0nmcp.database import DatabaseManager
        return DatabaseManager(str(tmp_path / "storage"))

    @pytest.fixture
    def session_mgr(self, db_manager):
        """Create a session manager."""
        from daem0nmcp.enforcement import SessionManager
        return SessionManager(db_manager)

    def test_get_session_id_format(self):
        """Session ID should be deterministic based on project and hour."""
        from daem0nmcp.enforcement import get_session_id
        session_id = get_session_id("/path/to/project")
        assert "-" in session_id
        parts = session_id.split("-")
        assert len(parts[0]) == 8  # hash prefix
        assert len(parts[1]) == 10  # YYYYMMDDHH

    def test_get_session_id_same_hour(self):
        """Same project in same hour should get same session ID."""
        from daem0nmcp.enforcement import get_session_id
        id1 = get_session_id("/path/to/project")
        id2 = get_session_id("/path/to/project")
        assert id1 == id2

    def test_get_session_id_different_projects(self):
        """Different projects should get different session IDs."""
        from daem0nmcp.enforcement import get_session_id
        id1 = get_session_id("/path/to/project1")
        id2 = get_session_id("/path/to/project2")
        assert id1 != id2

    @pytest.mark.asyncio
    async def test_mark_briefed(self, db_manager, session_mgr):
        """Marking briefed should update session state."""
        await db_manager.init_db()
        project_path = "/test/project"

        await session_mgr.mark_briefed(project_path)

        state = await session_mgr.get_session_state(project_path)
        assert state is not None
        assert state["briefed"] is True

    @pytest.mark.asyncio
    async def test_add_context_check(self, db_manager, session_mgr):
        """Adding context check should update session state."""
        await db_manager.init_db()
        project_path = "/test/project"

        await session_mgr.add_context_check(project_path, "src/auth.py")
        await session_mgr.add_context_check(project_path, "authentication")

        state = await session_mgr.get_session_state(project_path)
        checks = state["context_checks"]  # Already a list (JSON column)
        assert "src/auth.py" in checks
        assert "authentication" in checks

    @pytest.mark.asyncio
    async def test_add_pending_decision(self, db_manager, session_mgr):
        """Adding pending decision should update session state."""
        await db_manager.init_db()
        project_path = "/test/project"

        await session_mgr.add_pending_decision(project_path, 42)
        await session_mgr.add_pending_decision(project_path, 43)

        state = await session_mgr.get_session_state(project_path)
        pending = state["pending_decisions"]  # Already a list
        assert 42 in pending
        assert 43 in pending

    @pytest.mark.asyncio
    async def test_remove_pending_decision(self, db_manager, session_mgr):
        """Removing pending decision should update session state."""
        await db_manager.init_db()
        project_path = "/test/project"

        await session_mgr.add_pending_decision(project_path, 42)
        await session_mgr.add_pending_decision(project_path, 43)
        await session_mgr.remove_pending_decision(project_path, 42)

        state = await session_mgr.get_session_state(project_path)
        pending = state["pending_decisions"]
        assert 42 not in pending
        assert 43 in pending
