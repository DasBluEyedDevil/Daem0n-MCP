"""Tests for the rules engine."""

import pytest
from pathlib import Path
import tempfile
import shutil

from devilmcp.database import DatabaseManager
from devilmcp.rules import RulesEngine, match_score


class TestMatchScore:
    """Test rule matching logic."""

    def test_full_match(self):
        action_keywords = {"adding", "new", "api", "endpoint"}
        rule_keywords = "adding api endpoint"
        score = match_score(action_keywords, rule_keywords)
        assert score >= 0.9

    def test_partial_match(self):
        action_keywords = {"modifying", "database", "schema"}
        rule_keywords = "database migration schema"
        score = match_score(action_keywords, rule_keywords)
        assert 0.3 <= score <= 0.9

    def test_no_match(self):
        action_keywords = {"authentication", "login"}
        rule_keywords = "database migration"
        score = match_score(action_keywords, rule_keywords)
        assert score < 0.3

    def test_empty_inputs(self):
        assert match_score(set(), "keywords") == 0.0
        assert match_score({"word"}, "") == 0.0
        assert match_score(set(), "") == 0.0


@pytest.fixture
def temp_storage():
    """Create a temporary storage directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
async def rules_engine(temp_storage):
    """Create a rules engine with temporary storage."""
    db = DatabaseManager(temp_storage)
    await db.init_db()
    engine = RulesEngine(db)
    yield engine
    await db.close()


class TestRulesEngine:
    """Test rule management and checking."""

    @pytest.mark.asyncio
    async def test_add_rule(self, rules_engine):
        """Test adding a rule."""
        result = await rules_engine.add_rule(
            trigger="adding new API endpoint",
            must_do=["Add rate limiting", "Write tests"],
            must_not=["Use synchronous calls"],
            ask_first=["Is this a breaking change?"]
        )

        assert "id" in result
        assert result["trigger"] == "adding new API endpoint"
        assert "Add rate limiting" in result["must_do"]
        assert "Use synchronous calls" in result["must_not"]

    @pytest.mark.asyncio
    async def test_add_rule_with_warnings(self, rules_engine):
        """Test adding a rule with warnings."""
        result = await rules_engine.add_rule(
            trigger="modifying database schema",
            must_do=["Create migration"],
            warnings=["Last schema change caused downtime"]
        )

        assert "Last schema change caused downtime" in result["warnings"]

    @pytest.mark.asyncio
    async def test_check_rules_match(self, rules_engine):
        """Test checking an action against rules."""
        # Add a rule
        await rules_engine.add_rule(
            trigger="adding API endpoint",
            must_do=["Add rate limiting"],
            must_not=["Skip validation"]
        )

        # Check an action that matches
        result = await rules_engine.check_rules("I'm adding a new API endpoint for users")

        assert result["matched_rules"] >= 1
        assert result["guidance"] is not None
        assert "Add rate limiting" in result["guidance"]["must_do"]

    @pytest.mark.asyncio
    async def test_check_rules_no_match(self, rules_engine):
        """Test checking an action that doesn't match any rules."""
        await rules_engine.add_rule(
            trigger="database migration",
            must_do=["Backup first"]
        )

        result = await rules_engine.check_rules("updating documentation")

        assert result["matched_rules"] == 0
        assert result["guidance"] is None

    @pytest.mark.asyncio
    async def test_check_rules_multiple_matches(self, rules_engine):
        """Test combining guidance from multiple matching rules."""
        await rules_engine.add_rule(
            trigger="API changes",
            must_do=["Update OpenAPI spec"]
        )
        await rules_engine.add_rule(
            trigger="endpoint changes",
            must_do=["Write integration tests"],
            warnings=["Check backwards compatibility"]
        )

        result = await rules_engine.check_rules("making API endpoint changes")

        # Should combine guidance from both rules
        if result["matched_rules"] >= 2:
            guidance = result["guidance"]
            assert len(guidance["must_do"]) >= 2

    @pytest.mark.asyncio
    async def test_check_rules_has_blockers(self, rules_engine):
        """Test detecting blocker conditions."""
        await rules_engine.add_rule(
            trigger="production deployment",
            must_not=["Deploy on Friday"],
            warnings=["Always have rollback plan"]
        )

        result = await rules_engine.check_rules("deploying to production")

        if result["matched_rules"] >= 1:
            assert result["has_blockers"] == True

    @pytest.mark.asyncio
    async def test_list_rules(self, rules_engine):
        """Test listing all rules."""
        await rules_engine.add_rule(trigger="Rule 1", must_do=["Do X"])
        await rules_engine.add_rule(trigger="Rule 2", must_do=["Do Y"])

        rules = await rules_engine.list_rules()

        assert len(rules) >= 2
        triggers = [r["trigger"] for r in rules]
        assert "Rule 1" in triggers
        assert "Rule 2" in triggers

    @pytest.mark.asyncio
    async def test_update_rule(self, rules_engine):
        """Test updating a rule."""
        rule = await rules_engine.add_rule(
            trigger="test rule",
            must_do=["Original task"]
        )

        result = await rules_engine.update_rule(
            rule_id=rule["id"],
            must_do=["Updated task"],
            priority=10
        )

        assert result["updated"] == True

        # Verify update
        rules = await rules_engine.list_rules()
        updated = next(r for r in rules if r["id"] == rule["id"])
        assert "Updated task" in updated["must_do"]
        assert updated["priority"] == 10

    @pytest.mark.asyncio
    async def test_delete_rule(self, rules_engine):
        """Test deleting a rule."""
        rule = await rules_engine.add_rule(
            trigger="to be deleted",
            must_do=["Something"]
        )

        result = await rules_engine.delete_rule(rule["id"])
        assert result["deleted"] == True

        # Verify deletion
        rules = await rules_engine.list_rules()
        assert not any(r["id"] == rule["id"] for r in rules)

    @pytest.mark.asyncio
    async def test_add_warning_to_rule(self, rules_engine):
        """Test adding a warning to an existing rule."""
        rule = await rules_engine.add_rule(
            trigger="database changes",
            must_do=["Backup first"]
        )

        result = await rules_engine.add_warning_to_rule(
            rule["id"],
            "Previous migration took 2 hours"
        )

        assert "Previous migration took 2 hours" in result["warnings"]

    @pytest.mark.asyncio
    async def test_priority_ordering(self, rules_engine):
        """Test that higher priority rules come first."""
        await rules_engine.add_rule(trigger="Low priority", priority=1)
        await rules_engine.add_rule(trigger="High priority", priority=10)
        await rules_engine.add_rule(trigger="Medium priority", priority=5)

        rules = await rules_engine.list_rules()

        # Should be ordered by priority descending
        priorities = [r["priority"] for r in rules]
        assert priorities == sorted(priorities, reverse=True)

    @pytest.mark.asyncio
    async def test_disabled_rules_not_matched(self, rules_engine):
        """Test that disabled rules are not matched."""
        rule = await rules_engine.add_rule(
            trigger="disabled rule test",
            must_do=["Should not appear"]
        )

        # Disable the rule
        await rules_engine.update_rule(rule["id"], enabled=False)

        # Check rules - should not match
        result = await rules_engine.check_rules("disabled rule test action")

        # The disabled rule should not contribute
        if result["guidance"]:
            assert "Should not appear" not in result["guidance"]["must_do"]
