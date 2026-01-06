"""Tests for temporal versioning of memories."""

import pytest
import tempfile
import shutil
from datetime import datetime, timezone

from daem0nmcp.models import Memory, MemoryVersion


@pytest.fixture
def temp_storage():
    """Create a temporary storage directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
async def memory_manager(temp_storage):
    """Create a memory manager with temporary storage."""
    from daem0nmcp.database import DatabaseManager
    from daem0nmcp.memory import MemoryManager

    db = DatabaseManager(temp_storage)
    await db.init_db()
    manager = MemoryManager(db)
    yield manager
    if manager._qdrant:
        manager._qdrant.close()
    await db.close()


class TestMemoryVersionModel:
    """Test the MemoryVersion model structure."""

    def test_memory_version_has_required_fields(self):
        """MemoryVersion should have all required fields."""
        version = MemoryVersion(
            memory_id=1,
            version_number=1,
            content="Original content",
            rationale="Original rationale",
            context={},
            tags=["test"],
            change_type="created",
            changed_at=datetime.now(timezone.utc)
        )

        assert version.memory_id == 1
        assert version.version_number == 1
        assert version.content == "Original content"
        assert version.change_type == "created"


@pytest.mark.asyncio
async def test_memory_versions_table_created(temp_storage):
    """Verify memory_versions table is created during migration."""
    from daem0nmcp.database import DatabaseManager

    db = DatabaseManager(temp_storage)
    await db.init_db()

    async with db.get_session() as session:
        from sqlalchemy import text
        result = await session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='memory_versions'")
        )
        tables = result.fetchall()

    await db.close()
    assert len(tables) == 1
    assert tables[0][0] == "memory_versions"


@pytest.mark.asyncio
async def test_memory_versions_has_composite_index(temp_storage):
    """Verify memory_versions table has composite index on (memory_id, version_number)."""
    from daem0nmcp.database import DatabaseManager

    db = DatabaseManager(temp_storage)
    await db.init_db()

    async with db.get_session() as session:
        from sqlalchemy import text
        result = await session.execute(
            text("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='memory_versions'")
        )
        indexes = {row[0]: row[1] for row in result.fetchall()}

    await db.close()
    # Check that the composite index exists on (memory_id, version_number)
    composite_index_found = any(
        'memory_id' in (sql or '') and 'version_number' in (sql or '')
        for sql in indexes.values()
    )
    assert composite_index_found, \
        f"Expected composite index on (memory_id, version_number), found indexes: {indexes}"


@pytest.mark.asyncio
async def test_remember_creates_initial_version(memory_manager):
    """When a memory is created, version 1 should be auto-created."""
    result = await memory_manager.remember(
        category="decision",
        content="Use PostgreSQL",
        rationale="Better JSON support"
    )

    memory_id = result["id"]
    versions = await memory_manager.get_memory_versions(memory_id)

    assert len(versions) == 1
    assert versions[0]["version_number"] == 1
    assert versions[0]["change_type"] == "created"
    assert versions[0]["content"] == "Use PostgreSQL"


@pytest.mark.asyncio
async def test_record_outcome_creates_version(memory_manager):
    """Recording an outcome should create a new version."""
    result = await memory_manager.remember(
        category="decision",
        content="Use Redis for caching"
    )
    memory_id = result["id"]

    await memory_manager.record_outcome(
        memory_id=memory_id,
        outcome="Redis worked great, 10x faster",
        worked=True
    )

    versions = await memory_manager.get_memory_versions(memory_id)

    assert len(versions) == 2
    assert versions[1]["version_number"] == 2
    assert versions[1]["change_type"] == "outcome_recorded"
    assert versions[1]["outcome"] == "Redis worked great, 10x faster"
    assert versions[1]["worked"] == True


@pytest.mark.asyncio
async def test_get_memory_at_time(memory_manager):
    """Should return memory state as it was at a specific time."""
    from datetime import timedelta

    result = await memory_manager.remember(
        category="decision",
        content="Original content"
    )
    memory_id = result["id"]

    # Get the creation time
    versions = await memory_manager.get_memory_versions(memory_id)
    creation_time = versions[0]["changed_at"]

    # Record an outcome (creates version 2)
    await memory_manager.record_outcome(
        memory_id=memory_id,
        outcome="It worked",
        worked=True
    )

    # Query memory at creation time (before outcome)
    query_time = datetime.fromisoformat(creation_time)
    historical = await memory_manager.get_memory_at_time(memory_id, query_time)

    assert historical is not None
    assert historical["content"] == "Original content"
    assert historical["outcome"] is None  # No outcome at that time
