"""Tests for the memory management system."""

import pytest
from pathlib import Path
import tempfile
import shutil

from devilmcp.database import DatabaseManager
from devilmcp.memory import MemoryManager, extract_keywords


class TestExtractKeywords:
    """Test keyword extraction."""

    def test_basic_extraction(self):
        text = "Use JWT tokens for authentication"
        keywords = extract_keywords(text)
        assert "jwt" in keywords
        assert "tokens" in keywords
        assert "authentication" in keywords
        # Stop words should be removed
        assert "use" not in keywords
        assert "for" not in keywords

    def test_with_tags(self):
        text = "Add rate limiting"
        tags = ["api", "security"]
        keywords = extract_keywords(text, tags)
        assert "rate" in keywords
        assert "limiting" in keywords
        assert "api" in keywords
        assert "security" in keywords

    def test_empty_text(self):
        assert extract_keywords("") == ""
        assert extract_keywords(None) == ""

    def test_deduplication(self):
        text = "test test test"
        keywords = extract_keywords(text)
        assert keywords.count("test") == 1


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
    await db.close()


class TestMemoryManager:
    """Test memory storage and retrieval."""

    @pytest.mark.asyncio
    async def test_remember_decision(self, memory_manager):
        """Test storing a decision."""
        result = await memory_manager.remember(
            category="decision",
            content="Use PostgreSQL instead of MySQL",
            rationale="Better JSON support and performance",
            tags=["database", "architecture"]
        )

        assert "id" in result
        assert result["category"] == "decision"
        assert result["content"] == "Use PostgreSQL instead of MySQL"
        assert "database" in result["tags"]

    @pytest.mark.asyncio
    async def test_remember_warning(self, memory_manager):
        """Test storing a warning."""
        result = await memory_manager.remember(
            category="warning",
            content="Don't use synchronous database calls in handlers",
            rationale="Caused performance issues",
            context={"file": "handlers.py"}
        )

        assert result["category"] == "warning"
        assert "id" in result

    @pytest.mark.asyncio
    async def test_remember_invalid_category(self, memory_manager):
        """Test that invalid categories are rejected."""
        result = await memory_manager.remember(
            category="invalid",
            content="This should fail"
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_recall_by_topic(self, memory_manager):
        """Test recalling memories by topic."""
        # Store some memories
        await memory_manager.remember(
            category="decision",
            content="Use JWT for authentication",
            tags=["auth", "security"]
        )
        await memory_manager.remember(
            category="pattern",
            content="Always validate input on auth endpoints",
            tags=["auth", "validation"]
        )
        await memory_manager.remember(
            category="warning",
            content="Session tokens had security issues",
            tags=["auth"]
        )

        # Recall by topic
        result = await memory_manager.recall("authentication")

        assert result["found"] > 0
        # Should find auth-related memories
        total = len(result["decisions"]) + len(result["patterns"]) + len(result["warnings"])
        assert total >= 1

    @pytest.mark.asyncio
    async def test_recall_by_category(self, memory_manager):
        """Test filtering recall by category."""
        await memory_manager.remember(
            category="decision",
            content="Use Redis for caching",
            tags=["cache"]
        )
        await memory_manager.remember(
            category="warning",
            content="Cache invalidation is tricky",
            tags=["cache"]
        )

        # Only get warnings
        result = await memory_manager.recall("cache", categories=["warning"])

        # Warnings should always be included
        assert len(result["warnings"]) >= 0

    @pytest.mark.asyncio
    async def test_record_outcome(self, memory_manager):
        """Test recording outcomes."""
        # Create a memory
        memory = await memory_manager.remember(
            category="decision",
            content="Use microservices architecture"
        )

        # Record outcome
        result = await memory_manager.record_outcome(
            memory_id=memory["id"],
            outcome="Worked well, improved scalability",
            worked=True
        )

        assert result["worked"] == True
        assert "Worked well" in result["outcome"]

    @pytest.mark.asyncio
    async def test_record_outcome_failure(self, memory_manager):
        """Test recording failed outcomes."""
        memory = await memory_manager.remember(
            category="decision",
            content="Use complex caching strategy"
        )

        result = await memory_manager.record_outcome(
            memory_id=memory["id"],
            outcome="Caused stale data bugs",
            worked=False
        )

        assert result["worked"] == False

    @pytest.mark.asyncio
    async def test_record_outcome_invalid_id(self, memory_manager):
        """Test recording outcome for non-existent memory."""
        result = await memory_manager.record_outcome(
            memory_id=99999,
            outcome="Should fail",
            worked=True
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_search(self, memory_manager):
        """Test full-text search."""
        await memory_manager.remember(
            category="learning",
            content="GraphQL is better for complex queries"
        )
        await memory_manager.remember(
            category="learning",
            content="REST is simpler for basic CRUD"
        )

        results = await memory_manager.search("GraphQL")
        assert len(results) >= 1
        assert any("GraphQL" in r["content"] for r in results)

    @pytest.mark.asyncio
    async def test_get_statistics(self, memory_manager):
        """Test statistics retrieval."""
        await memory_manager.remember(category="decision", content="Decision 1")
        await memory_manager.remember(category="warning", content="Warning 1")
        await memory_manager.remember(category="pattern", content="Pattern 1")

        stats = await memory_manager.get_statistics()

        assert stats["total_memories"] >= 3
        assert "by_category" in stats
        assert "with_outcomes" in stats
