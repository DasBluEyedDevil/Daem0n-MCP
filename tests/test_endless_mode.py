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
