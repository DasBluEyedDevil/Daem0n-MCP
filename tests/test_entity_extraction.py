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
