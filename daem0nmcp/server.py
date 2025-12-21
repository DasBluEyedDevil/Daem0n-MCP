"""
Daem0nMCP Server - AI Memory System with Semantic Understanding

NOTE: On Windows, stdio may hang. Set PYTHONUNBUFFERED=1 or run with -u flag.

A smarter MCP server that provides:
1. Semantic memory storage and retrieval (TF-IDF + optional vectors)
2. Time-weighted recall (recent memories matter more, but patterns/warnings are permanent)
3. Conflict detection (warns about contradicting decisions)
4. Rule-based decision trees for consistent AI behavior
5. Outcome tracking for continuous learning
6. File-level memory associations
7. Git awareness (shows changes since last session)
8. Tech debt scanning (finds TODO/FIXME/HACK comments)
9. External documentation ingestion
10. Refactor proposal generation
11. Data export/import for backup and migration
12. Memory maintenance (pin, archive, prune)

22 Tools:
- remember: Store a decision, pattern, warning, or learning (with file association)
- recall: Retrieve relevant memories for a topic (semantic search)
- recall_for_file: Get all memories for a specific file
- add_rule: Add a decision tree node
- check_rules: Validate an action against rules
- record_outcome: Track whether a decision worked
- get_briefing: Get everything needed to start a session (with git changes)
- context_check: Quick pre-flight check (recall + rules combined)
- search_memories: Search across all memories
- list_rules: Show all rules
- update_rule: Modify existing rule
- find_related: Discover connected memories
- scan_todos: Find TODO/FIXME/HACK comments and track as tech debt
- ingest_doc: Fetch and store external documentation as learnings
- propose_refactor: Generate refactor suggestions based on memory context
- rebuild_index: Force rebuild of all search indexes
- export_data: Export all memories and rules as JSON (backup/migration)
- import_data: Import memories and rules from exported JSON
- pin_memory: Pin/unpin memories to prevent pruning
- archive_memory: Archive/restore memories (hidden from recall)
- prune_memories: Remove old, low-value memories
- health: Get server health, version, and statistics
"""

import sys
import os
import re
import logging
import atexit
import subprocess
import asyncio
import base64
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("ERROR: fastmcp not installed. Run: pip install fastmcp", file=sys.stderr)
    sys.exit(1)

try:
    from .config import settings
    from .database import DatabaseManager
    from .memory import MemoryManager
    from .rules import RulesEngine
    from .models import Memory, Rule
    from . import __version__
    from . import vectors
except ImportError:
    # For fastmcp run which executes server.py directly
    from daem0nmcp.config import settings
    from daem0nmcp.database import DatabaseManager
    from daem0nmcp.memory import MemoryManager
    from daem0nmcp.rules import RulesEngine
    from daem0nmcp.models import Memory, Rule
    from daem0nmcp import __version__
    from daem0nmcp import vectors
from sqlalchemy import select, desc
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("Daem0nMCP")


# ============================================================================
# PROJECT CONTEXT MANAGEMENT - Support multiple projects via HTTP transport
# ============================================================================
@dataclass
class ProjectContext:
    """Holds all managers for a specific project."""
    project_path: str
    storage_path: str
    db_manager: DatabaseManager
    memory_manager: MemoryManager
    rules_engine: RulesEngine
    initialized: bool = False
    last_accessed: float = 0.0  # For LRU tracking


# Cache of project contexts by normalized path
_project_contexts: Dict[str, ProjectContext] = {}
_context_locks: Dict[str, asyncio.Lock] = {}
_contexts_lock = asyncio.Lock()  # Lock for modifying the dicts themselves

# Default project path (ONLY used if DAEM0NMCP_PROJECT_ROOT is explicitly set)
_default_project_path: Optional[str] = os.environ.get('DAEM0NMCP_PROJECT_ROOT')


def _missing_project_path_error() -> Dict[str, Any]:
    """Return an error dict when project_path is not provided."""
    return {
        "error": "MISSING_PROJECT_PATH",
        "message": (
            "The project_path parameter is REQUIRED. "
            "The Daem0n serves multiple realms - you must specify which project's memories to access. "
            "Pass your current working directory as project_path. "
            "Example: project_path='C:/Users/you/projects/myapp' or project_path='/home/you/projects/myapp'"
        ),
        "hint": "Run 'pwd' in bash to get your current directory, or check your Claude Code session header."
    }


def _normalize_path(path: str) -> str:
    """Normalize a path for consistent cache keys."""
    if path is None:
        raise ValueError("Cannot normalize None path")
    return str(Path(path).resolve())


def _get_storage_for_project(project_path: str) -> str:
    """Get the storage path for a project."""
    return str(Path(project_path) / ".daem0nmcp" / "storage")


async def get_project_context(project_path: Optional[str] = None) -> ProjectContext:
    """
    Get or create a ProjectContext for the given project path.
    Thread-safe with per-project locking to prevent race conditions.

    This enables the HTTP server to handle multiple projects simultaneously,
    each with its own isolated database.

    Args:
        project_path: Path to the project root. If None, uses default.

    Returns:
        ProjectContext with initialized managers for that project.
    """
    import time

    # Use default if not specified
    if not project_path:
        project_path = _default_project_path

    # Normalize for consistent caching - validate project_path is not None
    if not project_path:
        raise ValueError("project_path is required when DAEM0NMCP_PROJECT_ROOT is not set")
    normalized = _normalize_path(project_path)

    # Fast path: context exists and is initialized
    if normalized in _project_contexts:
        ctx = _project_contexts[normalized]
        if ctx.initialized:
            ctx.last_accessed = time.time()
            # Opportunistic eviction: trigger background cleanup if over limit
            if len(_project_contexts) > MAX_PROJECT_CONTEXTS:
                asyncio.create_task(evict_stale_contexts())
            return ctx

    # Get or create lock for this project
    async with _contexts_lock:
        if normalized not in _context_locks:
            _context_locks[normalized] = asyncio.Lock()
        lock = _context_locks[normalized]

    # Initialize under project-specific lock
    async with lock:
        # Double-check after acquiring lock
        if normalized in _project_contexts:
            ctx = _project_contexts[normalized]
            if ctx.initialized:
                ctx.last_accessed = time.time()
                return ctx

        # Create new context
        storage_path = _get_storage_for_project(normalized)
        db_mgr = DatabaseManager(storage_path)
        mem_mgr = MemoryManager(db_mgr)
        rules_eng = RulesEngine(db_mgr)

        ctx = ProjectContext(
            project_path=normalized,
            storage_path=storage_path,
            db_manager=db_mgr,
            memory_manager=mem_mgr,
            rules_engine=rules_eng,
            initialized=False,
            last_accessed=time.time()
        )

        # Initialize database
        await db_mgr.init_db()
        ctx.initialized = True

        _project_contexts[normalized] = ctx
        logger.info(f"Created project context for: {normalized} (storage: {storage_path})")

        return ctx


