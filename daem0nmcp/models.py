"""
Daem0nMCP Models - Simplified schema focused on AI memory and decision trees.

Only 2 tables:
- memories: Stores decisions, patterns, warnings, learnings
- rules: Decision tree nodes / enforcement rules
"""

from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Boolean, LargeBinary
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime, timezone


class Base(DeclarativeBase):
    pass


class Memory(Base):
    """
    A memory is any piece of information the AI should remember.

    Categories:
    - decision: An architectural or design choice (episodic - decays)
    - pattern: A recurring approach that should be followed (semantic - permanent)
    - warning: Something that went wrong / should be avoided (semantic - permanent)
    - learning: A lesson learned from experience (episodic - decays)

    Semantic memories (patterns, warnings) don't decay - they're project facts.
    Episodic memories (decisions, learnings) decay over time.
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

    # File path association - link memory to specific files
    file_path = Column(String, nullable=True, index=True)

    # Extracted keywords for semantic-ish search (computed from content + tags)
    keywords = Column(Text, nullable=True, index=True)

    # Permanent flag - semantic memories (patterns, warnings) don't decay
    # Auto-set based on category, but can be overridden
    is_permanent = Column(Boolean, default=False)

    # Vector embedding for semantic search (optional - requires sentence-transformers)
    # Stored as packed floats (bytes)
    vector_embedding = Column(LargeBinary, nullable=True)

    # Outcome tracking
    outcome = Column(Text, nullable=True)  # What actually happened
    worked = Column(Boolean, nullable=True)  # Did it work out?

    # Pinned memories are never pruned and have boosted relevance
    pinned = Column(Boolean, default=False)

    # Archived memories are hidden from normal recall but kept for history
    archived = Column(Boolean, default=False)

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


# Note: ProjectState table was removed in v2.1 as it was unused.
# The briefing now computes statistics dynamically which is more accurate.
