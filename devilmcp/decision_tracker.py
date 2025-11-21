"""
Decision Tracker Module
Tracks AI decisions, rationale, and outcomes to maintain decision history and learning.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
from sqlalchemy import select, update, desc, func, or_

from .database import DatabaseManager
from .models import Decision

logger = logging.getLogger(__name__)


class DecisionTracker:
    """Tracks and manages decision history with full context and rationale."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    async def log_decision(
        self,
        decision: str,
        rationale: str,
        context: Dict,
        alternatives_considered: Optional[List[str]] = None,
        expected_impact: Optional[str] = None,
        risk_level: str = "medium",
        tags: Optional[List[str]] = None
    ) -> Dict:
        """
        Log a decision with full context and rationale.
        """
        async with self.db.get_session() as session:
            new_decision = Decision(
                decision=decision,
                rationale=rationale,
                context=context,
                alternatives_considered=alternatives_considered or [],
                expected_impact=expected_impact,
                risk_level=risk_level,
                tags=tags or [],
                timestamp=datetime.now(timezone.utc)
            )
            session.add(new_decision)
            await session.commit()
            await session.refresh(new_decision)
            
            logger.info(f"Decision logged: {new_decision.id} - {decision}")
            return self._to_dict(new_decision)

    async def update_decision_outcome(
        self,
        decision_id: int,
        outcome: str,
        actual_impact: str,
        lessons_learned: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Update a decision with its actual outcome and impact.
        """
        async with self.db.get_session() as session:
            stmt = select(Decision).where(Decision.id == decision_id)
            result = await session.execute(stmt)
            decision_record = result.scalar_one_or_none()

            if decision_record:
                decision_record.outcome = outcome
                decision_record.actual_impact = actual_impact
                decision_record.lessons_learned = lessons_learned
                decision_record.updated_at = datetime.now(timezone.utc)
                
                await session.commit()
                await session.refresh(decision_record)
                logger.info(f"Decision {decision_id} outcome updated")
                return self._to_dict(decision_record)

        logger.warning(f"Decision {decision_id} not found")
        return None

    async def query_decisions(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        risk_level: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Query decisions by various criteria.
        """
        async with self.db.get_session() as session:
            stmt = select(Decision).order_by(desc(Decision.timestamp))

            if query:
                search = f"%{query}%"
                stmt = stmt.where(
                    or_(
                        Decision.decision.ilike(search),
                        Decision.rationale.ilike(search)
                    )
                )

            if risk_level:
                stmt = stmt.where(Decision.risk_level == risk_level)

            # Tag filtering in SQLite JSON is complex; doing simple fetch-and-filter for now
            # or strict exact match if the user wanted that. 
            # For robust tag filtering, we'd need a separate Tags table or JSON operators.
            # Given SQLite + SQLAlchemy JSON support, we can try simple filtering in Python for tags if needed,
            # but let's stick to SQL for the main parts.
            
            stmt = stmt.limit(limit * 2) # Fetch more to allow python-side tag filtering if needed
            
            result = await session.execute(stmt)
            decisions = result.scalars().all()
            
            filtered_results = []
            for d in decisions:
                if tags:
                    # Python-side tag filtering
                    d_tags = set(d.tags)
                    if not any(tag in d_tags for tag in tags):
                        continue
                filtered_results.append(self._to_dict(d))
                if len(filtered_results) >= limit:
                    break
            
            return filtered_results

    async def analyze_decision_impact(self, decision_id: int) -> Dict:
        """
        Analyze the impact and consequences of a specific decision.
        """
        async with self.db.get_session() as session:
            stmt = select(Decision).where(Decision.id == decision_id)
            result = await session.execute(stmt)
            decision = result.scalar_one_or_none()

            if not decision:
                return {"error": f"Decision {decision_id} not found"}

            # Get all decisions for related analysis
            all_decisions_stmt = select(Decision).where(Decision.id != decision_id)
            all_decisions_result = await session.execute(all_decisions_stmt)
            all_decisions = all_decisions_result.scalars().all()

            analysis = {
                "decision_id": decision_id,
                "decision": decision.decision,
                "timestamp": decision.timestamp.isoformat(),
                "expected_vs_actual": {
                    "expected_impact": decision.expected_impact,
                    "actual_impact": decision.actual_impact,
                    "alignment": self._assess_alignment(
                        decision.expected_impact,
                        decision.actual_impact
                    )
                },
                "risk_assessment": {
                    "initial_risk_level": decision.risk_level,
                    "materialized": decision.outcome is not None
                },
                "related_decisions": self._find_related_decisions(decision, all_decisions),
                "lessons_learned": decision.lessons_learned
            }

            return analysis

    def _assess_alignment(
        self,
        expected: Optional[str],
        actual: Optional[str]
    ) -> str:
        """Assess alignment between expected and actual impact."""
        if not expected or not actual:
            return "unknown"

        expected_words = set(expected.lower().split())
        actual_words = set(actual.lower().split())

        overlap = len(expected_words & actual_words)
        total = len(expected_words | actual_words)

        if total == 0:
            return "unknown"

        alignment_ratio = overlap / total

        if alignment_ratio > 0.7:
            return "high"
        elif alignment_ratio > 0.4:
            return "medium"
        else:
            return "low"

    def _find_related_decisions(self, decision: Decision, all_decisions: List[Decision]) -> List[int]:
        """Find decisions related to the given decision."""
        related = []
        decision_tags = set(decision.tags)
        decision_words = set(decision.decision.lower().split())

        for other in all_decisions:
            # Check tag overlap
            other_tags = set(other.tags)
            if decision_tags & other_tags:
                related.append(other.id)
                continue

            # Check keyword overlap
            other_words = set(other.decision.lower().split())
            overlap = len(decision_words & other_words)

            if overlap >= 3:
                related.append(other.id)

        return related[:5]

    async def get_decision_statistics(self) -> Dict:
        """
        Get statistics about decisions made.
        """
        async with self.db.get_session() as session:
            total_decisions = await session.scalar(select(func.count(Decision.id)))
            
            if total_decisions == 0:
                return {"total_decisions": 0}

            decisions_with_outcomes = await session.scalar(
                select(func.count(Decision.id)).where(Decision.outcome.is_not(None))
            )
            
            # Get all tags to calculate frequency
            all_decisions = await session.execute(select(Decision.tags, Decision.risk_level))
            results = all_decisions.all()
            
            risk_distribution = {}
            tag_frequency = {}
            
            for tags, risk in results:
                risk_distribution[risk] = risk_distribution.get(risk, 0) + 1
                for tag in tags:
                    tag_frequency[tag] = tag_frequency.get(tag, 0) + 1

            last_decision = await session.execute(
                select(Decision.timestamp).order_by(desc(Decision.timestamp)).limit(1)
            )
            last_timestamp = last_decision.scalar_one_or_none()

            return {
                "total_decisions": total_decisions,
                "risk_distribution": risk_distribution,
                "decisions_with_outcomes": decisions_with_outcomes,
                "outcome_tracking_rate": decisions_with_outcomes / total_decisions,
                "top_tags": sorted(tag_frequency.items(), key=lambda x: x[1], reverse=True)[:10],
                "most_recent": last_timestamp.isoformat() if last_timestamp else None
            }

    def _to_dict(self, decision: Decision) -> Dict:
        """Convert SQLAlchemy model to dictionary."""
        return {
            "id": decision.id,
            "decision": decision.decision,
            "rationale": decision.rationale,
            "context": decision.context,
            "alternatives_considered": decision.alternatives_considered,
            "expected_impact": decision.expected_impact,
            "risk_level": decision.risk_level,
            "tags": decision.tags,
            "timestamp": decision.timestamp.isoformat(),
            "outcome": decision.outcome,
            "actual_impact": decision.actual_impact,
            "lessons_learned": decision.lessons_learned,
            "updated_at": decision.updated_at.isoformat() if decision.updated_at else None
        }