# Configuration constants (read from settings)
MAX_PROJECT_CONTEXTS = settings.max_project_contexts
CONTEXT_TTL_SECONDS = settings.context_ttl_seconds

# Ingestion limits
MAX_CONTENT_SIZE = settings.max_content_size
MAX_CHUNKS = settings.max_chunks
INGEST_TIMEOUT = settings.ingest_timeout
ALLOWED_URL_SCHEMES = settings.allowed_url_schemes


async def evict_stale_contexts() -> int:
    """
    Evict stale project contexts based on LRU and TTL policies.

    Returns the number of contexts evicted.
    """
    import time

    evicted = 0
    now = time.time()

    async with _contexts_lock:
        # First pass: TTL eviction
        ttl_expired = [
            path for path, ctx in _project_contexts.items()
            if (now - ctx.last_accessed) > CONTEXT_TTL_SECONDS
        ]

        for path in ttl_expired:
            ctx = _project_contexts.pop(path)
            try:
                await ctx.db_manager.close()
            except Exception as e:
                logger.warning(f"Error closing context for {path}: {e}")
            evicted += 1
            logger.info(f"Evicted TTL-expired context: {path}")

        # Second pass: LRU eviction if still over limit
        while len(_project_contexts) > MAX_PROJECT_CONTEXTS:
            # Find oldest context
            oldest_path = min(
                _project_contexts.keys(),
                key=lambda p: _project_contexts[p].last_accessed
            )
            ctx = _project_contexts.pop(oldest_path)
            try:
                await ctx.db_manager.close()
            except Exception as e:
                logger.warning(f"Error closing context for {oldest_path}: {e}")
            evicted += 1
            logger.info(f"Evicted LRU context: {oldest_path}")

        # Clean up orphaned locks
        orphaned_locks = set(_context_locks.keys()) - set(_project_contexts.keys())
        for path in orphaned_locks:
            del _context_locks[path]

    return evicted


async def cleanup_all_contexts():
    """Clean up all project contexts on shutdown."""
    for path, ctx in _project_contexts.items():
        try:
            await ctx.db_manager.close()
            logger.info(f"Closed database for: {path}")
        except Exception as e:
            logger.warning(f"Error closing database for {path}: {e}")
    _project_contexts.clear()


# Legacy global references for backward compatibility
# These point to the default project context
storage_path = settings.get_storage_path()
db_manager = DatabaseManager(storage_path)
memory_manager = MemoryManager(db_manager)
rules_engine = RulesEngine(db_manager)

logger.info(f"Daem0nMCP Server initialized (default storage: {storage_path})")


# ============================================================================
# Tool 1: REMEMBER - Store a memory with conflict detection
# ============================================================================
@mcp.tool()
async def remember(
    category: str,
    content: str,
    rationale: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
    file_path: Optional[str] = None,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Store a decision, pattern, warning, or learning in long-term memory.

    FEATURES:
    - Conflict detection: Warns if this contradicts a past failure
    - File association: Link memories to specific files
    - Auto-permanent: Patterns and warnings don't decay (they're project facts)

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
        file_path: Optional file path to associate this memory with
        project_path: Project root path (for multi-project HTTP server support)

    Returns:
        The created memory with its ID, plus any conflict warnings

    Examples:
        remember("decision", "Use JWT tokens instead of sessions",
                 rationale="Need stateless auth for horizontal scaling",
                 tags=["auth", "architecture"])

        remember("warning", "Don't use sync DB calls in request handlers",
                 rationale="Caused timeout issues in production",
                 file_path="api/handlers.py")

        remember("pattern", "All API routes must have rate limiting",
                 file_path="api/routes.py")
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)
    return await ctx.memory_manager.remember(
        category=category,
        content=content,
        rationale=rationale,
        context=context,
        tags=tags,
        file_path=file_path
    )


# ============================================================================
# Tool 2: RECALL - Semantic memory retrieval with decay
# ============================================================================
@mcp.tool()
async def recall(
    topic: str,
    categories: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    file_path: Optional[str] = None,
    limit: int = 10,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Recall memories relevant to a topic using SEMANTIC SIMILARITY.

    This uses TF-IDF matching, not just keywords - it understands related concepts.
    Results are weighted by:
    - Semantic relevance to your query
    - Recency (recent memories score higher)
    - Importance (warnings and failed decisions are boosted)

    Call this before working on any feature to get:
    - Past decisions about this area
    - Patterns that should be followed
    - Warnings about what to avoid (including failed approaches)
    - Learnings from previous work

    Args:
        topic: What you're looking for (e.g., "authentication", "database schema")
        categories: Limit to specific categories (default: all)
        tags: Filter to memories with specific tags
        file_path: Filter to memories for a specific file
        limit: Max memories per category (default: 10)
        project_path: Project root path (for multi-project HTTP server support)

    Returns:
        Categorized memories with relevance scores and failure warnings

    Examples:
        recall("authentication")  # Get all memories about auth
        recall("API endpoints", categories=["pattern", "warning"])
        recall("database")  # Before making DB changes
        recall("Redis", tags=["cache"])  # Only memories tagged with cache
        recall("sync calls", file_path="api/handlers.py")  # Only for specific file
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)
    return await ctx.memory_manager.recall(
        topic=topic,
        categories=categories,
        tags=tags,
        file_path=file_path,
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
    priority: int = 0,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Add a rule to the decision tree. Rules provide automatic guidance.

    Rules are matched SEMANTICALLY - you don't need exact keyword matches.
    "adding API endpoint" will match "creating a new REST route".

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
        project_path: Project root path (for multi-project HTTP server support)

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
            warnings=["Schema change on 2024-10-01 caused 2hr outage"],
            priority=10  # High priority
        )
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)
    return await ctx.rules_engine.add_rule(
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
    context: Optional[Dict[str, Any]] = None,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Check if an action triggers any rules and get guidance.

    Uses SEMANTIC matching - "creating REST endpoint" will match rules about "adding API routes".

    Call this BEFORE taking any significant action to get:
    - Matching rules for this type of action
    - Combined must_do / must_not guidance
    - Relevant warnings
    - Questions to consider

    Args:
        action: Description of what you're about to do
        context: Optional context (files involved, etc.)
        project_path: Project root path (for multi-project HTTP server support)

    Returns:
        Matching rules and combined guidance with severity indicator

    Examples:
        check_rules("adding a new REST endpoint for user profiles")
        check_rules("modifying the authentication middleware")
        check_rules("updating the database schema to add a new column")
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)
    return await ctx.rules_engine.check_rules(action=action, context=context)


