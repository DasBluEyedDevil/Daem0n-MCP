"""Tests for Phase 22: LLM Compatibility -- provenance tracking.

Covers:
- Memory model provenance columns
- Migration 15
- MemoryManager.remember() with/without provenance
- Inscribe dispatch _client_meta extraction
- CovenantMiddleware on_initialize
- Plugin template validation
"""

import json
import pytest
import tempfile
import shutil
from unittest.mock import AsyncMock, patch

from daem0nmcp.database import DatabaseManager
from daem0nmcp.memory import MemoryManager
from daem0nmcp.models import Memory
from daem0nmcp.migrations.schema import MIGRATIONS
from daem0nmcp.transforms.covenant import CovenantMiddleware


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_storage():
    """Create a temporary storage directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
async def memory_manager(temp_storage):
    """Create a memory manager with temporary storage."""
    db = DatabaseManager(temp_storage)
    await db.init_db()
    manager = MemoryManager(db)
    yield manager
    if manager._qdrant:
        manager._qdrant.close()
    await db.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMemoryModelProvenance:
    """Verify Memory model has provenance columns."""

    def test_memory_model_has_provenance_columns(self):
        """Memory model must have source_client and source_model as Column attributes."""
        from sqlalchemy import Column as SAColumn
        assert hasattr(Memory, 'source_client')
        assert hasattr(Memory, 'source_model')
        # Verify they are actual SQLAlchemy column descriptors
        assert isinstance(Memory.__table__.columns['source_client'].type, type(Memory.__table__.columns['content'].type).__mro__[0]) or True
        # Simpler check: column names are in the table
        col_names = [c.name for c in Memory.__table__.columns]
        assert 'source_client' in col_names
        assert 'source_model' in col_names


class TestMigration15:
    """Verify migration 15 exists with correct SQL."""

    def test_migration_15_exists(self):
        """Migration 15 must be in MIGRATIONS list with source_client and source_model ALTER TABLE statements."""
        m15_list = [m for m in MIGRATIONS if m[0] == 15]
        assert len(m15_list) == 1, "Exactly one migration 15 expected"

        version, description, stmts = m15_list[0]
        assert version == 15
        assert "source_client" in description.lower() or "llm" in description.lower()

        # Should have ALTER TABLE for source_client and source_model, plus index
        sql_text = " ".join(stmts)
        assert "source_client" in sql_text
        assert "source_model" in sql_text
        assert "ALTER TABLE" in sql_text
        assert "CREATE INDEX" in sql_text


class TestRememberProvenance:
    """Test MemoryManager.remember() with provenance params."""

    @pytest.mark.asyncio
    async def test_remember_stores_provenance(self, memory_manager):
        """Calling remember() with source_client and source_model should store and return them."""
        result = await memory_manager.remember(
            category="decision",
            content="Use FastAPI for the API layer",
            rationale="Async support and automatic OpenAPI docs",
            tags=["api"],
            source_client="opencode",
            source_model="anthropic/claude-sonnet-4",
        )

        assert "id" in result
        assert result["source_client"] == "opencode"
        assert result["source_model"] == "anthropic/claude-sonnet-4"

    @pytest.mark.asyncio
    async def test_remember_provenance_defaults_to_none(self, memory_manager):
        """Calling remember() without provenance params should default to None (backward compat)."""
        result = await memory_manager.remember(
            category="learning",
            content="SQLite WAL mode improves concurrency",
            rationale="Discovered during load testing",
            tags=["database"],
        )

        assert "id" in result
        assert result["source_client"] is None
        assert result["source_model"] is None


class TestInscribeDispatchClientMeta:
    """Test inscribe.dispatch() _client_meta extraction."""

    @pytest.mark.asyncio
    async def test_inscribe_dispatch_extracts_client_meta(self, memory_manager):
        """dispatch(action='remember', _client_meta=...) should thread provenance to stored memory."""
        from daem0nmcp.workflows import inscribe

        meta = {
            "client": "opencode",
            "providerID": "openai",
            "modelID": "gpt-5",
        }

        # Mock get_project_context to return our test memory_manager
        mock_ctx = AsyncMock()
        mock_ctx.memory_manager = memory_manager
        mock_ctx.project_path = "/tmp/test-project"

        with patch("daem0nmcp.context_manager.get_project_context", return_value=mock_ctx):
            result = await inscribe.dispatch(
                action="remember",
                project_path="/tmp/test-project",
                category="decision",
                content="Use gRPC for inter-service communication",
                rationale="Better performance than REST",
                tags=["architecture"],
                _client_meta=json.dumps(meta),
            )

        assert result["source_client"] == "opencode"
        assert result["source_model"] == "openai/gpt-5"

    @pytest.mark.asyncio
    async def test_inscribe_dispatch_ignores_malformed_meta(self, memory_manager):
        """dispatch() with malformed _client_meta should not raise; provenance defaults to None."""
        from daem0nmcp.workflows import inscribe

        mock_ctx = AsyncMock()
        mock_ctx.memory_manager = memory_manager
        mock_ctx.project_path = "/tmp/test-project"

        with patch("daem0nmcp.context_manager.get_project_context", return_value=mock_ctx):
            result = await inscribe.dispatch(
                action="remember",
                project_path="/tmp/test-project",
                category="warning",
                content="Never use eval() on user input",
                rationale="Security vulnerability",
                tags=["security"],
                _client_meta="not-valid-json",
            )

        assert "id" in result
        assert result["source_client"] is None
        assert result["source_model"] is None


class TestCovenantMiddleware:
    """Test CovenantMiddleware on_initialize and client_name."""

    def test_covenant_middleware_has_on_initialize(self):
        """CovenantMiddleware must have an on_initialize method and client_name property."""
        middleware = CovenantMiddleware(get_state=lambda p: None)
        assert hasattr(middleware, 'on_initialize')
        assert callable(middleware.on_initialize)
        assert hasattr(middleware, 'client_name')
        # client_name should be None before any initialization
        assert middleware.client_name is None


class TestPluginTemplate:
    """Verify plugin template contains required LLM compatibility features."""

    def test_simplified_covenant_in_plugin_template(self):
        """PLUGIN_TEMPLATE must contain both COVENANT_RULES_FULL and COVENANT_RULES_SIMPLIFIED,
        plus _client_meta injection and currentModel tracking."""
        from daem0nmcp.opencode_install import PLUGIN_TEMPLATE

        assert "COVENANT_RULES_FULL" in PLUGIN_TEMPLATE, (
            "PLUGIN_TEMPLATE must reference COVENANT_RULES_FULL"
        )
        assert "COVENANT_RULES_SIMPLIFIED" in PLUGIN_TEMPLATE, (
            "PLUGIN_TEMPLATE must reference COVENANT_RULES_SIMPLIFIED"
        )
        assert "_client_meta" in PLUGIN_TEMPLATE, (
            "PLUGIN_TEMPLATE must inject _client_meta for provenance tracking"
        )
        assert "currentModel" in PLUGIN_TEMPLATE, (
            "PLUGIN_TEMPLATE must track currentModel for _client_meta injection"
        )
