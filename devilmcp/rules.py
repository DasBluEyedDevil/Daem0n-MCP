"""
Rules Engine - Decision trees and enforcement for AI agents.

This module handles:
- Storing rules (decision tree nodes)
- Matching actions against rules
- Providing guidance based on matching rules
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import select, desc

from .database import DatabaseManager
from .models import Rule
from .memory import extract_keywords, STOP_WORDS

logger = logging.getLogger(__name__)


def match_score(action_keywords: set, rule_keywords: str) -> float:
    """
    Calculate how well an action matches a rule's trigger.

    Returns score from 0.0 to 1.0.
    """
    if not action_keywords or not rule_keywords:
        return 0.0

    rule_kw_set = set(rule_keywords.lower().split())

    if not rule_kw_set:
        return 0.0

    # Count matches
    matches = len(action_keywords & rule_kw_set)

    if matches == 0:
        return 0.0

    # Score based on what fraction of rule keywords are matched
    score = matches / len(rule_kw_set)

    return score


class RulesEngine:
    """
    Manages rules - the decision tree nodes that guide AI behavior.

    A rule has:
    - trigger: What activates it (e.g., "adding new API endpoint")
    - must_do: Things that must be done
    - must_not: Things to avoid
    - ask_first: Questions to consider
    - warnings: Warnings from past experience
    """

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    async def add_rule(
        self,
        trigger: str,
        must_do: Optional[List[str]] = None,
        must_not: Optional[List[str]] = None,
        ask_first: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        priority: int = 0
    ) -> Dict[str, Any]:
        """
        Add a new rule to the decision tree.

        Args:
            trigger: What activates this rule (natural language description)
            must_do: List of things that must be done
            must_not: List of things to avoid
            ask_first: Questions to consider before proceeding
            warnings: Warnings from past experience
            priority: Higher priority rules are shown first

        Returns:
            The created rule as a dict
        """
        # Extract keywords from trigger for matching
        trigger_keywords = extract_keywords(trigger)

        rule = Rule(
            trigger=trigger,
            trigger_keywords=trigger_keywords,
            must_do=must_do or [],
            must_not=must_not or [],
            ask_first=ask_first or [],
            warnings=warnings or [],
            priority=priority,
            enabled=True
        )

        async with self.db.get_session() as session:
            session.add(rule)
            await session.flush()
            rule_id = rule.id

            logger.info(f"Added rule: {trigger[:50]}...")

            return {
                "id": rule_id,
                "trigger": trigger,
                "must_do": must_do or [],
                "must_not": must_not or [],
                "ask_first": ask_first or [],
                "warnings": warnings or [],
                "priority": priority,
                "created_at": rule.created_at.isoformat()
            }

    async def check_rules(
        self,
        action: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Check if an action triggers any rules and return guidance.

        This is the enforcement function - the AI calls this before taking
        an action to get relevant rules.

        Args:
            action: Description of what the AI is about to do
            context: Optional context (files involved, etc.)

        Returns:
            Matching rules with combined guidance
        """
        # Extract keywords from action
        action_keywords = set(extract_keywords(action).split())

        if not action_keywords:
            return {
                "action": action,
                "matched_rules": 0,
                "guidance": None,
                "message": "No actionable keywords found"
            }

        async with self.db.get_session() as session:
            # Get all enabled rules
            result = await session.execute(
                select(Rule)
                .where(Rule.enabled == True)  # noqa: E712
                .order_by(desc(Rule.priority))
            )
            rules = result.scalars().all()

            # Score and collect matching rules
            matching = []
            for rule in rules:
                score = match_score(action_keywords, rule.trigger_keywords)
                if score >= 0.3:  # Minimum match threshold
                    matching.append((rule, score))

            if not matching:
                return {
                    "action": action,
                    "matched_rules": 0,
                    "guidance": None,
                    "message": "No rules match this action - proceed with caution"
                }

            # Sort by priority then score
            matching.sort(key=lambda x: (x[0].priority, x[1]), reverse=True)

            # Combine guidance from matching rules
            combined = {
                "must_do": [],
                "must_not": [],
                "ask_first": [],
                "warnings": []
            }

            matched_details = []
            for rule, score in matching:
                combined["must_do"].extend(rule.must_do)
                combined["must_not"].extend(rule.must_not)
                combined["ask_first"].extend(rule.ask_first)
                combined["warnings"].extend(rule.warnings)

                matched_details.append({
                    "id": rule.id,
                    "trigger": rule.trigger,
                    "match_score": round(score, 2),
                    "priority": rule.priority
                })

            # Deduplicate
            combined["must_do"] = list(dict.fromkeys(combined["must_do"]))
            combined["must_not"] = list(dict.fromkeys(combined["must_not"]))
            combined["ask_first"] = list(dict.fromkeys(combined["ask_first"]))
            combined["warnings"] = list(dict.fromkeys(combined["warnings"]))

            # Build response
            has_blockers = len(combined["must_not"]) > 0 or len(combined["warnings"]) > 0

            return {
                "action": action,
                "matched_rules": len(matching),
                "rules": matched_details,
                "guidance": combined,
                "has_blockers": has_blockers,
                "message": (
                    "STOP: Review warnings and must_not items before proceeding"
                    if has_blockers else
                    "Rules matched - review must_do items"
                )
            }

    async def list_rules(
        self,
        enabled_only: bool = True,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List all rules."""
        async with self.db.get_session() as session:
            query = select(Rule).order_by(desc(Rule.priority), desc(Rule.created_at))

            if enabled_only:
                query = query.where(Rule.enabled == True)  # noqa: E712

            query = query.limit(limit)

            result = await session.execute(query)
            rules = result.scalars().all()

            return [
                {
                    "id": r.id,
                    "trigger": r.trigger,
                    "must_do": r.must_do,
                    "must_not": r.must_not,
                    "ask_first": r.ask_first,
                    "warnings": r.warnings,
                    "priority": r.priority,
                    "enabled": r.enabled,
                    "created_at": r.created_at.isoformat()
                }
                for r in rules
            ]

    async def update_rule(
        self,
        rule_id: int,
        must_do: Optional[List[str]] = None,
        must_not: Optional[List[str]] = None,
        ask_first: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        priority: Optional[int] = None,
        enabled: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Update an existing rule."""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Rule).where(Rule.id == rule_id)
            )
            rule = result.scalar_one_or_none()

            if not rule:
                return {"error": f"Rule {rule_id} not found"}

            if must_do is not None:
                rule.must_do = must_do
            if must_not is not None:
                rule.must_not = must_not
            if ask_first is not None:
                rule.ask_first = ask_first
            if warnings is not None:
                rule.warnings = warnings
            if priority is not None:
                rule.priority = priority
            if enabled is not None:
                rule.enabled = enabled

            return {
                "id": rule.id,
                "trigger": rule.trigger,
                "updated": True
            }

    async def delete_rule(self, rule_id: int) -> Dict[str, Any]:
        """Delete a rule."""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Rule).where(Rule.id == rule_id)
            )
            rule = result.scalar_one_or_none()

            if not rule:
                return {"error": f"Rule {rule_id} not found"}

            trigger = rule.trigger
            await session.delete(rule)

            return {
                "deleted": True,
                "trigger": trigger
            }

    async def add_warning_to_rule(
        self,
        rule_id: int,
        warning: str
    ) -> Dict[str, Any]:
        """Add a warning to an existing rule (from learned experience)."""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Rule).where(Rule.id == rule_id)
            )
            rule = result.scalar_one_or_none()

            if not rule:
                return {"error": f"Rule {rule_id} not found"}

            if warning not in rule.warnings:
                rule.warnings = rule.warnings + [warning]

            return {
                "id": rule.id,
                "trigger": rule.trigger,
                "warnings": rule.warnings
            }
