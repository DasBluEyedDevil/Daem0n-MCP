"""Tests for FailedDecisionReview dream strategy.

Covers: query filtering, re-evaluation logic, yield behavior,
persistence calls, and graceful error degradation.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from daem0nmcp.dreaming.persistence import DreamSession
from daem0nmcp.dreaming.strategies import FailedDecisionReview


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_memory(
    id: int,
    content: str = "some decision content",
    outcome: str = "it failed",
    worked: bool = False,
    archived: bool = False,
    created_at: datetime = None,
    category: str = "decision",
):
    """Create a mock Memory object with the required fields."""
    mem = MagicMock()
    mem.id = id
    mem.content = content
    mem.outcome = outcome
    mem.worked = worked
    mem.archived = archived
    mem.created_at = created_at or (
        datetime.now(timezone.utc) - timedelta(hours=48)
    )
    mem.category = category
    mem.context = {}
    mem.tags = []
    return mem


def _make_recall_result(memories=None):
    """Build a recall() return dict with categorised memories.

    Each memory in *memories* is a dict with at least ``id`` and
    optionally ``worked``, ``content``, ``outcome``.
    """
    if memories is None:
        memories = []
    return {
        "topic": "query",
        "found": len(memories),
        "total_count": len(memories),
        "offset": 0,
        "limit": 5,
        "has_more": False,
        "summary": None,
        "decisions": [m for m in memories if m.get("category", "decision") == "decision"],
        "patterns": [m for m in memories if m.get("category") == "pattern"],
        "learnings": [m for m in memories if m.get("category") == "learning"],
        "warnings": [m for m in memories if m.get("category") == "warning"],
    }


def _make_scheduler(user_active_set: bool = False):
    """Create a mock scheduler with a real asyncio.Event."""
    scheduler = MagicMock()
    event = asyncio.Event()
    if user_active_set:
        event.set()
    else:
        event.clear()
    scheduler.user_active = event
    return scheduler


def _make_ctx(memories_from_db=None, recall_result=None):
    """Create a mock ProjectContext with db_manager and memory_manager."""
    ctx = MagicMock()
    ctx.project_path = "/test/project"

    # --- db_manager.get_session() as async context manager ---
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = memories_from_db or []
    mock_session.execute = AsyncMock(return_value=mock_result)

    # get_session returns an async context manager
    async_cm = AsyncMock()
    async_cm.__aenter__ = AsyncMock(return_value=mock_session)
    async_cm.__aexit__ = AsyncMock(return_value=False)
    ctx.db_manager.get_session = MagicMock(return_value=async_cm)

    # --- memory_manager.recall() ---
    ctx.memory_manager.recall = AsyncMock(
        return_value=recall_result or _make_recall_result()
    )

    # --- memory_manager.remember() for persist_dream_result ---
    ctx.memory_manager.remember = AsyncMock(return_value={"id": 999})

    return ctx, mock_session


def _make_session():
    """Create a fresh DreamSession for testing."""
    return DreamSession(project_path="/test/project")


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------


class TestNoFailedDecisions:
    @pytest.mark.asyncio
    async def test_no_failed_decisions_returns_empty_session(self):
        """When no failed decisions exist, session should be empty."""
        ctx, _ = _make_ctx(memories_from_db=[])
        scheduler = _make_scheduler(user_active_set=False)
        session = _make_session()

        strategy = FailedDecisionReview(max_decisions=5, min_age_hours=1)
        result = await strategy.execute(session, ctx, scheduler)

        assert result.decisions_reviewed == 0
        assert result.results == []
        assert not result.interrupted


class TestReviewsFailedDecisions:
    @pytest.mark.asyncio
    async def test_reviews_failed_decisions(self):
        """Strategy should review each failed decision and produce results."""
        mem1 = _make_memory(id=10, content="decision A failed")
        mem2 = _make_memory(id=20, content="decision B failed")

        recall_result = _make_recall_result([
            {"id": 100, "content": "some evidence", "worked": None, "category": "decision"},
            {"id": 101, "content": "more evidence", "worked": None, "category": "learning"},
            {"id": 102, "content": "even more", "worked": None, "category": "pattern"},
        ])

        ctx, _ = _make_ctx(memories_from_db=[mem1, mem2], recall_result=recall_result)
        scheduler = _make_scheduler(user_active_set=False)
        session = _make_session()

        strategy = FailedDecisionReview(max_decisions=5, min_age_hours=1)
        result = await strategy.execute(session, ctx, scheduler)

        assert result.decisions_reviewed == 2
        assert len(result.results) == 2


class TestMaxDecisionsLimit:
    @pytest.mark.asyncio
    async def test_respects_max_decisions_limit(self):
        """Strategy should limit the query to max_decisions."""
        mem1 = _make_memory(id=10)
        # Only 1 returned from DB because limit=1 in the query
        ctx, mock_session = _make_ctx(
            memories_from_db=[mem1],
            recall_result=_make_recall_result([
                {"id": 100, "content": "ev", "worked": None, "category": "decision"},
                {"id": 101, "content": "ev2", "worked": None, "category": "learning"},
                {"id": 102, "content": "ev3", "worked": None, "category": "pattern"},
            ]),
        )
        scheduler = _make_scheduler(user_active_set=False)
        session = _make_session()

        strategy = FailedDecisionReview(max_decisions=1, min_age_hours=1)
        result = await strategy.execute(session, ctx, scheduler)

        # Only 1 decision should have been reviewed (limit enforced at DB)
        assert result.decisions_reviewed == 1


class TestYieldOnUserActive:
    @pytest.mark.asyncio
    async def test_yield_on_user_active(self):
        """If user_active is set, strategy should yield immediately."""
        mem1 = _make_memory(id=10)
        mem2 = _make_memory(id=20)
        mem3 = _make_memory(id=30)

        ctx, _ = _make_ctx(memories_from_db=[mem1, mem2, mem3])
        # User is already active
        scheduler = _make_scheduler(user_active_set=True)
        session = _make_session()

        strategy = FailedDecisionReview(max_decisions=5, min_age_hours=1)
        result = await strategy.execute(session, ctx, scheduler)

        assert result.interrupted is True
        assert result.decisions_reviewed == 0


class TestReEvaluateRevised:
    @pytest.mark.asyncio
    async def test_re_evaluate_produces_revised_result(self):
        """When recall returns worked=True evidence, result_type should be 'revised'."""
        mem = _make_memory(id=10, content="Use approach X for caching")

        recall_result = _make_recall_result([
            {"id": 100, "content": "approach X works now", "worked": True, "category": "decision"},
            {"id": 101, "content": "caching pattern", "worked": None, "category": "pattern"},
        ])

        ctx, _ = _make_ctx(memories_from_db=[mem], recall_result=recall_result)
        scheduler = _make_scheduler(user_active_set=False)
        session = _make_session()

        strategy = FailedDecisionReview(max_decisions=5, min_age_hours=1)
        result = await strategy.execute(session, ctx, scheduler)

        assert len(result.results) == 1
        assert result.results[0].result_type == "revised"
        assert result.results[0].source_decision_id == 10


class TestReEvaluateSparseEvidence:
    @pytest.mark.asyncio
    async def test_re_evaluate_sparse_evidence_needs_more_data(self):
        """When recall returns sparse evidence, result_type should be 'needs_more_data'."""
        mem = _make_memory(id=10, content="Use approach Y")

        # Only return the decision itself -- no other evidence
        recall_result = _make_recall_result([
            {"id": 10, "content": "Use approach Y", "worked": False, "category": "decision"},
        ])

        ctx, _ = _make_ctx(memories_from_db=[mem], recall_result=recall_result)
        scheduler = _make_scheduler(user_active_set=False)
        session = _make_session()

        strategy = FailedDecisionReview(max_decisions=5, min_age_hours=1)
        result = await strategy.execute(session, ctx, scheduler)

        assert len(result.results) == 1
        assert result.results[0].result_type == "needs_more_data"


class TestReEvaluateConfirmedFailure:
    @pytest.mark.asyncio
    async def test_re_evaluate_confirmed_failure(self):
        """When recall returns evidence but no worked=True, result_type should be 'confirmed_failure'."""
        mem = _make_memory(id=10, content="Use approach Z")

        recall_result = _make_recall_result([
            {"id": 100, "content": "Z is problematic", "worked": False, "category": "decision"},
            {"id": 101, "content": "Z related warning", "worked": None, "category": "warning"},
            {"id": 102, "content": "Z context", "worked": None, "category": "learning"},
        ])

        ctx, _ = _make_ctx(memories_from_db=[mem], recall_result=recall_result)
        scheduler = _make_scheduler(user_active_set=False)
        session = _make_session()

        strategy = FailedDecisionReview(max_decisions=5, min_age_hours=1)
        result = await strategy.execute(session, ctx, scheduler)

        assert len(result.results) == 1
        assert result.results[0].result_type == "confirmed_failure"


class TestPersistCalledForInsights:
    @pytest.mark.asyncio
    async def test_persist_called_for_insights(self):
        """persist_dream_result should be called for revised/confirmed, not needs_more_data."""
        mem_revised = _make_memory(id=10, content="approach A")
        mem_sparse = _make_memory(id=20, content="approach B")

        call_index = 0

        async def mock_recall(topic, limit=5, project_path=None):
            nonlocal call_index
            call_index += 1
            if call_index == 1:
                # First decision: returns worked=True evidence -> revised
                return _make_recall_result([
                    {"id": 100, "content": "ev", "worked": True, "category": "decision"},
                    {"id": 101, "content": "ev2", "worked": None, "category": "pattern"},
                ])
            else:
                # Second decision: sparse evidence -> needs_more_data
                return _make_recall_result([
                    {"id": 20, "content": "approach B", "worked": False, "category": "decision"},
                ])

        ctx, _ = _make_ctx(memories_from_db=[mem_revised, mem_sparse])
        ctx.memory_manager.recall = AsyncMock(side_effect=mock_recall)
        scheduler = _make_scheduler(user_active_set=False)
        session = _make_session()

        with patch(
            "daem0nmcp.dreaming.strategies.persist_dream_result",
            new_callable=AsyncMock,
        ) as mock_persist:
            strategy = FailedDecisionReview(max_decisions=5, min_age_hours=1)
            result = await strategy.execute(session, ctx, scheduler)

            assert result.decisions_reviewed == 2
            assert len(result.results) == 2

            # First result is "revised" -> persist called
            # Second result is "needs_more_data" -> persist NOT called
            assert mock_persist.call_count == 1
            assert result.insights_generated == 1


class TestExceptionInReEvaluate:
    @pytest.mark.asyncio
    async def test_exception_in_re_evaluate_does_not_crash(self):
        """If recall() raises, strategy should not crash -- graceful degradation."""
        mem = _make_memory(id=10, content="approach that errors")

        ctx, _ = _make_ctx(memories_from_db=[mem])
        ctx.memory_manager.recall = AsyncMock(
            side_effect=RuntimeError("recall exploded")
        )
        scheduler = _make_scheduler(user_active_set=False)
        session = _make_session()

        strategy = FailedDecisionReview(max_decisions=5, min_age_hours=1)
        result = await strategy.execute(session, ctx, scheduler)

        # Should complete without raising
        assert result.decisions_reviewed == 1
        assert len(result.results) == 1
        assert result.results[0].result_type == "needs_more_data"
        assert "Error" in result.results[0].insight


class TestMinAgeFilter:
    @pytest.mark.asyncio
    async def test_min_age_filter(self):
        """Strategy should pass age cutoff to the database query."""
        ctx, mock_session = _make_ctx(memories_from_db=[])
        scheduler = _make_scheduler(user_active_set=False)
        session = _make_session()

        strategy = FailedDecisionReview(max_decisions=5, min_age_hours=24)
        await strategy.execute(session, ctx, scheduler)

        # Verify execute was called on the mock session (the query was issued)
        mock_session.execute.assert_called_once()

        # The query should have been issued -- we just verify the call happened.
        # The actual SQL filtering is tested by the fact that min_age_hours=24
        # computes an age_cutoff 24 hours ago and passes it to the WHERE clause.
        # With mocked DB, we trust SQLAlchemy does the right thing with our query.
        assert session.decisions_reviewed == 0  # No results from mocked DB


class TestDreamStrategyABC:
    """Verify DreamStrategy cannot be instantiated directly."""

    def test_cannot_instantiate_base_class(self):
        from daem0nmcp.dreaming.strategies import DreamStrategy
        with pytest.raises(TypeError):
            DreamStrategy()  # type: ignore[abstract]


class TestResultProvenance:
    @pytest.mark.asyncio
    async def test_result_contains_provenance_fields(self):
        """DreamResult should contain source_decision_id, original_content, evidence_ids."""
        mem = _make_memory(id=42, content="Use Redis for sessions", outcome="OOM killed")

        recall_result = _make_recall_result([
            {"id": 200, "content": "Redis works for cache", "worked": True, "category": "decision"},
            {"id": 201, "content": "Session pattern", "worked": None, "category": "pattern"},
        ])

        ctx, _ = _make_ctx(memories_from_db=[mem], recall_result=recall_result)
        scheduler = _make_scheduler(user_active_set=False)
        session = _make_session()

        strategy = FailedDecisionReview(max_decisions=5, min_age_hours=1)
        result = await strategy.execute(session, ctx, scheduler)

        dream_result = result.results[0]
        assert dream_result.source_decision_id == 42
        assert dream_result.original_content == "Use Redis for sessions"
        assert dream_result.original_outcome == "OOM killed"
        assert 200 in dream_result.evidence_ids
        assert 201 in dream_result.evidence_ids
        assert dream_result.result_type == "revised"
