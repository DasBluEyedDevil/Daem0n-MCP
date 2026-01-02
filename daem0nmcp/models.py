"""
Daem0nMCP Models - Schema for AI memory, decision trees, and knowledge graphs.

Tables:
- memories: Stores decisions, patterns, warnings, learnings
- rules: Decision tree nodes / enforcement rules
- memory_relationships: Graph edges between memories for causal reasoning
"""

from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Boolean, LargeBinary, Float, ForeignKey
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import relationship as orm_relationship
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

    # Relative file path (for portability across machines)
    file_path_relative = Column(String, nullable=True, index=True)

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

    # Recall count - tracks how often this memory is accessed (for saliency-based pruning)
    recall_count = Column(Integer, default=0)

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


class MemoryRelationship(Base):
    """
    Explicit relationship edges between memories for graph traversal.

    Enables causal chain reasoning that similarity search alone cannot provide:
    - "What decisions led to this pattern?"
    - "What does this library choice depend on?"
    - "What approaches have been superseded?"

    Relationship types:
    - led_to: A caused or resulted in B (e.g., "database choice led to caching pattern")
    - supersedes: A replaces B (B is now outdated)
    - depends_on: A requires B to be valid
    - conflicts_with: A contradicts B
    - related_to: General association (weaker than above)

    Usage pattern (Vector-First, Graph-Second):
    1. Use semantic search to find candidate memories
    2. Expand via graph edges to get connected context
    3. Assembly full context for LLM including structural relationships
    """
    __tablename__ = "memory_relationships"

    id = Column(Integer, primary_key=True, index=True)

    # Source memory (the "from" node)
    source_id = Column(Integer, ForeignKey("memories.id", ondelete="CASCADE"), nullable=False, index=True)

    # Target memory (the "to" node)
    target_id = Column(Integer, ForeignKey("memories.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationship type
    relationship = Column(String, nullable=False, index=True)

    # Optional description/context for this edge
    description = Column(Text, nullable=True)

    # Confidence/strength (1.0 = certain, can decay over time)
    confidence = Column(Float, default=1.0)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ORM relationships for easy navigation
    source = orm_relationship("Memory", foreign_keys=[source_id], backref="outgoing_relationships")
    target = orm_relationship("Memory", foreign_keys=[target_id], backref="incoming_relationships")


class SessionState(Base):
    """
    Tracks session state for enforcement.

    Sessions are identified by project + time bucket.
    Tracks what context checks were made and what decisions are pending outcomes.
    """
    __tablename__ = "session_state"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, nullable=False, unique=True, index=True)
    project_path = Column(String, nullable=False)
    briefed = Column(Boolean, default=False)
    context_checks = Column(JSON, default=list)  # List of files/topics checked
    pending_decisions = Column(JSON, default=list)  # List of memory IDs
    last_activity = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class EnforcementBypassLog(Base):
    """
    Audit log for when enforcement is bypassed via --no-verify.

    Provides accountability even when developers skip enforcement.
    """
    __tablename__ = "enforcement_bypass_log"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    pending_decisions = Column(JSON, default=list)  # List of skipped decision IDs
    staged_files_with_warnings = Column(JSON, default=list)  # List of risky files
    reason = Column(Text, nullable=True)  # Optional user-provided reason


class CodeEntity(Base):
    """
    A code element from an indexed project.

    Types: file, class, function, method, variable, import, module

    Used by Phase 2: Code Understanding layer to enable:
    - "What depends on X?"
    - Impact analysis for changes
    - Semantic code search
    """
    __tablename__ = "code_entities"

    id = Column(String, primary_key=True)  # hash of project+path+name+type
    project_path = Column(String, nullable=False, index=True)

    entity_type = Column(String, nullable=False)  # file, class, function, method
    name = Column(String, nullable=False)
    qualified_name = Column(String, nullable=True)  # e.g., "myapp.models.User.save"
    file_path = Column(String, nullable=False, index=True)
    line_start = Column(Integer, nullable=True)
    line_end = Column(Integer, nullable=True)

    signature = Column(Text, nullable=True)  # First line of definition
    docstring = Column(Text, nullable=True)

    # Structural relationships (for dependency tracking)
    calls = Column(JSON, default=list)  # Functions/methods this entity calls
    called_by = Column(JSON, default=list)  # Functions/methods that call this
    imports = Column(JSON, default=list)  # What this entity imports
    inherits = Column(JSON, default=list)  # Parent classes for class entities

    indexed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class MemoryCodeRef(Base):
    """
    Links memories to code entities.

    Enables automatic symbol resolution:
    - When a memory mentions `UserService.authenticate`, link to that entity
    - When code changes, surface relevant memories

    Relationship types:
    - about: Memory discusses this entity
    - modifies: Memory describes changes to this entity
    - introduces: Memory introduces this entity
    - deprecates: Memory marks this entity as deprecated
    """
    __tablename__ = "memory_code_refs"

    id = Column(Integer, primary_key=True)
    memory_id = Column(Integer, ForeignKey("memories.id", ondelete="CASCADE"), index=True)
    code_entity_id = Column(String, index=True)

    # Snapshot (survives reindex - entity might be renamed/moved)
    entity_type = Column(String, nullable=True)
    entity_name = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    line_number = Column(Integer, nullable=True)

    relationship = Column(String, nullable=True)  # "about", "modifies", "introduces", "deprecates"
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ORM relationship
    memory = orm_relationship("Memory", backref="code_refs")