# ============================================================================
# Tool 5: RECORD_OUTCOME - Track if a decision worked
# ============================================================================
@mcp.tool()
async def record_outcome(
    memory_id: int,
    outcome: str,
    worked: bool,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Record the outcome of a decision to learn from it.

    IMPORTANT: Failed decisions become implicit warnings that get BOOSTED
    in future recalls. This is how the system learns.

    Use this after implementing a decision to track:
    - What actually happened
    - Whether it worked out

    Args:
        memory_id: The ID of the memory (returned from 'remember')
        outcome: Description of what happened
        worked: Did it work? True/False
        project_path: Project root path (for multi-project HTTP server support)

    Returns:
        Updated memory, with suggestions if it failed

    Examples:
        record_outcome(42, "JWT auth works well, no session issues", worked=True)
        record_outcome(43, "Caching caused stale data bugs", worked=False)
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)
    return await ctx.memory_manager.record_outcome(
        memory_id=memory_id,
        outcome=outcome,
        worked=worked
    )


# ============================================================================
# Helper: Git awareness
# ============================================================================
def _get_git_changes(since_date: Optional[datetime] = None, project_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get git changes since a given date.

    Args:
        since_date: Only show commits since this date
        project_path: Directory to run git commands in (defaults to CWD)
    """
    try:
        # Use project_path as working directory for git commands
        cwd = project_path if project_path else None

        # Check if we're in a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd
        )
        if result.returncode != 0:
            return None

        git_info = {}

        # Get recent commits
        if since_date:
            since_str = since_date.strftime("%Y-%m-%d")
            cmd = ["git", "log", f"--since={since_str}", "--oneline", "-10"]
        else:
            cmd = ["git", "log", "--oneline", "-5"]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5, cwd=cwd)
        if result.returncode == 0 and result.stdout.strip():
            git_info["recent_commits"] = result.stdout.strip().split("\n")

        # Get changed files (uncommitted)
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd
        )
        if result.returncode == 0 and result.stdout.strip():
            changes = result.stdout.strip().split("\n")
            git_info["uncommitted_changes"] = [
                {"status": line[:2].strip(), "file": line[3:]}
                for line in changes if line.strip()
            ]

        # Get current branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd
        )
        if result.returncode == 0:
            git_info["branch"] = result.stdout.strip()

        return git_info if git_info else None

    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return None


# ============================================================================
# Tool 6: GET_BRIEFING - Smart session start summary
# ============================================================================
@mcp.tool()
async def get_briefing(
    project_path: Optional[str] = None,
    focus_areas: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Get everything needed to start a session - call this FIRST.

    Returns:
    - Memory statistics and learning insights
    - Recent decisions (what changed lately)
    - Active warnings (what to watch out for)
    - High-priority rules (what to always check)
    - Failed approaches (what not to repeat)
    - Git changes since last memory (what happened while you were away)

    If you provide focus_areas, you'll also get relevant memories for those topics.

    Args:
        project_path: Project root path (IMPORTANT for multi-project support - pass your current working directory)
        focus_areas: Optional list of topics to pre-fetch memories for

    Returns:
        Complete session briefing with actionable context

    Example:
        get_briefing()  # Basic briefing
        get_briefing(project_path="/path/to/project")  # Explicit project
        get_briefing(focus_areas=["authentication", "API"])  # With pre-loaded context
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    # Get statistics with learning insights
    stats = await ctx.memory_manager.get_statistics()

    # Get most recent memory timestamp for git awareness
    last_memory_date = None

    async with ctx.db_manager.get_session() as session:
        # Get most recent memory
        result = await session.execute(
            select(Memory.created_at)
            .order_by(Memory.created_at.desc())
            .limit(1)
        )
        row = result.first()
        if row:
            last_memory_date = row[0]

        # Get recent decisions (last 5)
        result = await session.execute(
            select(Memory)
            .where(Memory.category == 'decision')
            .order_by(Memory.created_at.desc())
            .limit(5)
        )
        recent_decisions = [
            {
                "id": m.id,
                "content": m.content,
                "worked": m.worked,
                "created_at": m.created_at.isoformat()
            }
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

        # Get FAILED decisions - these are critical
        result = await session.execute(
            select(Memory)
            .where(Memory.worked == False)  # noqa: E712
            .order_by(Memory.created_at.desc())
            .limit(5)
        )
        failed_approaches = [
            {
                "id": m.id,
                "content": m.content,
                "outcome": m.outcome,
                "category": m.category
            }
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
            {
                "id": r.id,
                "trigger": r.trigger,
                "priority": r.priority,
                "has_warnings": len(r.warnings) > 0
            }
            for r in result.scalars().all()
        ]

    # Get git changes since last memory (run in project directory)
    git_changes = _get_git_changes(last_memory_date, project_path=ctx.project_path)

    # Pre-fetch memories for focus areas if specified
    focus_memories = {}
    if focus_areas:
        for area in focus_areas[:3]:  # Limit to 3 areas
            memories = await ctx.memory_manager.recall(area, limit=5)
            focus_memories[area] = {
                "found": memories.get("found", 0),
                "summary": memories.get("summary"),
                "has_warnings": len(memories.get("warnings", [])) > 0,
                "has_failed": any(
                    m.get("worked") is False
                    for cat in ["decisions", "patterns", "learnings"]
                    for m in memories.get(cat, [])
                )
            }

    # Build actionable message
    message_parts = [f"Daem0nMCP ready. {stats['total_memories']} memories stored."]

    if failed_approaches:
        message_parts.append(f"[WARNING] {len(failed_approaches)} failed approaches to avoid!")

    if active_warnings:
        message_parts.append(f"{len(active_warnings)} active warnings.")

    if git_changes and git_changes.get("uncommitted_changes"):
        message_parts.append(f"{len(git_changes['uncommitted_changes'])} uncommitted file(s).")

    if stats.get("learning_insights", {}).get("suggestion"):
        message_parts.append(stats["learning_insights"]["suggestion"])

    return {
        "status": "ready",
        "statistics": stats,
        "recent_decisions": recent_decisions,
        "active_warnings": active_warnings,
        "failed_approaches": failed_approaches,
        "top_rules": top_rules,
        "git_changes": git_changes,
        "focus_areas": focus_memories if focus_memories else None,
        "message": " ".join(message_parts)
    }


# ============================================================================
# Tool 7: SEARCH - Full text search across memories
# ============================================================================
@mcp.tool()
async def search_memories(
    query: str,
    limit: int = 20,
    project_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Search across all memories with semantic similarity.

    Use this when you need to find specific memories by content.
    Uses TF-IDF matching for better results than exact text search.

    Args:
        query: Search text
        limit: Maximum results (default: 20)
        project_path: Project root path (for multi-project HTTP server support)

    Returns:
        Matching memories ranked by relevance
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)
    return await ctx.memory_manager.search(query=query, limit=limit)


# ============================================================================
# Tool 8: LIST_RULES - See all configured rules
# ============================================================================
@mcp.tool()
async def list_rules(
    enabled_only: bool = True,
    limit: int = 50,
    project_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all configured rules.

    Args:
        enabled_only: Only show enabled rules (default: True)
        limit: Maximum results (default: 50)
        project_path: Project root path (for multi-project HTTP server support)

    Returns:
        List of rules with their guidance
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)
    return await ctx.rules_engine.list_rules(enabled_only=enabled_only, limit=limit)


# ============================================================================
# Tool 9: UPDATE_RULE - Modify existing rules
# ============================================================================
@mcp.tool()
async def update_rule(
    rule_id: int,
    must_do: Optional[List[str]] = None,
    must_not: Optional[List[str]] = None,
    ask_first: Optional[List[str]] = None,
    warnings: Optional[List[str]] = None,
    priority: Optional[int] = None,
    enabled: Optional[bool] = None,
    project_path: Optional[str] = None
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
        project_path: Project root path (for multi-project HTTP server support)

    Returns:
        Updated rule or error
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)
    return await ctx.rules_engine.update_rule(
        rule_id=rule_id,
        must_do=must_do,
        must_not=must_not,
        ask_first=ask_first,
        warnings=warnings,
        priority=priority,
        enabled=enabled
    )


# ============================================================================
# Tool 10: FIND_RELATED - Discover connected memories
# ============================================================================
@mcp.tool()
async def find_related(
    memory_id: int,
    limit: int = 5,
    project_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Find memories related to a specific memory.

    Useful for exploring connected decisions and understanding context.
    Uses semantic similarity to find related content.

    Args:
        memory_id: ID of the memory to find related content for
        limit: Maximum related memories to return (default: 5)
        project_path: Project root path (for multi-project HTTP server support)

    Returns:
        List of related memories with similarity scores

    Example:
        # After seeing a decision about auth, find related patterns/warnings
        find_related(42)
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)
    return await ctx.memory_manager.find_related(memory_id=memory_id, limit=limit)


# ============================================================================
# Tool 11: CONTEXT_CHECK - Quick relevance check for current work
# ============================================================================
@mcp.tool()
async def context_check(
    description: str,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Quick check for any relevant memories and rules for what you're about to do.

    Combines recall and check_rules in one call. Use this as a fast
    pre-flight check before making changes.

    Args:
        description: Brief description of what you're working on
        project_path: Project root path (for multi-project HTTP server support)

    Returns:
        Combined results: relevant memories, matching rules, and any warnings

    Example:
        context_check("modifying the user authentication flow")
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    # Get relevant memories
    memories = await ctx.memory_manager.recall(description, limit=5)

    # Check rules
    rules = await ctx.rules_engine.check_rules(description)

    # Collect all warnings
    warnings = []

    # From memories
    for cat in ['warnings', 'decisions', 'patterns', 'learnings']:
        for mem in memories.get(cat, []):
            if mem.get('worked') is False:
                warnings.append({
                    "source": "failed_decision",
                    "content": mem['content'],
                    "outcome": mem.get('outcome')
                })
            elif cat == 'warnings':
                warnings.append({
                    "source": "warning",
                    "content": mem['content']
                })

    # From rules
    if rules.get('guidance', {}).get('warnings'):
        for w in rules['guidance']['warnings']:
            warnings.append({
                "source": "rule",
                "content": w
            })

    has_concerns = len(warnings) > 0 or rules.get('has_blockers', False)

    return {
        "description": description,
        "has_concerns": has_concerns,
        "memories_found": memories.get('found', 0),
        "rules_matched": rules.get('matched_rules', 0),
        "warnings": warnings,
        "must_do": rules.get('guidance', {}).get('must_do', []),
        "must_not": rules.get('guidance', {}).get('must_not', []),
        "ask_first": rules.get('guidance', {}).get('ask_first', []),
        "message": (
            "⚠️ Review warnings before proceeding" if has_concerns else
            "✓ No concerns found, but always use good judgment"
        )
    }


# ============================================================================
# Tool 12: RECALL_FOR_FILE - Get memories for a specific file
# ============================================================================
@mcp.tool()
async def recall_for_file(
    file_path: str,
    limit: int = 10,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get all memories associated with a specific file.

    Use this when opening or modifying a file to see:
    - Past decisions about this file
    - Patterns that apply
    - Warnings about potential issues
    - Failed approaches to avoid

    Args:
        file_path: The file path to look up
        limit: Max memories to return (default: 10)
        project_path: Project root path (for multi-project HTTP server support)

    Returns:
        Memories organized by category with warning indicators

    Example:
        recall_for_file("api/handlers.py")
        recall_for_file("src/components/Auth.tsx")
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)
    return await ctx.memory_manager.recall_for_file(file_path=file_path, limit=limit)


# ============================================================================
# Helper: TODO/FIXME Scanner
# ============================================================================
# Pattern matches TODO, FIXME, HACK, XXX, BUG, NOTE with optional colon and content
TODO_PATTERN = re.compile(
    r'(?:#|//|/\*|\*|--|<!--|\'\'\'|""")\s*'  # Comment markers
    r'(TODO|FIXME|HACK|XXX|BUG)\s*'  # Keywords (NOT matching NOTE - too noisy)
    r':?\s*'  # Optional colon
    r'(.+?)(?:\*/|-->|\'\'\'|"""|$)',  # Content until end marker
    re.IGNORECASE
)

