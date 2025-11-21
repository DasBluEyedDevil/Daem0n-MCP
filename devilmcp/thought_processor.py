"""
Thought Processor Module
Manages AI thought processes, reasoning chains, and cognitive context.
"""

import logging
from typing import Dict, List, Optional, Set
from datetime import datetime, timezone
from sqlalchemy import select, update, desc, func

from .database import DatabaseManager
from .models import Thought, ThoughtSession, Insight

logger = logging.getLogger(__name__)


class ThoughtProcessor:
    """Manages thought processes and reasoning chains for AI agents."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.active_session_id = None

    async def start_session(self, session_id: str, context: Dict) -> Dict:
        """
        Start a new thought processing session.
        """
        async with self.db.get_session() as session:
            # Check if exists
            stmt = select(ThoughtSession).where(ThoughtSession.id == session_id)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # If restarting an existing session, just update status
                existing.status = "active"
                # existing.started_at = datetime.now(timezone.utc) # Keep original start time? or update?
                # Let's keep original start time, maybe update context if provided
                if context:
                    existing.context = context
            else:
                new_session = ThoughtSession(
                    id=session_id,
                    context=context,
                    started_at=datetime.now(timezone.utc),
                    status="active",
                    outcomes=[],
                    summary=None
                )
                session.add(new_session)

            await session.commit()
            
            self.active_session_id = session_id
            logger.info(f"Started thought session: {session_id}")
            
            return {
                "id": session_id,
                "context": context,
                "status": "active",
                "started_at": datetime.now(timezone.utc).isoformat()
            }

    async def end_session(
        self,
        session_id: str,
        summary: Optional[str] = None,
        outcomes: Optional[List[str]] = None
    ) -> Dict:
        """
        End a thought processing session.
        """
        async with self.db.get_session() as session:
            stmt = select(ThoughtSession).where(ThoughtSession.id == session_id)
            result = await session.execute(stmt)
            thought_session = result.scalar_one_or_none()

            if not thought_session:
                return {"error": f"Session {session_id} not found"}

            thought_session.status = "completed"
            thought_session.ended_at = datetime.now(timezone.utc)
            thought_session.summary = summary
            thought_session.outcomes = outcomes or []

            if self.active_session_id == session_id:
                self.active_session_id = None

            await session.commit()
            await session.refresh(thought_session)

            logger.info(f"Ended thought session: {session_id}")
            return self._session_to_dict(thought_session)

    async def log_thought_process(
        self,
        thought: str,
        category: str,
        reasoning: str,
        related_to: Optional[List[str]] = None,
        confidence: Optional[float] = None,
        session_id: Optional[str] = None
    ) -> Dict:
        """
        Log a thought process with reasoning.
        """
        target_session_id = session_id or self.active_session_id
        
        async with self.db.get_session() as session:
            new_thought = Thought(
                thought=thought,
                category=category,
                reasoning=reasoning,
                related_to=related_to or [],
                confidence=confidence,
                timestamp=datetime.now(timezone.utc),
                session_id=target_session_id
            )
            session.add(new_thought)
            await session.commit()
            await session.refresh(new_thought)

            logger.info(f"Thought logged: {new_thought.id} - {category}")
            return self._thought_to_dict(new_thought)

    async def retrieve_thought_context(
        self,
        thought_id: Optional[int] = None,
        category: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Retrieve related thought context.
        """
        async with self.db.get_session() as session:
            results = []

            if thought_id:
                stmt = select(Thought).where(Thought.id == thought_id)
                result = await session.execute(stmt)
                target_thought = result.scalar_one_or_none()

                if target_thought:
                    results.append(self._thought_to_dict(target_thought))
                    
                    # Get related thoughts
                    related_ids = target_thought.related_to or []
                    # Filter out non-int IDs just in case
                    valid_ids = [rid for rid in related_ids if isinstance(rid, int)]
                    
                    if valid_ids:
                        stmt_rel = select(Thought).where(Thought.id.in_(valid_ids))
                        res_rel = await session.execute(stmt_rel)
                        for rel in res_rel.scalars():
                            results.append(self._thought_to_dict(rel))
            else:
                stmt = select(Thought).order_by(desc(Thought.timestamp))
                
                if category:
                    stmt = stmt.where(Thought.category == category)
                
                if session_id:
                    stmt = stmt.where(Thought.session_id == session_id)
                
                stmt = stmt.limit(limit)
                result = await session.execute(stmt)
                for t in result.scalars():
                    results.append(self._thought_to_dict(t))

            return results

    async def analyze_reasoning_gaps(self, session_id: Optional[str] = None) -> Dict:
        """
        Analyze gaps in reasoning or considerations.
        """
        target_session = session_id or self.active_session_id

        if not target_session:
            return {"error": "No session specified or active"}

        async with self.db.get_session() as session:
            # Check session exists
            sess_stmt = select(ThoughtSession).where(ThoughtSession.id == target_session)
            res = await session.execute(sess_stmt)
            if not res.scalar_one_or_none():
                return {"error": f"Session {target_session} not found"}

            # Get thoughts
            stmt = select(Thought).where(Thought.session_id == target_session)
            result = await session.execute(stmt)
            session_thoughts = result.scalars().all()

        analysis = {
            "session_id": target_session,
            "total_thoughts": len(session_thoughts),
            "categories_covered": set(),
            "gaps": [],
            "suggestions": []
        }

        # Analyze category coverage
        for thought in session_thoughts:
            analysis["categories_covered"].add(thought.category)

        analysis["categories_covered"] = list(analysis["categories_covered"])

        # Check for common gaps
        important_categories = {
            "analysis", "hypothesis", "concern", "validation",
            "alternative", "constraint", "risk"
        }

        missing_categories = important_categories - set(analysis["categories_covered"])

        if "concern" not in analysis["categories_covered"]:
            analysis["gaps"].append("No concerns raised - potential blind spots")
            analysis["suggestions"].append("Consider potential risks and edge cases")

        if "alternative" not in analysis["categories_covered"]:
            analysis["gaps"].append("No alternatives considered")
            analysis["suggestions"].append("Explore alternative approaches")

        if "validation" not in analysis["categories_covered"]:
            analysis["gaps"].append("No validation steps identified")
            analysis["suggestions"].append("Define how to validate the approach")

        if "risk" not in analysis["categories_covered"]:
            analysis["gaps"].append("Risk assessment not performed")
            analysis["suggestions"].append("Assess potential risks and mitigation strategies")

        # Check for low confidence thoughts
        low_confidence_thoughts = [
            t for t in session_thoughts
            if (t.confidence is not None and t.confidence < 0.6)
        ]

        if low_confidence_thoughts:
            analysis["gaps"].append(
                f"{len(low_confidence_thoughts)} low-confidence thoughts without resolution"
            )
            analysis["suggestions"].append(
                "Investigate low-confidence areas more thoroughly"
            )

        # Check reasoning chain completeness
        unlinked_thoughts = [
            t for t in session_thoughts
            if not t.related_to
        ]

        if len(session_thoughts) > 0 and (len(unlinked_thoughts) / len(session_thoughts) > 0.5):
            analysis["gaps"].append("Many thoughts not connected to reasoning chain")
            analysis["suggestions"].append(
                "Link related thoughts to build coherent reasoning"
            )

        return analysis

    async def record_insight(
        self,
        insight: str,
        source: str,
        applicability: str,
        session_id: Optional[str] = None
    ) -> Dict:
        """
        Record an insight gained during processing.
        """
        target_session = session_id or self.active_session_id

        async with self.db.get_session() as session:
            new_insight = Insight(
                insight=insight,
                source=source,
                applicability=applicability,
                session_id=target_session,
                timestamp=datetime.now(timezone.utc)
            )
            session.add(new_insight)
            await session.commit()
            await session.refresh(new_insight)

            logger.info(f"Insight recorded: {insight}")
            return self._insight_to_dict(new_insight)

    async def query_insights(
        self,
        query: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Query recorded insights.
        """
        async with self.db.get_session() as session:
            stmt = select(Insight).order_by(desc(Insight.timestamp))
            
            if query:
                # Basic Python-side filtering for now or use SQL 'LIKE'
                # Let's use SQL LIKE for efficiency
                search = f"%{query}%"
                # Note: 'applicability' and 'insight' are text fields
                from sqlalchemy import or_
                stmt = stmt.where(or_(
                    Insight.insight.ilike(search),
                    Insight.applicability.ilike(search)
                ))
            
            stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            
            return [self._insight_to_dict(i) for i in result.scalars()]

    async def build_reasoning_chain(
        self,
        start_thought_id: int,
        max_depth: int = 10
    ) -> Dict:
        """
        Build a complete reasoning chain from a starting thought.
        """
        async with self.db.get_session() as session:
            stmt = select(Thought).where(Thought.id == start_thought_id)
            result = await session.execute(stmt)
            start_thought = result.scalar_one_or_none()

            if not start_thought:
                return {"error": f"Thought {start_thought_id} not found"}

            chain_list = []
            visited = set()
            
            # We need to do recursion. Since we are inside an async function but need
            # to fetch data possibly deeply, let's just fetch thoughts as we need them.
            
            await self._build_chain_recursive(session, start_thought, chain_list, visited, 0, max_depth)

            return {
                "start": self._thought_to_dict(start_thought),
                "chain": chain_list,
                "depth": len(chain_list),
                "total_thoughts": len(set(t["id"] for t in chain_list))
            }

    async def _build_chain_recursive(
        self,
        session,
        thought: Thought,
        chain: List,
        visited: Set,
        current_depth: int,
        max_depth: int
    ):
        if current_depth >= max_depth or thought.id in visited:
            return

        visited.add(thought.id)
        chain.append(self._thought_to_dict(thought))

        related_ids = thought.related_to or []
        valid_ids = [rid for rid in related_ids if isinstance(rid, int)]
        
        if valid_ids:
            stmt = select(Thought).where(Thought.id.in_(valid_ids))
            result = await session.execute(stmt)
            for related in result.scalars():
                await self._build_chain_recursive(
                    session, related, chain, visited, current_depth + 1, max_depth
                )

    async def get_session_summary(self, session_id: str) -> Dict:
        """
        Get comprehensive summary of a session.
        """
        async with self.db.get_session() as session:
            # Get Session
            stmt = select(ThoughtSession).where(ThoughtSession.id == session_id)
            result = await session.execute(stmt)
            ts = result.scalar_one_or_none()
            
            if not ts:
                return {"error": f"Session {session_id} not found"}

            # Get Thoughts
            stmt_t = select(Thought).where(Thought.session_id == session_id)
            result_t = await session.execute(stmt_t)
            thoughts = result_t.scalars().all()
            
            # Get Insights
            stmt_i = select(Insight).where(Insight.session_id == session_id)
            result_i = await session.execute(stmt_i)
            insights = result_i.scalars().all()

            # Process Stats
            by_category = {}
            for t in thoughts:
                by_category.setdefault(t.category, []).append(self._thought_to_dict(t))

            concerns = [t["thought"] for t in by_category.get("concern", [])][:5]

            return {
                "session_id": session_id,
                "status": ts.status,
                "duration": self._calculate_duration(ts.started_at, ts.ended_at),
                "total_thoughts": len(thoughts),
                "by_category": {k: len(v) for k, v in by_category.items()},
                "total_insights": len(insights),
                "key_concerns": concerns,
                "outcomes": ts.outcomes,
                "summary": ts.summary
            }

    def _calculate_duration(
        self,
        start: Optional[datetime],
        end: Optional[datetime]
    ) -> Optional[str]:
        """Calculate duration between two timestamps."""
        if not start:
            return None
        
        # Ensure start is timezone-aware (UTC) if it's naive
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)

        # Ensure end is timezone-aware (UTC) if provided and naive
        if end and end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        
        end_dt = end or datetime.now(timezone.utc)
        return str(end_dt - start)

    async def get_thought_statistics(self) -> Dict:
        """
        Get statistics about thought processes.
        """
        async with self.db.get_session() as session:
            total_thoughts = await session.scalar(select(func.count(Thought.id)))
            
            if total_thoughts == 0:
                return {"total_thoughts": 0}

            total_sessions = await session.scalar(select(func.count(ThoughtSession.id)))
            total_insights = await session.scalar(select(func.count(Insight.id)))
            
            # Category distribution
            stmt = select(Thought.category, func.count(Thought.id)).group_by(Thought.category)
            res = await session.execute(stmt)
            category_dist = {row[0]: row[1] for row in res.all()}
            
            # Avg confidence
            avg_conf = await session.scalar(select(func.avg(Thought.confidence)))

            return {
                "total_thoughts": total_thoughts,
                "total_sessions": total_sessions,
                "total_insights": total_insights,
                "category_distribution": category_dist,
                "average_confidence": float(avg_conf) if avg_conf else None,
                "active_session": self.active_session_id
            }

    def _session_to_dict(self, s: ThoughtSession) -> Dict:
        return {
            "id": s.id,
            "context": s.context,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            "status": s.status,
            "summary": s.summary,
            "outcomes": s.outcomes
        }

    def _thought_to_dict(self, t: Thought) -> Dict:
        return {
            "id": t.id,
            "thought": t.thought,
            "category": t.category,
            "reasoning": t.reasoning,
            "related_to": t.related_to,
            "confidence": t.confidence,
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            "session_id": t.session_id
        }

    def _insight_to_dict(self, i: Insight) -> Dict:
        return {
            "id": i.id,
            "insight": i.insight,
            "source": i.source,
            "applicability": i.applicability,
            "session_id": i.session_id,
            "timestamp": i.timestamp.isoformat() if i.timestamp else None
        }
