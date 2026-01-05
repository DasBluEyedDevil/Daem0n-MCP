# tests/test_endless_mode.py
"""Tests for Endless Mode context compression."""

import pytest
import tempfile
import shutil

from daem0nmcp.database import DatabaseManager
from daem0nmcp.memory import MemoryManager


@pytest.fixture
def temp_storage():
    """Create a temporary storage directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
async def memory_manager(temp_storage):
    """Create a memory manager with temporary storage."""
    db = DatabaseManager(temp_storage)
    await db.init_db()
    manager = MemoryManager(db)
    yield manager
    # Close Qdrant before cleanup to release file locks on Windows
    if manager._qdrant:
        manager._qdrant.close()
    await db.close()


class TestCondensedRecall:
    """Test condensed mode in recall()."""

    @pytest.mark.asyncio
    async def test_recall_accepts_condensed_parameter(self, memory_manager):
        """recall() should accept condensed parameter."""
        # Create a memory with verbose content
        await memory_manager.remember(
            category="decision",
            content="This is a very long decision content that should be truncated when condensed mode is enabled",
            rationale="This is detailed rationale explaining why we made this decision",
            context={"key": "value", "nested": {"data": "here"}}
        )

        # Should not raise - condensed parameter accepted
        result = await memory_manager.recall("decision", condensed=True)
        assert "decisions" in result

    @pytest.mark.asyncio
    async def test_condensed_strips_rationale(self, memory_manager):
        """Condensed mode should strip rationale field."""
        await memory_manager.remember(
            category="decision",
            content="Use JWT tokens",
            rationale="Need stateless auth for horizontal scaling"
        )

        result = await memory_manager.recall("JWT", condensed=True)
        assert len(result["decisions"]) > 0
        # Rationale should be None or absent in condensed mode
        decision = result["decisions"][0]
        assert decision.get("rationale") is None

    @pytest.mark.asyncio
    async def test_condensed_strips_context(self, memory_manager):
        """Condensed mode should strip context field."""
        await memory_manager.remember(
            category="decision",
            content="Use PostgreSQL",
            context={"alternatives": ["MySQL", "MongoDB"], "reason": "ACID compliance"}
        )

        result = await memory_manager.recall("PostgreSQL", condensed=True)
        decision = result["decisions"][0]
        # Context should be None or absent in condensed mode
        assert decision.get("context") is None

    @pytest.mark.asyncio
    async def test_condensed_truncates_long_content(self, memory_manager):
        """Condensed mode should truncate content over 150 chars."""
        long_content = "This is a very long learning content that needs to be truncated " * 10  # >150 chars
        await memory_manager.remember(
            category="learning",
            content=long_content
        )

        result = await memory_manager.recall("long learning content truncated", condensed=True)
        assert len(result["learnings"]) > 0, f"No learnings found. Result: {result}"
        learning = result["learnings"][0]
        # Should be truncated to ~150 chars with ellipsis
        assert len(learning["content"]) <= 153  # 150 + "..."
        assert learning["content"].endswith("...")

    @pytest.mark.asyncio
    async def test_non_condensed_preserves_all_fields(self, memory_manager):
        """Non-condensed mode should preserve all fields."""
        await memory_manager.remember(
            category="decision",
            content="Use Redis for caching",
            rationale="Fast in-memory store",
            context={"alternatives": ["Memcached"]}
        )

        result = await memory_manager.recall("Redis", condensed=False)
        decision = result["decisions"][0]
        assert decision["rationale"] == "Fast in-memory store"
        assert decision["context"] == {"alternatives": ["Memcached"]}