# File extensions to scan
SCANNABLE_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.c', '.cpp', '.h', '.hpp',
    '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala', '.sh', '.bash',
    '.html', '.css', '.scss', '.sass', '.less', '.vue', '.svelte',
    '.sql', '.yaml', '.yml', '.toml', '.json', '.md', '.rst', '.txt'
}

# Directories to skip
SKIP_DIRS = {
    '.git', '.svn', '.hg', 'node_modules', '__pycache__', '.pytest_cache',
    'venv', '.venv', 'env', '.env', 'dist', 'build', '.tox', '.eggs',
    '*.egg-info', '.mypy_cache', '.coverage', 'htmlcov', '.daem0nmcp'
}


def _scan_for_todos(root_path: str, max_files: int = 500) -> List[Dict[str, Any]]:
    """Scan directory for TODO/FIXME/HACK comments."""
    todos = []
    files_scanned = 0
    root = Path(root_path)

    if not root.exists():
        return []

    for file_path in root.rglob('*'):
        # Skip directories
        if file_path.is_dir():
            continue

        # Check if any parent is a skip directory
        skip = False
        for part in file_path.parts:
            if part in SKIP_DIRS or part.endswith('.egg-info'):
                skip = True
                break
        if skip:
            continue

        # Check extension
        if file_path.suffix.lower() not in SCANNABLE_EXTENSIONS:
            continue

        # Limit files scanned
        files_scanned += 1
        if files_scanned > max_files:
            break

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            for line_num, line in enumerate(content.split('\n'), 1):
                matches = TODO_PATTERN.findall(line)
                for match in matches:
                    keyword, text = match
                    text = text.strip()
                    if text and len(text) > 3:  # Skip empty or very short todos
                        rel_path = str(file_path.relative_to(root))
                        todos.append({
                            'type': keyword.upper(),
                            'content': text[:200],  # Truncate long content
                            'file': rel_path,
                            'line': line_num,
                            'full_line': line.strip()[:300]
                        })
        except (OSError, UnicodeDecodeError):
            continue

    return todos


