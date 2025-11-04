"""
Decision Tracker Module
Tracks AI decisions, rationale, and outcomes to maintain decision history and learning.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DecisionTracker:
    """Tracks and manages decision history with full context and rationale."""

    def __init__(self, storage_path: str = "./storage"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self.decisions_file = self.storage_path / "decisions.json"
        self.decisions = self._load_decisions()

    def _load_decisions(self) -> List[Dict]:
        """Load existing decisions or create new list."""
        if self.decisions_file.exists():
            try:
                with open(self.decisions_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading decisions: {e}")
        return []

    def _save_decisions(self):
        """Persist decisions to storage."""
        try:
            with open(self.decisions_file, 'w') as f:
                json.dump(self.decisions, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving decisions: {e}")

    def log_decision(
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

        Args:
            decision: The decision made
            rationale: Explanation of why this decision was made
            context: Contextual information about the decision
            alternatives_considered: List of alternative approaches considered
            expected_impact: Expected impact of the decision
            risk_level: Risk level (low, medium, high, critical)
            tags: Tags for categorization

        Returns:
            The logged decision record with assigned ID
        """
        decision_id = len(self.decisions) + 1

        decision_record = {
            "id": decision_id,
            "decision": decision,
            "rationale": rationale,
            "context": context,
            "alternatives_considered": alternatives_considered or [],
            "expected_impact": expected_impact,
            "risk_level": risk_level,
            "tags": tags or [],
            "timestamp": datetime.now().isoformat(),
            "outcome": None,  # To be updated later
            "actual_impact": None  # To be updated later
        }

        self.decisions.append(decision_record)
        self._save_decisions()

        logger.info(f"Decision logged: {decision_id} - {decision}")
        return decision_record

    def update_decision_outcome(
        self,
        decision_id: int,
        outcome: str,
        actual_impact: str,
        lessons_learned: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Update a decision with its actual outcome and impact.

        Args:
            decision_id: ID of the decision to update
            outcome: The actual outcome of the decision
            actual_impact: The actual impact observed
            lessons_learned: Lessons learned from this decision

        Returns:
            Updated decision record or None if not found
        """
        for decision in self.decisions:
            if decision["id"] == decision_id:
                decision["outcome"] = outcome
                decision["actual_impact"] = actual_impact
                decision["lessons_learned"] = lessons_learned
                decision["updated_at"] = datetime.now().isoformat()

                self._save_decisions()
                logger.info(f"Decision {decision_id} outcome updated")
                return decision

        logger.warning(f"Decision {decision_id} not found")
        return None

    def query_decisions(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        risk_level: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Query decisions by various criteria.

        Args:
            query: Text to search for in decision and rationale
            tags: Filter by tags
            risk_level: Filter by risk level
            limit: Maximum number of results to return

        Returns:
            List of matching decisions
        """
        results = []

        for decision in reversed(self.decisions):  # Most recent first
            # Apply filters
            if query and query.lower() not in decision["decision"].lower() and \
               query.lower() not in decision["rationale"].lower():
                continue

            if tags and not any(tag in decision["tags"] for tag in tags):
                continue

            if risk_level and decision["risk_level"] != risk_level:
                continue

            results.append(decision)

            if len(results) >= limit:
                break

        return results

    def analyze_decision_impact(self, decision_id: int) -> Dict:
        """
        Analyze the impact and consequences of a specific decision.

        Args:
            decision_id: ID of the decision to analyze

        Returns:
            Analysis of the decision's impact
        """
        decision = next((d for d in self.decisions if d["id"] == decision_id), None)

        if not decision:
            return {"error": f"Decision {decision_id} not found"}

        analysis = {
            "decision_id": decision_id,
            "decision": decision["decision"],
            "timestamp": decision["timestamp"],
            "expected_vs_actual": {
                "expected_impact": decision.get("expected_impact"),
                "actual_impact": decision.get("actual_impact"),
                "alignment": self._assess_alignment(
                    decision.get("expected_impact"),
                    decision.get("actual_impact")
                )
            },
            "risk_assessment": {
                "initial_risk_level": decision["risk_level"],
                "materialized": decision.get("outcome") is not None
            },
            "related_decisions": self._find_related_decisions(decision),
            "lessons_learned": decision.get("lessons_learned")
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

        # Simple keyword matching (can be enhanced with NLP)
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

    def _find_related_decisions(self, decision: Dict) -> List[int]:
        """Find decisions related to the given decision."""
        related = []

        decision_tags = set(decision["tags"])
        decision_words = set(decision["decision"].lower().split())

        for other in self.decisions:
            if other["id"] == decision["id"]:
                continue

            # Check tag overlap
            other_tags = set(other["tags"])
            if decision_tags & other_tags:
                related.append(other["id"])
                continue

            # Check keyword overlap
            other_words = set(other["decision"].lower().split())
            overlap = len(decision_words & other_words)

            if overlap >= 3:  # At least 3 common words
                related.append(other["id"])

        return related[:5]  # Return top 5 related

    def get_decision_statistics(self) -> Dict:
        """
        Get statistics about decisions made.

        Returns:
            Statistics including risk distribution, outcome tracking, etc.
        """
        total_decisions = len(self.decisions)

        if total_decisions == 0:
            return {"total_decisions": 0}

        risk_distribution = {}
        decisions_with_outcomes = 0
        tag_frequency = {}

        for decision in self.decisions:
            # Risk distribution
            risk = decision["risk_level"]
            risk_distribution[risk] = risk_distribution.get(risk, 0) + 1

            # Outcomes tracked
            if decision.get("outcome"):
                decisions_with_outcomes += 1

            # Tag frequency
            for tag in decision["tags"]:
                tag_frequency[tag] = tag_frequency.get(tag, 0) + 1

        return {
            "total_decisions": total_decisions,
            "risk_distribution": risk_distribution,
            "decisions_with_outcomes": decisions_with_outcomes,
            "outcome_tracking_rate": decisions_with_outcomes / total_decisions,
            "top_tags": sorted(tag_frequency.items(), key=lambda x: x[1], reverse=True)[:10],
            "most_recent": self.decisions[-1]["timestamp"] if self.decisions else None
        }

    def export_decisions(self, format: str = "json") -> str:
        """
        Export decisions in various formats.

        Args:
            format: Export format ('json', 'markdown')

        Returns:
            Formatted decision export
        """
        if format == "json":
            return json.dumps(self.decisions, indent=2)

        elif format == "markdown":
            md = "# Decision Log\n\n"

            for decision in reversed(self.decisions):
                md += f"## Decision #{decision['id']}: {decision['decision']}\n\n"
                md += f"**Timestamp:** {decision['timestamp']}\n\n"
                md += f"**Risk Level:** {decision['risk_level']}\n\n"
                md += f"**Rationale:**\n{decision['rationale']}\n\n"

                if decision['alternatives_considered']:
                    md += "**Alternatives Considered:**\n"
                    for alt in decision['alternatives_considered']:
                        md += f"- {alt}\n"
                    md += "\n"

                if decision.get('expected_impact'):
                    md += f"**Expected Impact:** {decision['expected_impact']}\n\n"

                if decision.get('outcome'):
                    md += f"**Outcome:** {decision['outcome']}\n\n"

                if decision.get('actual_impact'):
                    md += f"**Actual Impact:** {decision['actual_impact']}\n\n"

                if decision['tags']:
                    md += f"**Tags:** {', '.join(decision['tags'])}\n\n"

                md += "---\n\n"

            return md

        else:
            return json.dumps({"error": f"Unsupported format: {format}"})
