"""Dream strategies for autonomous re-evaluation of past decisions.

DreamStrategy defines the ABC for pluggable dream processing strategies.
FailedDecisionReview is the concrete strategy that queries worked=False
decisions, re-evaluates them against current evidence from memory, and
produces structured DreamResult insights with full provenance.

Design: Lightweight query-compare-insight approach (not full Reflexion).
Each decision is evaluated independently with its own database session
to avoid holding transactions across yield points.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import select

if TYPE_CHECKING:
    from ..context_manager import ProjectContext
    from .scheduler import IdleDreamScheduler

try:
    from ..models import Memory
    from ..config import settings
except ImportError:
    from daem0nmcp.models import Memory
    from daem0nmcp.config import settings

from .persistence import DreamResult, DreamSession, persist_dream_result


class DreamStrategy(ABC):
    """Base class for dream processing strategies.

    Subclasses implement execute() which populates the session with
    DreamResult entries. Strategies must check scheduler.user_active
    at yield points and break immediately if the user returns.
    """

    @abstractmethod
    async def execute(
        self,
        session: DreamSession,
        ctx: "ProjectContext",
        scheduler: "IdleDreamScheduler",
    ) -> DreamSession:
        """Execute the strategy, populating session.results.

        Args:
            session: The DreamSession to populate with results.
            ctx: ProjectContext with db_manager and memory_manager.
            scheduler: IdleDreamScheduler for cooperative yield checks.

        Returns:
            The updated DreamSession.
        """
        ...


class FailedDecisionReview(DreamStrategy):
    """Re-evaluates worked=False decisions against current evidence.

    For each failed decision:
    1. Query memory for current evidence related to the decision
    2. Compare: does newer evidence suggest revision, or confirm failure?
    3. Produce a DreamResult with structured insight and provenance
    4. Persist insights (except needs_more_data) as learning memories

    Cooperative yielding: checks scheduler.user_active.is_set() before
    each decision and breaks immediately if the user returns.
    """

    def __init__(
        self,
        max_decisions: Optional[int] = None,
        min_age_hours: Optional[int] = None,
    ):
        self._max_decisions = max_decisions or settings.dream_max_decisions_per_session
        self._min_age_hours = min_age_hours or settings.dream_min_decision_age_hours
        self._logger = logging.getLogger(__name__)

    async def execute(
        self,
        session: DreamSession,
        ctx: "ProjectContext",
        scheduler: "IdleDreamScheduler",
    ) -> DreamSession:
        """Execute the FailedDecisionReview strategy.

        Fetches failed decisions, re-evaluates each against current
        evidence, and persists actionable insights.
        """
        self._logger.info(
            "Dream session %s: Starting FailedDecisionReview", session.session_id
        )

        decisions = await self._get_failed_decisions(ctx)

        if not decisions:
            self._logger.info("No failed decisions to review")
            return session

        for decision in decisions:
            # YIELD CHECKPOINT: break immediately if user returns
            if scheduler.user_active.is_set():
                session.interrupted = True
                break

            session.decisions_reviewed += 1

            result = await self._re_evaluate_decision(decision, ctx)
            session.results.append(result)

            if result.result_type != "needs_more_data":
                await persist_dream_result(ctx.memory_manager, result, session)
                session.insights_generated += 1

            # COOPERATIVE YIELD: give event loop a tick
            await asyncio.sleep(0)

        return session

    async def _get_failed_decisions(
        self, ctx: "ProjectContext"
    ) -> List[Any]:
        """Query worked=False decisions from the database.

        Uses its own database session (not held open across the
        decision processing loop) to avoid transaction timeouts.

        Filters:
        - worked == False
        - archived == False
        - created_at < age_cutoff (skip too-recent decisions)
        - Ordered by most recent first, limited to max_decisions
        """
        try:
            age_cutoff = datetime.now(timezone.utc) - timedelta(
                hours=self._min_age_hours
            )
            async with ctx.db_manager.get_session() as db_session:
                result = await db_session.execute(
                    select(Memory)
                    .where(Memory.worked == False)  # noqa: E712
                    .where(Memory.archived == False)  # noqa: E712
                    .where(Memory.created_at < age_cutoff)
                    .order_by(Memory.created_at.desc())
                    .limit(self._max_decisions)
                )
                return result.scalars().all()
        except Exception as e:
            self._logger.warning("Failed to query failed decisions: %s", e)
            return []

    async def _re_evaluate_decision(
        self, decision: Any, ctx: "ProjectContext"
    ) -> DreamResult:
        """Re-evaluate a single failed decision against current evidence.

        Steps:
        1. Use the decision content as a search query
        2. Recall current evidence via memory_manager.recall()
        3. Analyze evidence to determine result_type
        4. Build structured DreamResult with provenance

        Returns:
            DreamResult with result_type in {revised, confirmed_failure,
            needs_more_data} and an insight string summarizing findings.
        """
        try:
            # Use first 200 chars of decision as search query
            query = decision.content[:200]

            # Gather current evidence from memory
            evidence = await ctx.memory_manager.recall(
                query, limit=5, project_path=ctx.project_path
            )

            # Extract evidence summaries across all categories
            evidence_items: List[Dict[str, Any]] = []
            evidence_ids: List[int] = []

            for category_key in ("decisions", "patterns", "learnings", "warnings"):
                for mem in evidence.get(category_key, []):
                    # Skip the decision itself
                    if mem.get("id") == decision.id:
                        continue
                    evidence_items.append(mem)
                    evidence_ids.append(mem["id"])
                    if len(evidence_items) >= 5:
                        break
                if len(evidence_items) >= 5:
                    break

            # Determine result_type based on evidence
            has_worked_evidence = any(
                mem.get("worked") is True for mem in evidence_items
            )

            if has_worked_evidence:
                result_type = "revised"
                evidence_summary = (
                    f"Found {len(evidence_items)} related memories, including "
                    f"successful approaches that suggest the original failure "
                    f"may be addressable with current knowledge."
                )
            elif len(evidence_items) < 2:
                result_type = "needs_more_data"
                evidence_summary = (
                    f"Only {len(evidence_items)} related memories found "
                    f"(excluding the decision itself). Insufficient evidence "
                    f"for re-evaluation."
                )
            else:
                result_type = "confirmed_failure"
                evidence_summary = (
                    f"Found {len(evidence_items)} related memories. Available "
                    f"evidence still supports the original failure assessment."
                )

            # Build insight text
            content_preview = decision.content[:80]
            insight = (
                f"Re-evaluated decision #{decision.id}: "
                f"'{content_preview}...' -- {result_type}. {evidence_summary}"
            )

            return DreamResult(
                source_decision_id=decision.id,
                original_content=decision.content[:200],
                original_outcome=decision.outcome,
                insight=insight,
                result_type=result_type,
                evidence_ids=evidence_ids,
            )

        except Exception as e:
            self._logger.warning(
                "Error re-evaluating decision #%d: %s", decision.id, e
            )
            return DreamResult(
                source_decision_id=decision.id,
                original_content=getattr(decision, "content", "")[:200],
                original_outcome=getattr(decision, "outcome", None),
                insight=f"Error during re-evaluation of decision #{decision.id}: {e}",
                result_type="needs_more_data",
                evidence_ids=[],
            )