# ============================================================================
# Tool 13: SCAN_TODOS - Find tech debt in codebase
# ============================================================================
@mcp.tool()
async def scan_todos(
    path: Optional[str] = None,
    auto_remember: bool = False,
    types: Optional[List[str]] = None,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Scan the codebase for TODO, FIXME, HACK, XXX, and BUG comments.

    Tech debt finder - discovers and optionally tracks code comments that
    indicate incomplete work, known issues, or workarounds.

    Args:
        path: Directory to scan (defaults to project directory)
        auto_remember: If True, automatically create warning memories for each TODO
        types: Filter to specific types (e.g., ["FIXME", "HACK"]) - default: all
        project_path: Path to the project root (for multi-project support)

    Returns:
        List of found items grouped by type, with file locations

    Examples:
        scan_todos()  # Scan current directory
        scan_todos(types=["FIXME", "HACK"])  # Only critical items
        scan_todos(auto_remember=True)  # Scan and save as warnings
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    # Use provided path, or fall back to project path
    scan_path = path or ctx.project_path
    found_todos = _scan_for_todos(scan_path)

    # Filter by types if specified
    if types:
        types_upper = [t.upper() for t in types]
        found_todos = [t for t in found_todos if t['type'] in types_upper]

    # Group by type
    by_type: Dict[str, List] = {}
    for todo in found_todos:
        todo_type = todo['type']
        if todo_type not in by_type:
            by_type[todo_type] = []
        by_type[todo_type].append(todo)

    # Get existing todo-related memories to avoid duplicates
    existing_todos = set()
    async with ctx.db_manager.get_session() as session:
        result = await session.execute(
            select(Memory)
            .where(Memory.tags.contains('"tech_debt"'))  # JSON contains check
        )
        for mem in result.scalars().all():
            # Create a simple signature to check duplicates
            if mem.file_path:
                existing_todos.add(f"{mem.file_path}:{mem.content[:50]}")

    # Auto-remember if requested
    new_memories = []
    if auto_remember:
        for todo in found_todos:
            sig = f"{todo['file']}:{todo['content'][:50]}"
            if sig not in existing_todos:
                memory = await ctx.memory_manager.remember(
                    category='warning',
                    content=f"{todo['type']}: {todo['content']}",
                    rationale=f"Found in codebase at {todo['file']}:{todo['line']}",
                    tags=['tech_debt', 'auto_scanned', todo['type'].lower()],
                    file_path=todo['file']
                )
                new_memories.append(memory)
                existing_todos.add(sig)  # Prevent duplicates in same scan

    # Build summary
    summary_parts = []
    for todo_type in ['FIXME', 'HACK', 'BUG', 'XXX', 'TODO']:
        if todo_type in by_type:
            count = len(by_type[todo_type])
            summary_parts.append(f"{count} {todo_type}")

    return {
        "total_found": len(found_todos),
        "by_type": by_type,
        "summary": ", ".join(summary_parts) if summary_parts else "No tech debt found",
        "new_memories_created": len(new_memories) if auto_remember else 0,
        "message": (
            f"Found {len(found_todos)} tech debt items" +
            (f", created {len(new_memories)} new warnings" if new_memories else "")
        )
    }


# ============================================================================
# Helper: Web fetching for documentation ingestion
# ============================================================================
def _validate_url(url: str) -> Optional[str]:
    """
    Validate URL for ingestion.
    Returns error message if invalid, None if valid.

    Security checks:
    - Scheme validation (no file://, etc.)
    - SSRF protection: Blocks localhost and private IPs
    - Cloud metadata endpoint protection
    """
    from urllib.parse import urlparse
    import ipaddress
    import socket

    try:
        parsed = urlparse(url)
    except Exception:
        return "Invalid URL format"

    if parsed.scheme.lower() not in ALLOWED_URL_SCHEMES:
        return f"Invalid URL scheme '{parsed.scheme}'. Allowed: {ALLOWED_URL_SCHEMES}"

    if not parsed.netloc:
        return "URL must have a host"

    # Extract hostname from netloc (remove port)
    hostname = parsed.hostname
    if not hostname:
        return "URL must have a valid hostname"

    # Block localhost
    if hostname.lower() in ['localhost', 'localhost.localdomain', '127.0.0.1', '::1']:
        return "Localhost URLs are not allowed"

    # Try to resolve and check for private/reserved IPs
    try:
        ip = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip)

        # Block private, loopback, and link-local addresses
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
            return f"Private/internal IP addresses are not allowed: {ip}"

        # Block cloud metadata endpoint
        if str(ip_obj) == '169.254.169.254':
            return "Cloud metadata endpoints are not allowed"

    except socket.gaierror:
        # Hostname could not be resolved - allow it to fail later at fetch time
        pass
    except ValueError:
        # Not a valid IP address - allow it through
        pass

    return None


