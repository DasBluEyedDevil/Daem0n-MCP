"""
Thought Processor Module
Manages AI thought processes, reasoning chains, and cognitive context.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ThoughtProcessor:
    """Manages thought processes and reasoning chains for AI agents."""

    def __init__(self, storage_path: str = "./storage"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self.thoughts_file = self.storage_path / "thoughts.json"
        self.thoughts = self._load_thoughts()
        self.active_session = None

    def _load_thoughts(self) -> Dict:
        """Load existing thought data."""
        if self.thoughts_file.exists():
            try:
                with open(self.thoughts_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading thoughts: {e}")

        return {
            "sessions": {},
            "reasoning_chains": [],
            "insights": []
        }

    def _save_thoughts(self):
        """Persist thought data."""
        try:
            with open(self.thoughts_file, 'w') as f:
                json.dump(self.thoughts, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving thoughts: {e}")

    def start_session(self, session_id: str, context: Dict) -> Dict:
        """
        Start a new thought processing session.

        Args:
            session_id: Unique identifier for the session
            context: Initial context for the session

        Returns:
            Session information
        """
        session = {
            "id": session_id,
            "context": context,
            "started_at": datetime.now().isoformat(),
            "thoughts": [],
            "decisions": [],
            "insights": [],
            "status": "active"
        }

        self.thoughts["sessions"][session_id] = session
        self.active_session = session_id
        self._save_thoughts()

        logger.info(f"Started thought session: {session_id}")
        return session

    def end_session(
        self,
        session_id: str,
        summary: Optional[str] = None,
        outcomes: Optional[List[str]] = None
    ) -> Dict:
        """
        End a thought processing session.

        Args:
            session_id: Session to end
            summary: Summary of the session
            outcomes: List of outcomes achieved

        Returns:
            Final session state
        """
        if session_id not in self.thoughts["sessions"]:
            return {"error": f"Session {session_id} not found"}

        session = self.thoughts["sessions"][session_id]
        session["status"] = "completed"
        session["ended_at"] = datetime.now().isoformat()
        session["summary"] = summary
        session["outcomes"] = outcomes or []

        if self.active_session == session_id:
            self.active_session = None

        self._save_thoughts()

        logger.info(f"Ended thought session: {session_id}")
        return session

    def log_thought_process(
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

        Args:
            thought: The thought or consideration
            category: Category (analysis, hypothesis, concern, question, etc.)
            reasoning: The reasoning behind this thought
            related_to: List of related thought IDs or concepts
            confidence: Confidence level (0.0 to 1.0)
            session_id: Session this thought belongs to

        Returns:
            The logged thought record
        """
        thought_id = len(self.thoughts["reasoning_chains"]) + 1

        thought_record = {
            "id": thought_id,
            "thought": thought,
            "category": category,
            "reasoning": reasoning,
            "related_to": related_to or [],
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id or self.active_session
        }

        self.thoughts["reasoning_chains"].append(thought_record)

        # Add to active session if applicable
        if thought_record["session_id"]:
            session = self.thoughts["sessions"].get(thought_record["session_id"])
            if session:
                session["thoughts"].append(thought_id)

        self._save_thoughts()

        logger.info(f"Thought logged: {thought_id} - {category}")
        return thought_record

    def retrieve_thought_context(
        self,
        thought_id: Optional[int] = None,
        category: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Retrieve related thought context.

        Args:
            thought_id: Specific thought ID to get context for
            category: Filter by category
            session_id: Filter by session
            limit: Maximum number of results

        Returns:
            List of related thoughts
        """
        results = []

        # If looking for specific thought
        if thought_id:
            target_thought = next(
                (t for t in self.thoughts["reasoning_chains"] if t["id"] == thought_id),
                None
            )

            if target_thought:
                results.append(target_thought)

                # Get related thoughts
                for related_id in target_thought.get("related_to", []):
                    if isinstance(related_id, int):
                        related = next(
                            (t for t in self.thoughts["reasoning_chains"] if t["id"] == related_id),
                            None
                        )
                        if related:
                            results.append(related)

        # General query
        else:
            for thought in reversed(self.thoughts["reasoning_chains"]):
                if category and thought["category"] != category:
                    continue

                if session_id and thought.get("session_id") != session_id:
                    continue

                results.append(thought)

                if len(results) >= limit:
                    break

        return results

    def analyze_reasoning_gaps(self, session_id: Optional[str] = None) -> Dict:
        """
        Analyze gaps in reasoning or considerations.

        Args:
            session_id: Optional session to analyze (defaults to active)

        Returns:
            Analysis of reasoning gaps and suggestions
        """
        target_session = session_id or self.active_session

        if not target_session:
            return {"error": "No session specified or active"}

        session = self.thoughts["sessions"].get(target_session)
        if not session:
            return {"error": f"Session {target_session} not found"}

        # Get all thoughts for this session
        session_thoughts = [
            t for t in self.thoughts["reasoning_chains"]
            if t.get("session_id") == target_session
        ]

        analysis = {
            "session_id": target_session,
            "total_thoughts": len(session_thoughts),
            "categories_covered": set(),
            "gaps": [],
            "suggestions": []
        }

        # Analyze category coverage
        for thought in session_thoughts:
            analysis["categories_covered"].add(thought["category"])

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

        # Check for low confidence thoughts without follow-up
        low_confidence_thoughts = [
            t for t in session_thoughts
            if t.get("confidence", 1.0) < 0.6
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
            if not t.get("related_to")
        ]

        if len(unlinked_thoughts) / max(len(session_thoughts), 1) > 0.5:
            analysis["gaps"].append("Many thoughts not connected to reasoning chain")
            analysis["suggestions"].append(
                "Link related thoughts to build coherent reasoning"
            )

        return analysis

    def record_insight(
        self,
        insight: str,
        source: str,
        applicability: str,
        session_id: Optional[str] = None
    ) -> Dict:
        """
        Record an insight gained during processing.

        Args:
            insight: The insight discovered
            source: Where this insight came from
            applicability: Where/how this insight can be applied
            session_id: Session this insight came from

        Returns:
            The recorded insight
        """
        insight_record = {
            "id": len(self.thoughts["insights"]) + 1,
            "insight": insight,
            "source": source,
            "applicability": applicability,
            "session_id": session_id or self.active_session,
            "timestamp": datetime.now().isoformat()
        }

        self.thoughts["insights"].append(insight_record)

        # Add to session if applicable
        if insight_record["session_id"]:
            session = self.thoughts["sessions"].get(insight_record["session_id"])
            if session:
                session.setdefault("insights", []).append(insight_record["id"])

        self._save_thoughts()

        logger.info(f"Insight recorded: {insight}")
        return insight_record

    def query_insights(
        self,
        query: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Query recorded insights.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching insights
        """
        results = []

        for insight in reversed(self.thoughts["insights"]):
            if query:
                query_lower = query.lower()
                if (query_lower not in insight["insight"].lower() and
                    query_lower not in insight["applicability"].lower()):
                    continue

            results.append(insight)

            if len(results) >= limit:
                break

        return results

    def build_reasoning_chain(
        self,
        start_thought_id: int,
        max_depth: int = 10
    ) -> Dict:
        """
        Build a complete reasoning chain from a starting thought.

        Args:
            start_thought_id: Starting thought ID
            max_depth: Maximum chain depth

        Returns:
            Complete reasoning chain
        """
        start_thought = next(
            (t for t in self.thoughts["reasoning_chains"] if t["id"] == start_thought_id),
            None
        )

        if not start_thought:
            return {"error": f"Thought {start_thought_id} not found"}

        chain = {
            "start": start_thought,
            "chain": [],
            "depth": 0
        }

        # Build chain recursively
        visited = set()
        self._build_chain_recursive(start_thought, chain["chain"], visited, 0, max_depth)

        chain["depth"] = len(chain["chain"])
        chain["total_thoughts"] = len(set(t["id"] for t in chain["chain"]))

        return chain

    def _build_chain_recursive(
        self,
        thought: Dict,
        chain: List,
        visited: Set,
        current_depth: int,
        max_depth: int
    ):
        """Recursively build reasoning chain."""
        if current_depth >= max_depth or thought["id"] in visited:
            return

        visited.add(thought["id"])
        chain.append(thought)

        # Follow related thoughts
        for related_id in thought.get("related_to", []):
            if isinstance(related_id, int):
                related = next(
                    (t for t in self.thoughts["reasoning_chains"] if t["id"] == related_id),
                    None
                )
                if related:
                    self._build_chain_recursive(
                        related, chain, visited, current_depth + 1, max_depth
                    )

    def get_session_summary(self, session_id: str) -> Dict:
        """
        Get comprehensive summary of a session.

        Args:
            session_id: Session to summarize

        Returns:
            Session summary with statistics and key points
        """
        session = self.thoughts["sessions"].get(session_id)

        if not session:
            return {"error": f"Session {session_id} not found"}

        # Get session thoughts
        session_thoughts = [
            t for t in self.thoughts["reasoning_chains"]
            if t.get("session_id") == session_id
        ]

        # Categorize thoughts
        by_category = {}
        for thought in session_thoughts:
            category = thought["category"]
            by_category.setdefault(category, []).append(thought)

        # Get insights
        session_insights = [
            i for i in self.thoughts["insights"]
            if i.get("session_id") == session_id
        ]

        summary = {
            "session_id": session_id,
            "status": session["status"],
            "duration": self._calculate_duration(
                session.get("started_at"),
                session.get("ended_at")
            ),
            "total_thoughts": len(session_thoughts),
            "by_category": {
                cat: len(thoughts) for cat, thoughts in by_category.items()
            },
            "total_insights": len(session_insights),
            "key_concerns": [
                t["thought"] for t in by_category.get("concern", [])
            ][:5],
            "key_decisions": session.get("decisions", []),
            "outcomes": session.get("outcomes", []),
            "summary": session.get("summary")
        }

        return summary

    def _calculate_duration(
        self,
        start: Optional[str],
        end: Optional[str]
    ) -> Optional[str]:
        """Calculate duration between two timestamps."""
        if not start:
            return None

        try:
            from datetime import datetime
            start_dt = datetime.fromisoformat(start)

            if end:
                end_dt = datetime.fromisoformat(end)
            else:
                end_dt = datetime.now()

            duration = end_dt - start_dt
            return str(duration)
        except Exception:
            return None

    def get_thought_statistics(self) -> Dict:
        """
        Get statistics about thought processes.

        Returns:
            Statistics including category distribution, confidence levels, etc.
        """
        if not self.thoughts["reasoning_chains"]:
            return {"total_thoughts": 0}

        category_dist = {}
        confidence_levels = []

        for thought in self.thoughts["reasoning_chains"]:
            category = thought["category"]
            category_dist[category] = category_dist.get(category, 0) + 1

            if thought.get("confidence") is not None:
                confidence_levels.append(thought["confidence"])

        avg_confidence = (
            sum(confidence_levels) / len(confidence_levels)
            if confidence_levels else None
        )

        return {
            "total_thoughts": len(self.thoughts["reasoning_chains"]),
            "total_sessions": len(self.thoughts["sessions"]),
            "total_insights": len(self.thoughts["insights"]),
            "category_distribution": category_dist,
            "average_confidence": avg_confidence,
            "active_session": self.active_session
        }
