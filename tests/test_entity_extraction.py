"""Tests for auto entity extraction from memories."""

import pytest
from datetime import datetime, timezone

from daem0nmcp.models import ExtractedEntity, MemoryEntityRef


class TestExtractedEntityModel:
    """Test the ExtractedEntity model structure."""

    def test_extracted_entity_has_required_fields(self):
        """ExtractedEntity should have all required fields."""
        entity = ExtractedEntity(
            project_path="/test/project",
            entity_type="function",
            name="authenticate_user",
            qualified_name="auth.service.authenticate_user",
            mention_count=3
        )

        assert entity.project_path == "/test/project"
        assert entity.entity_type == "function"
        assert entity.name == "authenticate_user"
        assert entity.mention_count == 3

    def test_extracted_entity_optional_fields(self):
        """ExtractedEntity should have optional code_entity_id field."""
        entity = ExtractedEntity(
            project_path="/test/project",
            entity_type="class",
            name="UserService",
            code_entity_id="abc123"
        )

        assert entity.code_entity_id == "abc123"
        assert entity.qualified_name is None
        # Note: mention_count default (1) is applied at DB insert time, not object creation


class TestMemoryEntityRefModel:
    """Test the MemoryEntityRef model structure."""

    def test_memory_entity_ref_has_required_fields(self):
        """MemoryEntityRef should link memory to entity."""
        ref = MemoryEntityRef(
            memory_id=1,
            entity_id=42,
            relationship="mentions",
            context_snippet="...calls authenticate_user()..."
        )

        assert ref.memory_id == 1
        assert ref.entity_id == 42
        assert ref.relationship == "mentions"
        assert ref.context_snippet == "...calls authenticate_user()..."

    def test_memory_entity_ref_optional_fields(self):
        """MemoryEntityRef should allow optional context_snippet."""
        ref = MemoryEntityRef(
            memory_id=1,
            entity_id=42,
            relationship="about"
        )

        assert ref.relationship == "about"
        assert ref.context_snippet is None
        # Note: relationship default ('mentions') is applied at DB insert time, not object creation


@pytest.fixture
def extractor():
    """Create an entity extractor."""
    from daem0nmcp.entity_extractor import EntityExtractor
    return EntityExtractor()


class TestEntityExtractor:
    """Test entity extraction from text."""

    def test_extract_function_names(self, extractor):
        """Should extract function names from content."""
        text = "Call authenticate_user() to verify the token, then call get_permissions()"
        entities = extractor.extract_entities(text)

        functions = [e for e in entities if e["type"] == "function"]
        names = [f["name"] for f in functions]

        assert "authenticate_user" in names
        assert "get_permissions" in names

    def test_extract_class_names(self, extractor):
        """Should extract class names from content."""
        text = "The UserService class handles auth. Use AuthController for API endpoints."
        entities = extractor.extract_entities(text)

        classes = [e for e in entities if e["type"] == "class"]
        names = [c["name"] for c in classes]

        assert "UserService" in names
        assert "AuthController" in names

    def test_extract_file_paths(self, extractor):
        """Should extract file paths from content."""
        text = "Edit src/auth/service.py and update tests/test_auth.py"
        entities = extractor.extract_entities(text)

        files = [e for e in entities if e["type"] == "file"]
        names = [f["name"] for f in files]

        assert "src/auth/service.py" in names
        assert "tests/test_auth.py" in names


import tempfile
import shutil


@pytest.fixture
def temp_storage():
    """Create a temporary storage directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
async def entity_manager(temp_storage):
    """Create an entity manager with temporary storage."""
    from daem0nmcp.database import DatabaseManager
    from daem0nmcp.entity_manager import EntityManager

    db = DatabaseManager(temp_storage)
    await db.init_db()
    manager = EntityManager(db)
    yield manager
    await db.close()


@pytest.mark.asyncio
async def test_process_memory_extracts_entities(entity_manager, temp_storage):
    """Processing a memory should extract and store entities."""
    from daem0nmcp.memory import MemoryManager
    from daem0nmcp.database import DatabaseManager

    db = DatabaseManager(temp_storage)
    await db.init_db()
    mem_manager = MemoryManager(db)

    # Create a memory with entity references
    mem = await mem_manager.remember(
        category="decision",
        content="Use authenticate_user() in the UserService class for auth"
    )

    # Process it
    result = await entity_manager.process_memory(
        memory_id=mem["id"],
        content=mem["content"],
        project_path=temp_storage
    )

    assert result["entities_found"] > 0
    assert result["refs_created"] > 0

    # Verify entities were stored
    entities = await entity_manager.get_entities_for_memory(mem["id"])
    assert len(entities) > 0

    await db.close()


@pytest.mark.asyncio
async def test_get_memories_for_entity(entity_manager, temp_storage):
    """Should retrieve memories by entity name."""
    from daem0nmcp.memory import MemoryManager
    from daem0nmcp.database import DatabaseManager

    db = DatabaseManager(temp_storage)
    await db.init_db()
    mem_manager = MemoryManager(db)

    mem = await mem_manager.remember(
        category="decision",
        content="Use UserService for auth operations"
    )
    await entity_manager.process_memory(
        memory_id=mem["id"],
        content=mem["content"],
        project_path=temp_storage
    )

    result = await entity_manager.get_memories_for_entity(
        entity_name="UserService",
        project_path=temp_storage
    )

    assert result["found"] is True
    assert len(result["memories"]) == 1
    await db.close()


@pytest.mark.asyncio
async def test_get_popular_entities(entity_manager, temp_storage):
    """Should return most mentioned entities."""
    from daem0nmcp.memory import MemoryManager
    from daem0nmcp.database import DatabaseManager

    db = DatabaseManager(temp_storage)
    await db.init_db()
    mem_manager = MemoryManager(db)

    # Create multiple memories mentioning same entity
    for i in range(3):
        mem = await mem_manager.remember(
            category="decision",
            content=f"Call authenticate_user() for step {i}"
        )
        await entity_manager.process_memory(
            memory_id=mem["id"],
            content=mem["content"],
            project_path=temp_storage
        )

    popular = await entity_manager.get_popular_entities(temp_storage, limit=5)

    assert len(popular) > 0
    await db.close()


@pytest.mark.asyncio
async def test_remember_auto_extracts_entities(temp_storage):
    """remember() should auto-extract entities."""
    from daem0nmcp.database import DatabaseManager
    from daem0nmcp.memory import MemoryManager
    from daem0nmcp.entity_manager import EntityManager

    db = DatabaseManager(temp_storage)
    await db.init_db()
    mem_manager = MemoryManager(db)
    ent_manager = EntityManager(db)

    # Create memory (should auto-extract)
    mem = await mem_manager.remember(
        category="decision",
        content="Call authenticate_user() in UserService",
        project_path=temp_storage
    )

    # Check entities were extracted
    entities = await ent_manager.get_entities_for_memory(mem["id"])

    await db.close()

    assert len(entities) > 0
    names = [e["name"] for e in entities]
    assert "authenticate_user" in names
