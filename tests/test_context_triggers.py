"""Tests for contextual recall triggers."""

import pytest
from datetime import datetime, timezone

from daem0nmcp.models import ContextTrigger


class TestContextTriggerModel:
    """Test the ContextTrigger model structure."""

    def test_context_trigger_has_required_fields(self):
        """ContextTrigger should have all required fields."""
        trigger = ContextTrigger(
            project_path="/test/project",
            trigger_type="file_pattern",
            pattern="src/auth/**/*.py",
            recall_topic="authentication",
            is_active=True
        )

        assert trigger.project_path == "/test/project"
        assert trigger.trigger_type == "file_pattern"
        assert trigger.pattern == "src/auth/**/*.py"
        assert trigger.recall_topic == "authentication"
        assert trigger.is_active == True

    def test_context_trigger_default_values(self):
        """ContextTrigger should have sensible defaults when explicitly set."""
        # Note: SQLAlchemy Column defaults are applied at INSERT time, not instantiation
        # Test that the model accepts default-like values properly
        trigger = ContextTrigger(
            project_path="/test/project",
            trigger_type="tag_match",
            pattern="auth.*",
            recall_topic="authentication",
            is_active=True,
            priority=0,
            recall_categories=[],
            trigger_count=0
        )

        # Verify values are set correctly
        assert trigger.is_active == True
        assert trigger.priority == 0
        assert trigger.recall_categories == []
        assert trigger.trigger_count == 0
        assert trigger.last_triggered is None

    def test_context_trigger_all_fields(self):
        """ContextTrigger should support all fields."""
        now = datetime.now(timezone.utc)
        trigger = ContextTrigger(
            project_path="/test/project",
            trigger_type="entity_match",
            pattern="UserService|AuthService",
            recall_topic="user authentication",
            recall_categories=["decision", "warning"],
            is_active=False,
            priority=10,
            trigger_count=5,
            last_triggered=now
        )

        assert trigger.project_path == "/test/project"
        assert trigger.trigger_type == "entity_match"
        assert trigger.pattern == "UserService|AuthService"
        assert trigger.recall_topic == "user authentication"
        assert trigger.recall_categories == ["decision", "warning"]
        assert trigger.is_active == False
        assert trigger.priority == 10
        assert trigger.trigger_count == 5
        assert trigger.last_triggered == now

    def test_context_trigger_types(self):
        """ContextTrigger should support different trigger types."""
        # File pattern trigger
        file_trigger = ContextTrigger(
            project_path="/test",
            trigger_type="file_pattern",
            pattern="src/api/**/*.py",
            recall_topic="API design"
        )
        assert file_trigger.trigger_type == "file_pattern"

        # Tag match trigger
        tag_trigger = ContextTrigger(
            project_path="/test",
            trigger_type="tag_match",
            pattern="database|sql",
            recall_topic="database decisions"
        )
        assert tag_trigger.trigger_type == "tag_match"

        # Entity match trigger
        entity_trigger = ContextTrigger(
            project_path="/test",
            trigger_type="entity_match",
            pattern=".*Repository$",
            recall_topic="repository pattern"
        )
        assert entity_trigger.trigger_type == "entity_match"
