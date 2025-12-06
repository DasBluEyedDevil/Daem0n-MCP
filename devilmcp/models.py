"""
DevilMCP Models - Simplified schema focused on AI memory and decision trees.

Only 3 tables:
- memories: Stores decisions, patterns, warnings, learnings
- rules: Decision tree nodes / enforcement rules
- project_state: Cached project context
"""

from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Boolean
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime, timezone


class Base(DeclarativeBase):
    pass


class Memory(Base):
    """
    A memory is any piece of information the AI should remember.

    Categories:
    - decision: An architectural or design choice
    - pattern: A recurring approach that should be followed
    - warning: Something that went wrong / should be avoided
    - learning: A lesson learned from experience
    """
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, index=True)

    # What type of memory
    category = Column(String, nullable=False, index=True)  # decision, pattern, warning, learning

    # The actual content
    content = Column(Text, nullable=False)

    # Why this decision was made / context
    rationale = Column(Text, nullable=True)

    # Structured context (files involved, alternatives, etc.)
    context = Column(JSON, default=dict)

    # Tags for retrieval
    tags = Column(JSON, default=list)

    # Extracted keywords for semantic-ish search (computed from content + tags)
    keywords = Column(Text, nullable=True, index=True)

    # Outcome tracking
    outcome = Column(Text, nullable=True)  # What actually happened
    worked = Column(Boolean, nullable=True)  # Did it work out?

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))


class Rule(Base):
    """
    A rule is a decision tree node - when a trigger condition is met,
    it provides guidance on what to do.

    Example:
        trigger: "adding new API endpoint"
        must_do: ["Add rate limiting", "Add to OpenAPI spec"]
        must_not: ["Use synchronous database calls"]
        ask_first: ["Is this a breaking change?"]
    """
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, index=True)

    # What activates this rule (human-readable description)
    trigger = Column(Text, nullable=False)

    # Extracted keywords for matching
    trigger_keywords = Column(Text, nullable=True, index=True)

    # Things that MUST be done when this rule applies
    must_do = Column(JSON, default=list)

    # Things that MUST NOT be done
    must_not = Column(JSON, default=list)

    # Questions to ask/consider before proceeding
    ask_first = Column(JSON, default=list)

    # Warnings to display (from past experience)
    warnings = Column(JSON, default=list)

    # Higher priority rules are shown first
    priority = Column(Integer, default=0)

    # Can disable rules without deleting
    enabled = Column(Boolean, default=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ProjectState(Base):
    """
    Cached project state for quick briefings.
    """
    __tablename__ = "project_state"

    id = Column(Integer, primary_key=True, index=True)
    project_path = Column(String, unique=True, nullable=False, index=True)

    # Cached summary data
    summary = Column(JSON, default=dict)

    # Statistics
    memory_count = Column(Integer, default=0)
    rule_count = Column(Integer, default=0)

    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))
