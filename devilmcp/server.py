"""
DevilMCP Server - Focused AI Memory System

A streamlined MCP server that provides:
1. Memory storage and retrieval (decisions, patterns, warnings, learnings)
2. Rule-based decision trees for consistent AI behavior
3. Outcome tracking for continuous learning

Core Tools:
- remember: Store a decision, pattern, warning, or learning
- recall: Retrieve relevant memories for a topic
- add_rule: Add a decision tree node
- check_rules: Validate an action against rules
- record_outcome: Track whether a decision worked
- get_briefing: Get everything needed to start a session
"""

import sys
import logging
import atexit
from typing import Dict, List, Optional, Any

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("ERROR: fastmcp not installed. Run: pip install fastmcp", file=sys.stderr)
    sys.exit(1)

from .config import settings
from .database import DatabaseManager
from .memory import MemoryManager
from .rules import RulesEngine
from .models import Memory, Rule
from sqlalchemy import select

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("DevilMCP")

# Initialize core modules
storage_path = settings.get_storage_path()
db_manager = DatabaseManager(storage_path)
memory_manager = MemoryManager(db_manager)
rules_engine = RulesEngine(db_manager)

logger.info(f"DevilMCP Server initialized (storage: {storage_path})")


# ============================================================================
# Tool 1: REMEMBER - Store a memory
# ============================================================================
@mcp.tool()
async def remember(
    category: str,
    content: str,
    rationale: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Store a decision, pattern, warning, or learning in long-term memory.

    Use this immediately when:
    - Making an architectural decision
    - Establishing a pattern to follow
    - Encountering something that should be avoided (warning)
    - Learning something useful from experience

    Args:
        category: One of 'decision', 'pattern', 'warning', 'learning'
        content: The actual content to remember
        rationale: Why this is important / the reasoning behind it
        context: Structured context (files involved, alternatives considered, etc.)
        tags: Tags for easier retrieval (e.g., ['auth', 'security', 'api'])

    Returns:
        The created memory with its ID for future reference

    Examples:
        remember("decision", "Use JWT tokens instead of sessions",
                 rationale="Need stateless auth for horizontal scaling",
                 tags=["auth", "architecture"])

        remember("warning", "Don't use sync DB calls in request handlers",
                 rationale="Caused timeout issues in production",
                 context={"file": "api/handlers.py"})

        remember("pattern", "All API endpoints must have rate limiting",
                 rationale="Security requirement from review",
                 tags=["api", "security"])
    """
    await db_manager.init_db()
    return await memory_manager.remember(
        category=category,
        content=content,
        rationale=rationale,
        context=context,
        tags=tags
    )


# ============================================================================
# Tool 2: RECALL - Retrieve relevant memories
# ============================================================================
@mcp.tool()
async def recall(
    topic: str,
    categories: Optional[List[str]] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Recall memories relevant to a topic. This is ACTIVE memory retrieval.

    Call this before working on any feature or making changes to get:
    - Past decisions about this area
    - Patterns that should be followed
    - Warnings about what to avoid
    - Learnings from previous work

    Args:
        topic: What you're looking for (e.g., "authentication", "database schema")
        categories: Limit to specific categories (default: all)
        limit: Max memories per category (default: 10)

    Returns:
        Categorized memories with relevance scores

    Examples:
        recall("authentication")  # Get all memories about auth
        recall("API endpoints", categories=["pattern", "warning"])
        recall("database")  # Before making DB changes
    """
    await db_manager.init_db()
    return await memory_manager.recall(
        topic=topic,
        categories=categories,
        limit=limit
    )


# ============================================================================
# Tool 3: ADD_RULE - Create a decision tree node
# ============================================================================
@mcp.tool()
async def add_rule(
    trigger: str,
    must_do: Optional[List[str]] = None,
    must_not: Optional[List[str]] = None,
    ask_first: Optional[List[str]] = None,
    warnings: Optional[List[str]] = None,
    priority: int = 0
) -> Dict[str, Any]:
    """
    Add a rule to the decision tree. Rules provide automatic guidance.

    When an action matches a rule's trigger, the AI gets guidance on:
    - What MUST be done
    - What MUST NOT be done
    - What questions to ask first
    - What warnings to consider

    Args:
        trigger: What activates this rule (natural language, e.g., "adding new API endpoint")
        must_do: Things that must be done when this rule applies
        must_not: Things that must be avoided
        ask_first: Questions to consider before proceeding
        warnings: Warnings from past experience
        priority: Higher priority rules are shown first (default: 0)

    Returns:
        The created rule

    Examples:
        add_rule(
            trigger="adding new API endpoint",
            must_do=["Add rate limiting", "Add to OpenAPI spec", "Write integration test"],
            must_not=["Use synchronous database calls"],
            ask_first=["Is this a breaking change?", "Does this need authentication?"]
        )

        add_rule(
            trigger="modifying database schema",
            must_do=["Create migration", "Test rollback", "Update seed data"],
            warnings=["Schema change on 2024-10-01 caused 2hr outage"]
        )
    """
    await db_manager.init_db()
    return await rules_engine.add_rule(
        trigger=trigger,
        must_do=must_do,
        must_not=must_not,
        ask_first=ask_first,
        warnings=warnings,
        priority=priority
    )


# ============================================================================
# Tool 4: CHECK_RULES - Validate an action against rules
# ============================================================================
@mcp.tool()
async def check_rules(
    action: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Check if an action triggers any rules and get guidance.

    Call this BEFORE taking any significant action to get:
    - Matching rules for this type of action
    - Combined must_do / must_not guidance
    - Relevant warnings
    - Questions to consider

    Args:
        action: Description of what you're about to do
        context: Optional context (files involved, etc.)

    Returns:
        Matching rules and combined guidance

    Examples:
        check_rules("adding a new REST endpoint for user profiles")
        check_rules("modifying the authentication middleware")
        check_rules("updating the database schema to add a new column")
    """
    await db_manager.init_db()
    return await rules_engine.check_rules(action=action, context=context)


# ============================================================================
# Tool 5: RECORD_OUTCOME - Track if a decision worked
# ============================================================================
@mcp.tool()
async def record_outcome(
    memory_id: int,
    outcome: str,
    worked: bool
) -> Dict[str, Any]:
    """
    Record the outcome of a decision to learn from it.

    Use this after implementing a decision to track:
    - What actually happened
    - Whether it worked out

    Failed decisions inform future recalls - they become implicit warnings.

    Args:
        memory_id: The ID of the memory (returned from 'remember')
        outcome: Description of what happened
        worked: Did it work out? True/False

    Returns:
        Updated memory

    Examples:
        record_outcome(42, "JWT auth works well, no session issues", worked=True)
        record_outcome(43, "Caching caused stale data bugs", worked=False)
    """
    await db_manager.init_db()
    return await memory_manager.record_outcome(
        memory_id=memory_id,
        outcome=outcome,
        worked=worked
    )


# ============================================================================
# Tool 6: GET_BRIEFING - Session start summary
# ============================================================================
@mcp.tool()
async def get_briefing(
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get everything needed to start a session.

    Call this at the START of every conversation to get:
    - Memory statistics (how much context exists)
    - Recent decisions
    - Active warnings
    - High-priority rules

    This ensures the AI starts with full context awareness.

    Args:
        project_path: Optional project path (uses default if not specified)

    Returns:
        Session briefing with key information

    Example:
        get_briefing()  # At session start
    """
    await db_manager.init_db()

    # Get statistics
    stats = await memory_manager.get_statistics()

    # Get recent decisions (last 5)
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(Memory)
            .where(Memory.category == 'decision')
            .order_by(Memory.created_at.desc())
            .limit(5)
        )
        recent_decisions = [
            {"id": m.id, "content": m.content, "created_at": m.created_at.isoformat()}
            for m in result.scalars().all()
        ]

        # Get active warnings
        result = await session.execute(
            select(Memory)
            .where(Memory.category == 'warning')
            .order_by(Memory.created_at.desc())
            .limit(10)
        )
        active_warnings = [
            {"id": m.id, "content": m.content}
            for m in result.scalars().all()
        ]

        # Get high-priority rules
        result = await session.execute(
            select(Rule)
            .where(Rule.enabled == True)  # noqa: E712
            .order_by(Rule.priority.desc())
            .limit(5)
        )
        top_rules = [
            {"id": r.id, "trigger": r.trigger, "priority": r.priority}
            for r in result.scalars().all()
        ]

    return {
        "status": "ready",
        "statistics": stats,
        "recent_decisions": recent_decisions,
        "active_warnings": active_warnings,
        "top_rules": top_rules,
        "message": (
            f"DevilMCP ready. {stats['total_memories']} memories stored. "
            f"{len(active_warnings)} active warnings. "
            f"{len(top_rules)} rules configured."
        )
    }


# ============================================================================
# Utility: SEARCH - Full text search across memories
# ============================================================================
@mcp.tool()
async def search_memories(
    query: str,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Search across all memories with a text query.

    Use this when you need to find specific memories by content.

    Args:
        query: Search text
        limit: Maximum results (default: 20)

    Returns:
        Matching memories
    """
    await db_manager.init_db()
    return await memory_manager.search(query=query, limit=limit)


# ============================================================================
# Utility: LIST_RULES - See all configured rules
# ============================================================================
@mcp.tool()
async def list_rules(
    enabled_only: bool = True,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    List all configured rules.

    Args:
        enabled_only: Only show enabled rules (default: True)
        limit: Maximum results (default: 50)

    Returns:
        List of rules
    """
    await db_manager.init_db()
    return await rules_engine.list_rules(enabled_only=enabled_only, limit=limit)


# ============================================================================
# Utility: UPDATE_RULE - Modify existing rules
# ============================================================================
@mcp.tool()
async def update_rule(
    rule_id: int,
    must_do: Optional[List[str]] = None,
    must_not: Optional[List[str]] = None,
    ask_first: Optional[List[str]] = None,
    warnings: Optional[List[str]] = None,
    priority: Optional[int] = None,
    enabled: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Update an existing rule.

    Args:
        rule_id: ID of the rule to update
        must_do: New must_do list (replaces existing)
        must_not: New must_not list (replaces existing)
        ask_first: New ask_first list (replaces existing)
        warnings: New warnings list (replaces existing)
        priority: New priority
        enabled: Enable/disable rule

    Returns:
        Updated rule or error
    """
    await db_manager.init_db()
    return await rules_engine.update_rule(
        rule_id=rule_id,
        must_do=must_do,
        must_not=must_not,
        ask_first=ask_first,
        warnings=warnings,
        priority=priority,
        enabled=enabled
    )


# ============================================================================
# Cleanup
# ============================================================================
def cleanup():
    """Cleanup on exit."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(db_manager.close())
        else:
            loop.run_until_complete(db_manager.close())
    except Exception:
        pass


atexit.register(cleanup)


# ============================================================================
# Entry point
# ============================================================================
def main():
    """Run the MCP server."""
    import asyncio

    logger.info("Starting DevilMCP server...")
    logger.info(f"Storage: {storage_path}")

    # Initialize database
    try:
        asyncio.run(db_manager.init_db())
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    # Run MCP server
    try:
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    main()