def _fetch_and_extract(url: str) -> Optional[str]:
    """Fetch URL and extract text content with size limits."""
    try:
        import httpx
        from bs4 import BeautifulSoup
    except ImportError:
        return None

    try:
        with httpx.Client(timeout=float(INGEST_TIMEOUT), follow_redirects=False) as client:
            response = client.get(url)
            response.raise_for_status()

            # Check content length header first
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > MAX_CONTENT_SIZE:
                logger.warning(f"Content too large: {content_length} bytes")
                return None

            # Truncate if response is too large
            text = response.text
            if len(text) > MAX_CONTENT_SIZE:
                logger.warning(f"Truncating content from {len(text)} to {MAX_CONTENT_SIZE}")
                text = text[:MAX_CONTENT_SIZE]

            soup = BeautifulSoup(text, 'html.parser')

            # Remove script and style elements
            for element in soup(['script', 'style', 'nav', 'footer', 'header']):
                element.decompose()

            # Get text
            text = soup.get_text(separator='\n', strip=True)

            # Clean up whitespace
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            return '\n'.join(lines)

    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None


# ============================================================================
# Tool 14: INGEST_DOC - Import external documentation
# ============================================================================
@mcp.tool()
async def ingest_doc(
    url: str,
    topic: str,
    chunk_size: int = 2000,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch external documentation and store it as permanent learnings.

    Use this to import knowledge from external sources:
    - API documentation (Stripe, Twilio, etc.)
    - Library docs (React, Django, etc.)
    - Team wikis or RFCs
    - Best practices guides

    The content is chunked and stored as permanent learnings that can be
    recalled later. Each chunk is tagged with the topic for easy retrieval.

    Args:
        url: The URL to fetch documentation from
        topic: Topic tag for organizing the docs (e.g., "stripe", "react-hooks")
        chunk_size: Max characters per memory chunk (default: 2000)
        project_path: Path to the project root (for multi-project support)

    Returns:
        Summary of ingested content

    Examples:
        ingest_doc("https://stripe.com/docs/api/charges", "stripe-charges")
        ingest_doc("https://react.dev/reference/react/hooks", "react-hooks")
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    # Validate input parameters
    if chunk_size <= 0:
        return {"error": "chunk_size must be positive", "url": url}

    if chunk_size > MAX_CONTENT_SIZE:
        return {"error": f"chunk_size cannot exceed {MAX_CONTENT_SIZE}", "url": url}

    if not topic or not topic.strip():
        return {"error": "topic cannot be empty", "url": url}

    # Validate URL
    url_error = _validate_url(url)
    if url_error:
        return {"error": url_error, "url": url}

    ctx = await get_project_context(project_path)

    content = _fetch_and_extract(url)

    if content is None:
        return {
            "error": f"Failed to fetch URL. Ensure httpx and beautifulsoup4 are installed, "
                     f"content is under {MAX_CONTENT_SIZE} bytes, and URL is accessible.",
            "url": url
        }

    if not content.strip():
        return {
            "error": "No text content found at URL",
            "url": url
        }

    # Chunk the content with limit
    chunks = []
    words = content.split()
    current_chunk = []
    current_size = 0

    for word in words:
        word_len = len(word) + 1  # +1 for space
        if current_size + word_len > chunk_size and current_chunk:
            chunks.append(' '.join(current_chunk))
            if len(chunks) >= MAX_CHUNKS:
                logger.warning(f"Reached max chunks ({MAX_CHUNKS}), stopping")
                break
            current_chunk = [word]
            current_size = word_len
        else:
            current_chunk.append(word)
            current_size += word_len

    if current_chunk and len(chunks) < MAX_CHUNKS:
        chunks.append(' '.join(current_chunk))

    # Store each chunk as a learning
    memories_created = []
    for i, chunk in enumerate(chunks):
        memory = await ctx.memory_manager.remember(
            category='learning',
            content=chunk[:500] + "..." if len(chunk) > 500 else chunk,
            rationale=f"Ingested from {url} (chunk {i+1}/{len(chunks)})",
            tags=['docs', 'ingested', topic],
            context={'source_url': url, 'chunk_index': i, 'total_chunks': len(chunks)}
        )
        memories_created.append(memory)

    return {
        "status": "success",
        "url": url,
        "topic": topic,
        "chunks_created": len(chunks),
        "total_chars": len(content),
        "truncated": len(chunks) >= MAX_CHUNKS,
        "message": f"Ingested {len(chunks)} chunks from {url}. Use recall('{topic}') to retrieve.",
        "memory_ids": [m.get('id') for m in memories_created if 'id' in m]
    }


# ============================================================================
# Tool 15: PROPOSE_REFACTOR - Generate refactor suggestions
# ============================================================================
@mcp.tool()
async def propose_refactor(
    file_path: str,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate refactor suggestions for a file based on memory context.

    Combines:
    - File-specific memories (past decisions, warnings)
    - TODO/FIXME comments in the file
    - Relevant rules and patterns

    Returns structured context that helps the AI agent propose
    informed refactoring decisions.

    Args:
        file_path: The file to analyze for refactoring
        project_path: Path to the project root (for multi-project support)

    Returns:
        Combined context with memories, todos, and suggested actions

    Example:
        propose_refactor("src/auth/handlers.py")
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    result = {
        "file_path": file_path,
        "memories": {},
        "todos": [],
        "rules": {},
        "constraints": [],
        "opportunities": []
    }

    # Get file-specific memories
    file_memories = await ctx.memory_manager.recall_for_file(file_path)
    result["memories"] = file_memories

    # Resolve file path relative to project directory
    absolute_file_path = Path(ctx.project_path) / file_path
    if not absolute_file_path.is_absolute():
        absolute_file_path = absolute_file_path.resolve()

    # Scan for TODOs in this specific file
    if absolute_file_path.exists():
        # Scan the file's directory and filter to just this file
        scan_dir = str(absolute_file_path.parent)
        file_todos = _scan_for_todos(scan_dir, max_files=100)
        target_filename = absolute_file_path.name
        result["todos"] = [t for t in file_todos if t['file'] == target_filename or t['file'].endswith(os.sep + target_filename)]

    # Check relevant rules
    filename = os.path.basename(file_path)
    rules = await ctx.rules_engine.check_rules(f"refactoring {filename}")
    result["rules"] = rules

    # Extract constraints from warnings and failed approaches
    for cat in ['warnings', 'decisions', 'patterns']:
        for mem in file_memories.get(cat, []):
            if mem.get('worked') is False:
                result["constraints"].append({
                    "type": "failed_approach",
                    "content": mem['content'],
                    "outcome": mem.get('outcome'),
                    "action": "AVOID this approach"
                })
            elif cat == 'warnings':
                result["constraints"].append({
                    "type": "warning",
                    "content": mem['content'],
                    "action": "Consider this warning"
                })

    # Identify opportunities from TODOs
    for todo in result["todos"]:
        result["opportunities"].append({
            "type": todo['type'],
            "content": todo['content'],
            "line": todo['line'],
            "action": f"Address this {todo['type']}"
        })

    # Build summary message
    num_constraints = len(result["constraints"])
    num_opportunities = len(result["opportunities"])
    num_memories = file_memories.get('found', 0)

    result["message"] = (
        f"Analysis for {file_path}: "
        f"{num_memories} memories, "
        f"{num_constraints} constraints, "
        f"{num_opportunities} opportunities"
    )

    if num_constraints > 0:
        result["message"] += " | Review constraints before refactoring!"

    return result


# ============================================================================
# Tool 16: REBUILD_INDEX - Force rebuild of search indexes
# ============================================================================
@mcp.tool()
async def rebuild_index(
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Force rebuild of all search indexes.

    Use this if search results seem stale or after bulk database operations.
    Rebuilds both memory TF-IDF/vector indexes and rule indexes.

    Args:
        project_path: Project root path

    Returns:
        Statistics about the rebuild
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    memory_stats = await ctx.memory_manager.rebuild_index()
    rules_stats = await ctx.rules_engine.rebuild_index()

    return {
        "status": "rebuilt",
        "memories": memory_stats,
        "rules": rules_stats,
        "message": f"Rebuilt indexes: {memory_stats['memories_indexed']} memories, {rules_stats['rules_indexed']} rules"
    }


@mcp.tool()
async def export_data(
    project_path: Optional[str] = None,
    include_vectors: bool = False
) -> Dict[str, Any]:
    """
    Export all memories and rules as JSON.

    Use for backup, migration, or sharing project knowledge.

    Args:
        project_path: Project root path
        include_vectors: Include vector embeddings (large, default False)

    Returns:
        JSON structure with all memories and rules
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    async with ctx.db_manager.get_session() as session:
        # Export memories
        result = await session.execute(select(Memory))
        memories = [
            {
                "id": m.id,
                "category": m.category,
                "content": m.content,
                "rationale": m.rationale,
                "context": m.context,
                "tags": m.tags,
                "file_path": m.file_path,
                "keywords": m.keywords,
                "is_permanent": m.is_permanent,
                "outcome": m.outcome,
                "worked": m.worked,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "updated_at": m.updated_at.isoformat() if m.updated_at else None,
                # Optionally include vectors (base64 encoded)
                "vector_embedding": (
                    base64.b64encode(m.vector_embedding).decode()
                    if include_vectors and m.vector_embedding else None
                )
            }
            for m in result.scalars().all()
        ]

        # Export rules
        result = await session.execute(select(Rule))
        rules = [
            {
                "id": r.id,
                "trigger": r.trigger,
                "trigger_keywords": r.trigger_keywords,
                "must_do": r.must_do,
                "must_not": r.must_not,
                "ask_first": r.ask_first,
                "warnings": r.warnings,
                "priority": r.priority,
                "enabled": r.enabled,
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            for r in result.scalars().all()
        ]

    return {
        "version": __version__,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "project_path": ctx.project_path,
        "memories": memories,
        "rules": rules
    }


@mcp.tool()
async def import_data(
    data: Dict[str, Any],
    project_path: Optional[str] = None,
    merge: bool = True
) -> Dict[str, Any]:
    """
    Import memories and rules from exported JSON.

    Args:
        data: Exported data structure (from export_data)
        project_path: Project root path
        merge: If True, add to existing data. If False, replace all.

    Returns:
        Import statistics
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    if "memories" not in data or "rules" not in data:
        return {"error": "Invalid data format. Expected 'memories' and 'rules' keys."}

    ctx = await get_project_context(project_path)

    memories_imported = 0
    rules_imported = 0

    async with ctx.db_manager.get_session() as session:
        # Import memories
        for mem_data in data.get("memories", []):
            # Decode vector if present
            vector_bytes = None
            if mem_data.get("vector_embedding"):
                try:
                    vector_bytes = base64.b64decode(mem_data["vector_embedding"])
                except Exception:
                    pass

            memory = Memory(
                category=mem_data["category"],
                content=mem_data["content"],
                rationale=mem_data.get("rationale"),
                context=mem_data.get("context", {}),
                tags=mem_data.get("tags", []),
                file_path=mem_data.get("file_path"),
                keywords=mem_data.get("keywords"),
                is_permanent=mem_data.get("is_permanent", False),
                outcome=mem_data.get("outcome"),
                worked=mem_data.get("worked"),
                vector_embedding=vector_bytes
            )
            session.add(memory)
            memories_imported += 1

        # Import rules
        for rule_data in data.get("rules", []):
            rule = Rule(
                trigger=rule_data["trigger"],
                trigger_keywords=rule_data.get("trigger_keywords"),
                must_do=rule_data.get("must_do", []),
                must_not=rule_data.get("must_not", []),
                ask_first=rule_data.get("ask_first", []),
                warnings=rule_data.get("warnings", []),
                priority=rule_data.get("priority", 0),
                enabled=rule_data.get("enabled", True)
            )
            session.add(rule)
            rules_imported += 1

    # Rebuild indexes
    await ctx.memory_manager.rebuild_index()
    await ctx.rules_engine.rebuild_index()

    return {
        "status": "imported",
        "memories_imported": memories_imported,
        "rules_imported": rules_imported,
        "message": f"Imported {memories_imported} memories and {rules_imported} rules"
    }


@mcp.tool()
async def pin_memory(
    memory_id: int,
    pinned: bool = True,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Pin or unpin a memory.

    Pinned memories:
    - Never pruned automatically
    - Get relevance boost in recall
    - Treated as permanent project knowledge

    Args:
        memory_id: Memory to pin/unpin
        pinned: True to pin, False to unpin
        project_path: Project root path
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    async with ctx.db_manager.get_session() as session:
        result = await session.execute(
            select(Memory).where(Memory.id == memory_id)
        )
        memory = result.scalar_one_or_none()

        if not memory:
            return {"error": f"Memory {memory_id} not found"}

        memory.pinned = pinned
        memory.is_permanent = pinned  # Pinned = permanent

        return {
            "id": memory_id,
            "pinned": pinned,
            "content": memory.content[:100],
            "message": f"Memory {'pinned' if pinned else 'unpinned'}"
        }


@mcp.tool()
async def prune_memories(
    older_than_days: int = 90,
    categories: Optional[List[str]] = None,
    dry_run: bool = True,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Prune old, low-value memories.

    By default, only affects episodic memories (decisions, learnings).
    Permanent memories (patterns, warnings), pinned, and memories with
    outcomes are protected.

    Args:
        older_than_days: Only prune memories older than this
        categories: Limit to these categories (default: decision, learning)
        dry_run: If True, just report what would be pruned
        project_path: Project root path
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    if categories is None:
        categories = ["decision", "learning"]

    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)

    async with ctx.db_manager.get_session() as session:
        # Find prunable memories
        query = select(Memory).where(
            Memory.category.in_(categories),
            Memory.created_at < cutoff,
            Memory.is_permanent == False,
            Memory.pinned == False,
            Memory.outcome == None,  # Don't prune memories with outcomes
            Memory.archived == False
        )

        result = await session.execute(query)
        to_prune = result.scalars().all()

        if dry_run:
            return {
                "dry_run": True,
                "would_prune": len(to_prune),
                "categories": categories,
                "older_than_days": older_than_days,
                "samples": [
                    {"id": m.id, "content": m.content[:50], "created_at": m.created_at.isoformat()}
                    for m in to_prune[:5]
                ]
            }

        # Actually delete
        for memory in to_prune:
            await session.delete(memory)

        return {
            "pruned": len(to_prune),
            "categories": categories,
            "older_than_days": older_than_days,
            "message": f"Pruned {len(to_prune)} old memories"
        }


@mcp.tool()
async def archive_memory(
    memory_id: int,
    archived: bool = True,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Archive or unarchive a memory.

    Archived memories are hidden from recall but preserved for history.

    Args:
        memory_id: Memory to archive/unarchive
        archived: True to archive, False to restore
        project_path: Project root path
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    async with ctx.db_manager.get_session() as session:
        result = await session.execute(
            select(Memory).where(Memory.id == memory_id)
        )
        memory = result.scalar_one_or_none()

        if not memory:
            return {"error": f"Memory {memory_id} not found"}

        memory.archived = archived

        return {
            "id": memory_id,
            "archived": archived,
            "content": memory.content[:100],
            "message": f"Memory {'archived' if archived else 'restored'}"
        }


@mcp.tool()
async def health(
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get server health and version information.

    Returns version, statistics, and configuration info.
    Useful for debugging and monitoring.

    Args:
        project_path: Project root path

    Returns:
        Health status with version and statistics
    """
    import time

    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)
    stats = await ctx.memory_manager.get_statistics()

    # Get rule count
    rules = await ctx.rules_engine.list_rules(enabled_only=False, limit=1000)

    return {
        "status": "healthy",
        "version": __version__,
        "project_path": ctx.project_path,
        "storage_path": ctx.storage_path,
        "memories_count": stats.get("total_memories", 0),
        "rules_count": len(rules),
        "by_category": stats.get("by_category", {}),
        "contexts_cached": len(_project_contexts),
        "vectors_enabled": vectors.is_available(),
        "timestamp": time.time()
    }


# ============================================================================
# Cleanup
# ============================================================================
async def _cleanup_all_contexts():
    """Close all project contexts."""
    for ctx in _project_contexts.values():
        try:
            await ctx.db_manager.close()
        except Exception:
            pass


def cleanup():
    """Cleanup on exit."""
    import asyncio
    try:
        # Try to get the running loop if one exists
        try:
            loop = asyncio.get_running_loop()
            # If there's a running loop, schedule cleanup
            loop.create_task(_cleanup_all_contexts())
        except RuntimeError:
            # No running loop - try to create one for cleanup
            # Only close contexts that were actually initialized
            contexts_to_close = [
                ctx for ctx in _project_contexts.values()
                if ctx.db_manager._engine is not None
            ]
            if contexts_to_close:
                asyncio.run(_cleanup_all_contexts())
    except Exception:
        # Cleanup is best-effort, don't crash on exit
        pass


atexit.register(cleanup)


# ============================================================================
# Entry point
# ============================================================================
def main():
    """Run the MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Daem0nMCP Server")
    parser.add_argument(
        "--transport", "-t",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport type: stdio (default) or sse (HTTP server)"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8765,
        help="Port for SSE transport (default: 8765)"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for SSE transport (default: 127.0.0.1)"
    )
    args = parser.parse_args()

    logger.info("Starting Daem0nMCP server...")
    logger.info(f"Storage: {storage_path}")
    logger.info(f"Transport: {args.transport}")

    # NOTE: Database initialization is now lazy and happens on first tool call.
    # This ensures the async engine is created within the correct event loop
    # context (the one that FastMCP creates and manages).

    # Run MCP server - this creates and manages its own event loop
    try:
        if args.transport == "sse":
            # Configure SSE settings
            mcp.settings.host = args.host
            mcp.settings.port = args.port
            logger.info(f"SSE server at http://{args.host}:{args.port}/sse")
            mcp.run(transport="sse")
        else:
            mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    main()
