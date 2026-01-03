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
12. Memory maintenance (pin, archive, prune, cleanup)
13. Code understanding via tree-sitter parsing

32 Tools:
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
- cleanup_memories: Deduplicate and merge duplicate memories
- health: Get server health, version, and statistics
- index_project: Index code structure for understanding
- find_code: Semantic search across code entities
- analyze_impact: Analyze what changing an entity would affect
"""

import sys
import os
import re
import logging
import atexit
import subprocess
import asyncio
import base64
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Set, Tuple
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
    from .logging_config import StructuredFormatter, with_request_id, request_id_var, set_release_callback
except ImportError:
    # For fastmcp run which executes server.py directly
    from daem0nmcp.config import settings
    from daem0nmcp.database import DatabaseManager
    from daem0nmcp.memory import MemoryManager
    from daem0nmcp.rules import RulesEngine
    from daem0nmcp.models import Memory, Rule
    from daem0nmcp import __version__
    from daem0nmcp import vectors
    from daem0nmcp.logging_config import StructuredFormatter, with_request_id, request_id_var, set_release_callback
from sqlalchemy import select, delete, or_
from dataclasses import dataclass, field

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configure structured logging (optional - only if env var set)
if os.getenv('DAEM0NMCP_STRUCTURED_LOGS'):
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    daem0n_logger = logging.getLogger('daem0nmcp')
    daem0n_logger.addHandler(handler)
    daem0n_logger.setLevel(logging.INFO)

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
    active_requests: int = 0  # Prevent eviction while in use
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


# Cache of project contexts by normalized path
_project_contexts: Dict[str, ProjectContext] = {}
_context_locks: Dict[str, asyncio.Lock] = {}
_contexts_lock = asyncio.Lock()  # Lock for modifying the dicts themselves
_task_contexts: Dict[asyncio.Task, Dict[str, int]] = {}
_task_contexts_lock = asyncio.Lock()
_last_eviction: float = 0.0
_EVICTION_INTERVAL_SECONDS: float = 60.0

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


def _resolve_within_project(project_root: str, target_path: Optional[str]) -> Tuple[Optional[Path], Optional[str]]:
    """
    Resolve a path and ensure it stays within the project root.

    Args:
        project_root: The project root directory
        target_path: Optional path relative to project root

    Returns:
        Tuple of (resolved_path, error_message). On success, error_message is None.
        On failure, resolved_path is None and error_message describes the issue.
    """
    try:
        root = Path(project_root).resolve()
        candidate = root if not target_path else (root / target_path)
        resolved = candidate.resolve()
    except OSError as e:
        # Handle invalid paths (too long, invalid characters, permission issues, etc.)
        logger.warning(f"Path resolution failed for '{project_root}' / '{target_path}': {e}")
        return None, f"Invalid path: {e}"

    try:
        resolved.relative_to(root)
    except ValueError:
        return None, "Path must be within the project root"

    return resolved, None


async def _release_task_contexts(task: asyncio.Task) -> None:
    """Release context usage counts for a completed task."""
    async with _task_contexts_lock:
        counts = _task_contexts.pop(task, None)

    if not counts:
        return

    for path, count in counts.items():
        ctx = _project_contexts.get(path)
        if ctx:
            async with ctx.lock:
                ctx.active_requests = max(0, ctx.active_requests - count)


def _schedule_task_release(task: asyncio.Task) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(_release_task_contexts(task))


async def _track_task_context(ctx: ProjectContext) -> None:
    """Track which task is using a context to avoid eviction while in-flight."""
    if not request_id_var.get():
        return

    task = asyncio.current_task()
    if task is None:
        return

    async with _task_contexts_lock:
        counts = _task_contexts.setdefault(task, {})
        counts[ctx.project_path] = counts.get(ctx.project_path, 0) + 1

        if not getattr(task, "_daem0n_ctx_tracked", False):
            setattr(task, "_daem0n_ctx_tracked", True)
            task.add_done_callback(_schedule_task_release)

    async with ctx.lock:
        ctx.active_requests += 1


async def _release_current_task_contexts() -> None:
    """Release context usage for the current task (per tool call)."""
    task = asyncio.current_task()
    if task:
        await _release_task_contexts(task)


def _maybe_schedule_eviction(now: float) -> None:
    """Avoid running eviction too frequently."""
    global _last_eviction
    if now - _last_eviction < _EVICTION_INTERVAL_SECONDS:
        return
    _last_eviction = now
    asyncio.create_task(evict_stale_contexts())


set_release_callback(_release_current_task_contexts)


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
            now = time.time()
            ctx.last_accessed = now
            # Opportunistic eviction: trigger background cleanup if over limit
            if len(_project_contexts) > MAX_PROJECT_CONTEXTS:
                asyncio.create_task(evict_stale_contexts())
            else:
                _maybe_schedule_eviction(now)
            await _track_task_context(ctx)
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
                now = time.time()
                ctx.last_accessed = now
                _maybe_schedule_eviction(now)
                await _track_task_context(ctx)
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

        _maybe_schedule_eviction(time.time())
        await _track_task_context(ctx)
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

    Note: Uses a two-phase approach to avoid nested lock acquisition:
    1. Collect candidates under contexts_lock (no nested locks)
    2. Process each candidate individually with proper lock ordering
    """
    import time

    evicted = 0
    now = time.time()

    # Phase 1: Collect TTL candidates (no nested locks)
    ttl_candidates = []
    async with _contexts_lock:
        for path, ctx in _project_contexts.items():
            if (now - ctx.last_accessed) <= CONTEXT_TTL_SECONDS:
                continue
            # Skip if path-level lock is held
            if _context_locks.get(path) and _context_locks[path].locked():
                continue
            ttl_candidates.append(path)

    # Phase 2: Process TTL candidates individually
    for path in ttl_candidates:
        async with _contexts_lock:
            ctx = _project_contexts.get(path)
            if ctx is None:
                continue  # Already evicted by another task

            # Now safely check active_requests under context's own lock
            async with ctx.lock:
                if ctx.active_requests > 0:
                    continue  # Became active, skip

                # Safe to evict
                _project_contexts.pop(path, None)

            try:
                await ctx.db_manager.close()
            except Exception as e:
                logger.warning(f"Error closing context for {path}: {e}")
            evicted += 1
            logger.info(f"Evicted TTL-expired context: {path}")

    # Phase 3: LRU eviction if still over limit
    while True:
        async with _contexts_lock:
            if len(_project_contexts) <= MAX_PROJECT_CONTEXTS:
                break

            # Find candidates (paths with unlocked context locks)
            candidates = []
            for path, ctx in _project_contexts.items():
                if _context_locks.get(path) and _context_locks[path].locked():
                    continue
                candidates.append((path, ctx.last_accessed))

            if not candidates:
                break

            # Find oldest
            oldest_path = min(candidates, key=lambda x: x[1])[0]
            ctx = _project_contexts.get(oldest_path)

            if ctx is None:
                continue

            # Check if still idle under context lock
            async with ctx.lock:
                if ctx.active_requests > 0:
                    continue

                _project_contexts.pop(oldest_path, None)

            try:
                await ctx.db_manager.close()
            except Exception as e:
                logger.warning(f"Error closing context for {oldest_path}: {e}")
            evicted += 1
            logger.info(f"Evicted LRU context: {oldest_path}")

    # Phase 4: Clean up orphaned locks
    async with _contexts_lock:
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
@with_request_id
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
        file_path=file_path,
        project_path=ctx.project_path
    )


# ============================================================================
# Tool 1b: REMEMBER_BATCH - Store multiple memories efficiently
# ============================================================================
@mcp.tool()
@with_request_id
async def remember_batch(
    memories: List[Dict[str, Any]],
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Store multiple memories in a single transaction.

    More efficient than calling remember() multiple times, especially for
    bootstrapping or bulk imports. All memories are stored atomically.

    Args:
        memories: List of memory dicts, each with:
            - category: One of 'decision', 'pattern', 'warning', 'learning' (required)
            - content: The actual content to remember (required)
            - rationale: Why this is important (optional)
            - tags: List of tags for retrieval (optional)
            - file_path: Associated file path (optional)
        project_path: Project root path (for multi-project HTTP server support)

    Returns:
        Summary with created_count, error_count, ids list, and any errors

    Examples:
        remember_batch([
            {"category": "pattern", "content": "Use TypeScript for all new code"},
            {"category": "warning", "content": "Don't use var, use const/let"},
            {"category": "decision", "content": "Chose React over Vue", "rationale": "Team expertise"}
        ])
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    if not memories:
        return {
            "created_count": 0,
            "error_count": 0,
            "ids": [],
            "errors": [],
            "message": "No memories provided"
        }

    ctx = await get_project_context(project_path)
    result = await ctx.memory_manager.remember_batch(
        memories=memories,
        project_path=ctx.project_path
    )

    result["message"] = (
        f"Stored {result['created_count']} memories"
        + (f" with {result['error_count']} error(s)" if result['error_count'] else "")
    )

    return result


# ============================================================================
# Tool 2: RECALL - Semantic memory retrieval with decay
# ============================================================================
@mcp.tool()
@with_request_id
async def recall(
    topic: str,
    categories: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    file_path: Optional[str] = None,
    offset: int = 0,
    limit: int = 10,
    since: Optional[str] = None,
    until: Optional[str] = None,
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
        offset: Number of results to skip for pagination (default: 0)
        limit: Max memories per category (default: 10)
        since: Only include memories created after this date (ISO format)
        until: Only include memories created before this date (ISO format)
        project_path: Project root path (for multi-project HTTP server support)

    Returns:
        Categorized memories with relevance scores, pagination metadata, and failure warnings

    Examples:
        recall("authentication")  # Get all memories about auth
        recall("API endpoints", categories=["pattern", "warning"])
        recall("database")  # Before making DB changes
        recall("Redis", tags=["cache"])  # Only memories tagged with cache
        recall("sync calls", file_path="api/handlers.py")  # Only for specific file
        recall("API", offset=10, limit=10)  # Get second page
        recall("auth", since="2025-01-01T00:00:00Z")  # Only recent memories
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    # Parse date strings if provided
    since_dt = None
    until_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
        except ValueError:
            return {"error": f"Invalid 'since' date format: {since}. Use ISO format (e.g., '2025-01-01T00:00:00Z')"}

    if until:
        try:
            until_dt = datetime.fromisoformat(until.replace('Z', '+00:00'))
        except ValueError:
            return {"error": f"Invalid 'until' date format: {until}. Use ISO format (e.g., '2025-12-31T23:59:59Z')"}

    ctx = await get_project_context(project_path)
    return await ctx.memory_manager.recall(
        topic=topic,
        categories=categories,
        tags=tags,
        file_path=file_path,
        offset=offset,
        limit=limit,
        since=since_dt,
        until=until_dt,
        project_path=ctx.project_path
    )


# ============================================================================
# Tool 3: ADD_RULE - Create a decision tree node
# ============================================================================
@mcp.tool()
@with_request_id
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
@with_request_id
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
@with_request_id
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


# Directories to exclude when scanning project structure
BOOTSTRAP_EXCLUDED_DIRS = {
    'node_modules', '.git', '__pycache__', '.venv', 'venv',
    'dist', 'build', '.next', 'target', '.idea', '.vscode',
    '.eggs', 'eggs', '.tox', '.nox', '.mypy_cache', '.pytest_cache',
    '.ruff_cache', 'htmlcov', '.coverage', 'site-packages'
}


def _extract_project_identity(project_path: str) -> Optional[str]:
    """
    Extract project identity from manifest files.

    Tries manifests in priority order:
    1. package.json (Node.js)
    2. pyproject.toml (Python)
    3. Cargo.toml (Rust)
    4. go.mod (Go)

    Returns:
        Formatted string with project name, description, and key dependencies,
        or None if no manifest found.
    """
    root = Path(project_path)

    # Try package.json first
    package_json = root / "package.json"
    if package_json.exists():
        try:
            data = json.loads(package_json.read_text(encoding='utf-8', errors='ignore'))
            parts = []
            if data.get('name'):
                parts.append(f"Project: {data['name']}")
            if data.get('description'):
                parts.append(f"Description: {data['description']}")
            if data.get('scripts'):
                scripts = ', '.join(list(data['scripts'].keys())[:5])
                parts.append(f"Scripts: {scripts}")
            deps = list(data.get('dependencies', {}).keys())[:10]
            dev_deps = list(data.get('devDependencies', {}).keys())[:5]
            if deps:
                parts.append(f"Dependencies: {', '.join(deps)}")
            if dev_deps:
                parts.append(f"Dev dependencies: {', '.join(dev_deps)}")
            if parts:
                return "Tech stack (from package.json):\n" + "\n".join(parts)
        except Exception as e:
            logger.debug(f"Failed to parse package.json: {e}")

    # Try pyproject.toml
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding='utf-8', errors='ignore')
            # Simple parsing without external deps
            parts = []
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('name = '):
                    project_name = line.split('=', 1)[1].strip().strip('"')
                    parts.append(f"Project: {project_name}")
                elif line.startswith('description = '):
                    description = line.split('=', 1)[1].strip().strip('"')
                    parts.append(f"Description: {description}")
            # Extract dependencies list
            if 'dependencies = [' in content:
                start = content.find('dependencies = [')
                end = content.find(']', start)
                if end > start:
                    deps_str = content[start:end+1]
                    deps = [d.strip().strip('"').strip("'").split('[')[0].split('>')[0].split('<')[0].split('=')[0].strip()
                            for d in deps_str.split('[')[1].split(']')[0].split(',')
                            if d.strip()]
                    deps = [d for d in deps if d]  # Remove empty strings
                    if deps:
                        parts.append(f"Dependencies: {', '.join(deps[:10])}")
            if parts:
                return "Tech stack (from pyproject.toml):\n" + "\n".join(parts)
        except Exception as e:
            logger.debug(f"Failed to parse pyproject.toml: {e}")

    # Try Cargo.toml
    cargo = root / "Cargo.toml"
    if cargo.exists():
        try:
            content = cargo.read_text(encoding='utf-8', errors='ignore')
            parts = []
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('name = '):
                    project_name = line.split('=', 1)[1].strip().strip('"')
                    parts.append(f"Project: {project_name}")
                elif line.startswith('description = '):
                    description = line.split('=', 1)[1].strip().strip('"')
                    parts.append(f"Description: {description}")
            if parts:
                return "Tech stack (from Cargo.toml):\n" + "\n".join(parts)
        except Exception as e:
            logger.debug(f"Failed to parse Cargo.toml: {e}")

    # Try go.mod
    gomod = root / "go.mod"
    if gomod.exists():
        try:
            content = gomod.read_text(encoding='utf-8', errors='ignore')
            parts = []
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('module '):
                    parts.append(f"Module: {line.split(' ', 1)[1]}")
                elif line.startswith('go '):
                    parts.append(f"Go version: {line.split(' ', 1)[1]}")
            if parts:
                return "Tech stack (from go.mod):\n" + "\n".join(parts)
        except Exception as e:
            logger.debug(f"Failed to parse go.mod: {e}")

    return None


def _extract_architecture(project_path: str) -> Optional[str]:
    """
    Extract architecture overview from README and directory structure.

    Combines:
    1. README.md content (first 2000 chars)
    2. Top-level directory structure (excluding noise)

    Returns:
        Formatted string with architecture overview, or None if empty project.
    """
    root = Path(project_path)
    parts = []

    # Extract README content
    for readme_name in ["README.md", "README.rst", "README.txt", "README"]:
        readme = root / readme_name
        if readme.exists():
            try:
                content = readme.read_text(encoding='utf-8', errors='ignore')[:2000]
                if content.strip():
                    parts.append(f"README:\n{content}")
                break
            except Exception as e:
                logger.debug(f"Failed to read {readme_name}: {e}")

    # Extract directory structure (top 2 levels)
    dirs = []
    files = []
    try:
        for item in sorted(root.iterdir()):
            name = item.name
            if name.startswith('.') and name not in ['.github']:
                continue
            if name in BOOTSTRAP_EXCLUDED_DIRS:
                continue
            if item.is_dir():
                # Get immediate children count
                try:
                    child_count = sum(1 for _ in item.iterdir())
                    dirs.append(f"  {name}/ ({child_count} items)")
                except PermissionError:
                    dirs.append(f"  {name}/")
            elif item.is_file() and name in [
                'main.py', 'app.py', 'index.ts', 'index.js', 'main.rs',
                'main.go', 'Makefile', 'Dockerfile', 'docker-compose.yml'
            ]:
                files.append(f"  {name}")
    except Exception as e:
        logger.debug(f"Failed to scan directory: {e}")

    if dirs or files:
        structure = "Directory structure:\n"
        structure += "\n".join(dirs + files)
        parts.append(structure)

    if not parts:
        return None

    return "Architecture overview:\n\n" + "\n\n".join(parts)


def _extract_conventions(project_path: str) -> Optional[str]:
    """
    Extract coding conventions from config files and docs.

    Checks for:
    1. CONTRIBUTING.md / CONTRIBUTING
    2. Linter configs (.eslintrc, ruff.toml, .pylintrc, etc.)
    3. Formatter configs (.prettierrc, pyproject.toml [tool.black])

    Returns:
        Formatted string with coding conventions, or None if nothing found.
    """
    root = Path(project_path)
    parts = []

    # Check CONTRIBUTING.md
    for contrib_name in ["CONTRIBUTING.md", "CONTRIBUTING.rst", "CONTRIBUTING"]:
        contrib = root / contrib_name
        if contrib.exists():
            try:
                content = contrib.read_text(encoding='utf-8', errors='ignore')[:1500]
                if content.strip():
                    parts.append(f"Contributing guidelines:\n{content}")
                break
            except Exception as e:
                logger.debug(f"Failed to read {contrib_name}: {e}")

    # Detect linter/formatter configs
    config_files = [
        (".eslintrc", "ESLint"),
        (".eslintrc.js", "ESLint"),
        (".eslintrc.json", "ESLint"),
        (".prettierrc", "Prettier"),
        (".prettierrc.json", "Prettier"),
        ("prettier.config.js", "Prettier"),
        ("ruff.toml", "Ruff"),
        (".pylintrc", "Pylint"),
        ("pylintrc", "Pylint"),
        ("mypy.ini", "Mypy"),
        (".flake8", "Flake8"),
        ("setup.cfg", "Setup.cfg"),
        ("tslint.json", "TSLint"),
        ("biome.json", "Biome"),
        (".editorconfig", "EditorConfig"),
    ]

    found_configs = []
    for filename, tool_name in config_files:
        if (root / filename).exists():
            found_configs.append(tool_name)

    # Check pyproject.toml for tool configs
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding='utf-8', errors='ignore')
            if '[tool.black]' in content:
                found_configs.append("Black")
            if '[tool.ruff]' in content:
                found_configs.append("Ruff")
            if '[tool.mypy]' in content:
                found_configs.append("Mypy")
            if '[tool.pytest]' in content or '[tool.pytest.ini_options]' in content:
                found_configs.append("Pytest")
        except Exception:
            pass

    if found_configs:
        # Deduplicate
        unique_configs = list(dict.fromkeys(found_configs))
        parts.append(f"Code tools configured: {', '.join(unique_configs)}")

    if not parts:
        return None

    return "Coding conventions:\n\n" + "\n\n".join(parts)


def _extract_entry_points(project_path: str) -> Optional[str]:
    """
    Find common entry point files in the project.

    Looks for files like:
    - main.py, app.py, cli.py, __main__.py (Python)
    - index.js, index.ts, main.js, main.ts (Node.js)
    - main.rs (Rust)
    - main.go, cmd/ (Go)
    - server.py, server.js, api.py (Servers)

    Returns:
        Formatted list of entry points found, or None if none found.
    """
    root = Path(project_path)
    entry_point_patterns = [
        "main.py", "app.py", "cli.py", "__main__.py", "server.py", "api.py",
        "wsgi.py", "asgi.py", "manage.py",
        "index.js", "index.ts", "index.tsx", "main.js", "main.ts",
        "server.js", "server.ts", "app.js", "app.ts",
        "main.rs", "lib.rs",
        "main.go",
    ]

    found = []

    def scan_dir(dir_path: Path, depth: int = 0):
        if depth > 2:  # Only scan 2 levels deep
            return
        try:
            for item in dir_path.iterdir():
                if item.name in BOOTSTRAP_EXCLUDED_DIRS:
                    continue
                if item.is_file() and item.name in entry_point_patterns:
                    rel_path = item.relative_to(root)
                    found.append(str(rel_path))
                elif item.is_dir() and not item.name.startswith('.'):
                    scan_dir(item, depth + 1)
        except PermissionError:
            pass

    scan_dir(root)

    # Also check for cmd/ directory (Go convention)
    cmd_dir = root / "cmd"
    if cmd_dir.exists() and cmd_dir.is_dir():
        try:
            for item in cmd_dir.iterdir():
                if item.is_dir():
                    found.append(f"cmd/{item.name}/")
        except PermissionError:
            pass

    if not found:
        return None

    return "Entry points identified:\n" + "\n".join(f"  - {f}" for f in sorted(found)[:15])


def _scan_todos_for_bootstrap(project_path: str, limit: int = 20) -> Optional[str]:
    """
    Scan for TODO/FIXME/HACK comments during bootstrap.

    Uses the existing _scan_for_todos helper but formats results
    for bootstrap memory storage.

    Args:
        project_path: Directory to scan
        limit: Maximum items to include (default: 20)

    Returns:
        Formatted string with TODO summary, or None if none found.
    """
    todos = _scan_for_todos(project_path, max_files=200)

    if not todos:
        return None

    # Limit and format
    limited = todos[:limit]

    # Group by type
    by_type: Dict[str, int] = {}
    for todo in todos:
        todo_type = todo.get('type', 'TODO')
        by_type[todo_type] = by_type.get(todo_type, 0) + 1

    summary_parts = []

    # Add counts summary
    counts = ", ".join(f"{count} {t}" for t, count in sorted(by_type.items()))
    summary_parts.append(f"Found: {counts}")

    # Add individual items
    for todo in limited:
        file_path = todo.get('file', 'unknown')
        line = todo.get('line', 0)
        todo_type = todo.get('type', 'TODO')
        content = todo.get('content', '')[:80]
        summary_parts.append(f"  [{todo_type}] {file_path}:{line} - {content}")

    if len(todos) > limit:
        summary_parts.append(f"  ... and {len(todos) - limit} more")

    return "Known issues from code comments:\n" + "\n".join(summary_parts)


def _extract_project_instructions(project_path: str) -> Optional[str]:
    """
    Extract project instructions from CLAUDE.md and AGENTS.md.

    Returns:
        Combined instructions content, or None if no files found.
    """
    root = Path(project_path)
    parts = []

    # Check CLAUDE.md
    claude_md = root / "CLAUDE.md"
    if claude_md.exists():
        try:
            content = claude_md.read_text(encoding='utf-8', errors='ignore')[:3000]
            if content.strip():
                parts.append(f"From CLAUDE.md:\n{content}")
        except Exception as e:
            logger.debug(f"Failed to read CLAUDE.md: {e}")

    # Check AGENTS.md
    agents_md = root / "AGENTS.md"
    if agents_md.exists():
        try:
            content = agents_md.read_text(encoding='utf-8', errors='ignore')[:2000]
            if content.strip():
                parts.append(f"From AGENTS.md:\n{content}")
        except Exception as e:
            logger.debug(f"Failed to read AGENTS.md: {e}")

    if not parts:
        return None

    return "Project instructions:\n\n" + "\n\n".join(parts)


# ============================================================================
# Helper: Git awareness
# ============================================================================
def _get_git_history_summary(project_path: str, limit: int = 30) -> Optional[str]:
    """Get a summary of git history for bootstrapping context.

    Args:
        project_path: Directory to run git commands in
        limit: Maximum number of commits to include

    Returns:
        Formatted string summary of git history, or None if not a git repo
    """
    try:
        # Check if we're in a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=project_path
        )
        if result.returncode != 0:
            return None

        # Get commit history with more detail
        result = subprocess.run(
            ["git", "log", f"-{limit}", "--format=%h|%s|%an|%ar"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=project_path
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        lines = result.stdout.strip().split("\n")
        summary_parts = []
        for line in lines:
            parts = line.split("|", 3)
            if len(parts) >= 2:
                commit_hash, message = parts[0], parts[1]
                summary_parts.append(f"- {commit_hash}: {message}")

        if not summary_parts:
            return None

        return "\n".join(summary_parts)

    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return None


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
# Helper: Bootstrap project context on first run
# ============================================================================
async def _bootstrap_project_context(ctx: ProjectContext) -> Dict[str, Any]:
    """
    Bootstrap initial context on first run.

    Called automatically when get_briefing() detects no memories exist.
    Ingests multiple sources to provide comprehensive project awareness:
    1. Project identity (tech stack from manifests)
    2. Architecture overview (README + directory structure)
    3. Coding conventions (from config files)
    4. Project instructions (CLAUDE.md, AGENTS.md)
    5. Git history baseline
    6. Known issues (TODO/FIXME scan)
    7. Entry points (main files)

    Args:
        ctx: The project context to bootstrap

    Returns:
        Dictionary with bootstrap results including sources status
    """
    results = {
        "bootstrapped": True,
        "memories_created": 0,
        "sources": {}
    }

    # Define all extractors with their memory configs
    extractors = [
        (
            "project_identity",
            lambda: _extract_project_identity(ctx.project_path),
            "pattern",
            "Tech stack and dependencies from project manifest",
            ["bootstrap", "tech-stack", "identity"]
        ),
        (
            "architecture",
            lambda: _extract_architecture(ctx.project_path),
            "pattern",
            "Project structure and README overview",
            ["bootstrap", "architecture", "structure"]
        ),
        (
            "conventions",
            lambda: _extract_conventions(ctx.project_path),
            "pattern",
            "Coding conventions and tool configurations",
            ["bootstrap", "conventions", "style"]
        ),
        (
            "project_instructions",
            lambda: _extract_project_instructions(ctx.project_path),
            "pattern",
            "Project-specific AI instructions from CLAUDE.md/AGENTS.md",
            ["bootstrap", "project-config", "instructions"]
        ),
        (
            "git_evolution",
            lambda: _get_git_history_summary(ctx.project_path, limit=30),
            "learning",
            "Recent git history showing project evolution",
            ["bootstrap", "git-history", "evolution"]
        ),
        (
            "known_issues",
            lambda: _scan_todos_for_bootstrap(ctx.project_path, limit=20),
            "warning",
            "Known issues from TODO/FIXME/HACK comments in code",
            ["bootstrap", "tech-debt", "issues"]
        ),
        (
            "entry_points",
            lambda: _extract_entry_points(ctx.project_path),
            "learning",
            "Main entry point files identified in the project",
            ["bootstrap", "entry-points", "structure"]
        ),
    ]

    # Run each extractor and create memories
    for name, extractor, category, rationale, tags in extractors:
        try:
            content = extractor()
            if content:
                await ctx.memory_manager.remember(
                    category=category,
                    content=content,
                    rationale=f"Auto-ingested on first run: {rationale}",
                    tags=tags,
                    project_path=ctx.project_path
                )
                results["sources"][name] = "ingested"
                results["memories_created"] += 1
                logger.info(f"Bootstrapped {name} for {ctx.project_path}")
            else:
                results["sources"][name] = "skipped"
        except Exception as e:
            logger.warning(f"Failed to extract {name}: {e}")
            results["sources"][name] = f"error: {e}"

    return results


# ============================================================================
# Helper functions for get_briefing (extracted for maintainability)
# ============================================================================

async def _fetch_recent_context(ctx: ProjectContext) -> Dict[str, Any]:
    """
    Fetch recent decisions, warnings, failed approaches, and top rules.

    Args:
        ctx: Project context with database access

    Returns:
        Dict with recent_decisions, active_warnings, failed_approaches,
        top_rules, and last_memory_date
    """
    last_memory_date = None

    async with ctx.db_manager.get_session() as session:
        # Get most recent memory timestamp
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

    return {
        "last_memory_date": last_memory_date,
        "recent_decisions": recent_decisions,
        "active_warnings": active_warnings,
        "failed_approaches": failed_approaches,
        "top_rules": top_rules
    }


async def _prefetch_focus_areas(
    ctx: ProjectContext,
    focus_areas: List[str]
) -> Dict[str, Dict[str, Any]]:
    """
    Pre-fetch memories for specified focus areas.

    Args:
        ctx: Project context with memory manager
        focus_areas: List of topics to fetch (max 3 processed)

    Returns:
        Dict mapping area name to summary info
    """
    focus_memories = {}

    for area in focus_areas[:3]:  # Limit to 3 areas
        memories = await ctx.memory_manager.recall(
            area, limit=5, project_path=ctx.project_path
        )
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

    return focus_memories


def _build_briefing_message(
    stats: Dict[str, Any],
    bootstrap_result: Optional[Dict[str, Any]],
    failed_approaches: List[Dict[str, Any]],
    active_warnings: List[Dict[str, Any]],
    git_changes: Optional[Dict[str, Any]]
) -> str:
    """
    Build the actionable message for the briefing.

    Args:
        stats: Memory statistics
        bootstrap_result: Bootstrap result if first run
        failed_approaches: List of failed approaches
        active_warnings: List of active warnings
        git_changes: Git changes info

    Returns:
        Human-readable briefing message
    """
    message_parts = [f"Daem0nMCP ready. {stats['total_memories']} memories stored."]

    # Add bootstrap notification if this was first run
    if bootstrap_result:
        sources = bootstrap_result.get("sources", {})
        ingested = [k for k, v in sources.items() if v == "ingested"]

        if ingested:
            source_summary = ", ".join(ingested)
            message_parts.append(f"[BOOTSTRAP] First run - ingested: {source_summary}.")
        else:
            message_parts.append("[BOOTSTRAP] First run - no sources found.")

    if failed_approaches:
        message_parts.append(f"[WARNING] {len(failed_approaches)} failed approaches to avoid!")

    if active_warnings:
        message_parts.append(f"{len(active_warnings)} active warnings.")

    if git_changes and git_changes.get("uncommitted_changes"):
        message_parts.append(f"{len(git_changes['uncommitted_changes'])} uncommitted file(s).")

    if stats.get("learning_insights", {}).get("suggestion"):
        message_parts.append(stats["learning_insights"]["suggestion"])

    return " ".join(message_parts)


# ============================================================================
# Tool 6: GET_BRIEFING - Smart session start summary
# ============================================================================
@mcp.tool()
@with_request_id
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

    # AUTO-BOOTSTRAP: First run detection
    bootstrap_result = None
    if stats.get('total_memories', 0) == 0:
        bootstrap_result = await _bootstrap_project_context(ctx)
        stats = await ctx.memory_manager.get_statistics()

    # Fetch recent context (decisions, warnings, failed approaches, rules)
    recent_context = await _fetch_recent_context(ctx)

    # Get git changes since last memory
    git_changes = _get_git_changes(
        recent_context["last_memory_date"],
        project_path=ctx.project_path
    )

    # Pre-fetch memories for focus areas if specified
    focus_memories = None
    if focus_areas:
        focus_memories = await _prefetch_focus_areas(ctx, focus_areas)

    # Build actionable message
    message = _build_briefing_message(
        stats=stats,
        bootstrap_result=bootstrap_result,
        failed_approaches=recent_context["failed_approaches"],
        active_warnings=recent_context["active_warnings"],
        git_changes=git_changes
    )

    return {
        "status": "ready",
        "statistics": stats,
        "recent_decisions": recent_context["recent_decisions"],
        "active_warnings": recent_context["active_warnings"],
        "failed_approaches": recent_context["failed_approaches"],
        "top_rules": recent_context["top_rules"],
        "git_changes": git_changes,
        "focus_areas": focus_memories,
        "bootstrap": bootstrap_result,
        "message": message
    }


# ============================================================================
# Tool 7: SEARCH - Full text search across memories
# ============================================================================
@mcp.tool()
@with_request_id
async def search_memories(
    query: str,
    limit: int = 20,
    offset: int = 0,
    include_meta: bool = False,
    highlight: bool = False,
    highlight_start: str = "<b>",
    highlight_end: str = "</b>",
    project_path: Optional[str] = None
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Search across all memories with semantic similarity.

    Use this when you need to find specific memories by content.
    Uses TF-IDF matching for better results than exact text search.
    Optionally includes highlighted excerpts showing matched terms.

    Args:
        query: Search text
        limit: Maximum results (default: 20)
        offset: Number of results to skip (default: 0)
        include_meta: Return pagination metadata with results
        highlight: If True, include highlighted excerpts in results
        highlight_start: Opening tag for matched terms (default: <b>)
        highlight_end: Closing tag for matched terms (default: </b>)
        project_path: Project root path (for multi-project HTTP server support)

    Returns:
        Matching memories ranked by relevance.
        If highlight=True, each result includes an 'excerpt' field with
        highlighted matches.
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    if offset < 0:
        return {"error": "offset must be non-negative"}

    ctx = await get_project_context(project_path)
    raw_limit = offset + limit + 1

    if highlight:
        # Use FTS search with highlighting
        results = await ctx.memory_manager.fts_search(
            query=query,
            limit=raw_limit,
            highlight=True,
            highlight_start=highlight_start,
            highlight_end=highlight_end
        )
    else:
        results = await ctx.memory_manager.search(query=query, limit=raw_limit)

    has_more = len(results) > offset + limit
    paginated = results[offset:offset + limit]

    if include_meta:
        return {
            "query": query,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "highlight": highlight,
            "results": paginated
        }

    return paginated


# ============================================================================
# Tool 8: LIST_RULES - See all configured rules
# ============================================================================
@mcp.tool()
@with_request_id
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
@with_request_id
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
@with_request_id
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
@with_request_id
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

    # Get relevant memories (with defensive None check)
    memories = await ctx.memory_manager.recall(description, limit=5, project_path=ctx.project_path)
    if memories is None:
        memories = {}

    # Check rules (with defensive None check)
    rules = await ctx.rules_engine.check_rules(description)
    if rules is None:
        rules = {}

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
@with_request_id
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
    return await ctx.memory_manager.recall_for_file(file_path=file_path, limit=limit, project_path=ctx.project_path)


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


def _scan_for_todos(
    root_path: str,
    max_files: int = 500,
    skip_dirs: Optional[List[str]] = None,
    skip_extensions: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Scan directory for TODO/FIXME/HACK comments with deduplication.

    Supports:
    - Single-line comments (# // --)
    - Multi-line block comments (/* */ ''' \"\"\")
    - Content hashing to avoid duplicates
    - Configurable skip lists

    Args:
        root_path: Directory to scan
        max_files: Maximum files to scan (default: 500)
        skip_dirs: Directories to skip (default: from settings)
        skip_extensions: File extensions to skip (default: from settings)

    Returns:
        List of TODO items with file, line, type, content, and hash
    """
    import hashlib

    # Use settings defaults if not provided
    if skip_dirs is None:
        skip_dirs = settings.todo_skip_dirs
    if skip_extensions is None:
        skip_extensions = settings.todo_skip_extensions

    todos = []
    seen_hashes = set()
    files_scanned = 0
    root = Path(root_path)

    if not root.exists():
        return []

    # Convert skip_dirs to set for faster lookup
    skip_dirs_set = set(skip_dirs)
    skip_exts_set = set(skip_extensions)

    for file_path in root.rglob('*'):
        # Skip directories
        if file_path.is_dir():
            continue

        # Check if any parent is a skip directory
        skip = False
        for part in file_path.parts:
            if part in skip_dirs_set or part.endswith('.egg-info'):
                skip = True
                break
        if skip:
            continue

        # Check extension
        if file_path.suffix.lower() in skip_exts_set:
            continue

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

                        # Deduplicate by content hash
                        content_hash = hashlib.md5(
                            f"{rel_path}:{text}".encode()
                        ).hexdigest()[:8]

                        if content_hash not in seen_hashes:
                            seen_hashes.add(content_hash)
                            todos.append({
                                'type': keyword.upper(),
                                'content': text[:200],  # Truncate long content
                                'file': rel_path,
                                'line': line_num,
                                'full_line': line.strip()[:300],
                                'hash': content_hash
                            })
        except (OSError, UnicodeDecodeError):
            continue

    return todos


# ============================================================================
# Tool 13: SCAN_TODOS - Find tech debt in codebase
# ============================================================================
@mcp.tool()
@with_request_id
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
    resolved_scan_path, error = _resolve_within_project(ctx.project_path, scan_path)
    if error or resolved_scan_path is None:
        return {"error": error or "Invalid scan path", "path": scan_path}
    found_todos = _scan_for_todos(
        str(resolved_scan_path),
        max_files=settings.todo_max_files
    )

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
                    file_path=todo['file'],
                    project_path=ctx.project_path
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
def _resolve_public_ips(hostname: str) -> Set[str]:
    """Resolve a hostname and ensure all IPs are public/global."""
    import ipaddress
    import socket

    try:
        addr_infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise ValueError("Host could not be resolved")

    if not addr_infos:
        raise ValueError("Host could not be resolved")

    ips: Set[str] = set()
    for _, _, _, _, sockaddr in addr_infos:
        ip_str = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError as exc:
            raise ValueError(f"Invalid IP address for host: {ip_str}") from exc
        if not ip_obj.is_global:
            raise ValueError(f"Non-public IP addresses are not allowed: {ip_obj}")
        ips.add(str(ip_obj))

    return ips


def _validate_url(url: str) -> Tuple[Optional[str], Optional[Set[str]]]:
    """
    Validate URL for ingestion.
    Returns (error_message, resolved_public_ips).

    Security checks:
    - Scheme validation (no file://, etc.)
    - SSRF protection: Blocks localhost and private IPs
    - Cloud metadata endpoint protection
    """
    from urllib.parse import urlparse
    import ipaddress

    try:
        parsed = urlparse(url)
    except Exception:
        return "Invalid URL format", None

    if parsed.scheme.lower() not in ALLOWED_URL_SCHEMES:
        return f"Invalid URL scheme '{parsed.scheme}'. Allowed: {ALLOWED_URL_SCHEMES}", None

    if not parsed.netloc:
        return "URL must have a host", None

    # Extract hostname from netloc (remove port)
    hostname = parsed.hostname
    if not hostname:
        return "URL must have a valid hostname", None

    # Block localhost
    if hostname.lower() in ['localhost', 'localhost.localdomain', '127.0.0.1', '::1']:
        return "Localhost URLs are not allowed", None

    # If hostname is an IP literal, validate directly
    try:
        ip_obj = ipaddress.ip_address(hostname)
        if not ip_obj.is_global:
            return f"Non-public IP addresses are not allowed: {ip_obj}", None
        return None, {str(ip_obj)}
    except ValueError:
        pass

    try:
        allowed_ips = _resolve_public_ips(hostname)
    except ValueError as exc:
        return str(exc), None

    return None, allowed_ips


async def _fetch_and_extract(url: str, allowed_ips: Optional[Set[str]] = None) -> Optional[str]:
    """Fetch URL and extract text content with size limits."""
    try:
        import httpx
        from bs4 import BeautifulSoup
    except ImportError:
        return None

    response = None
    try:
        limits = httpx.Limits(max_connections=1, max_keepalive_connections=0)
        async with httpx.AsyncClient(
            timeout=float(INGEST_TIMEOUT),
            follow_redirects=False,
            trust_env=False,
            limits=limits,
            headers={"Accept-Encoding": "identity"},
        ) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()

                # Check content length header first
                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        if int(content_length) > MAX_CONTENT_SIZE:
                            logger.warning(f"Content too large: {content_length} bytes")
                            return None
                    except ValueError:
                        pass

                size = 0
                chunks: List[bytes] = []
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_CONTENT_SIZE:
                        logger.warning(f"Content too large: {size} bytes")
                        return None
                    chunks.append(chunk)

                stream = response.extensions.get("network_stream")
                if allowed_ips and stream and hasattr(stream, "get_extra_info"):
                    peer = stream.get_extra_info("peername")
                    peer_ip = None
                    if isinstance(peer, (tuple, list)) and peer:
                        peer_ip = peer[0]
                    elif peer:
                        peer_ip = str(peer)
                    if peer_ip:
                        try:
                            import ipaddress
                            peer_ip = str(ipaddress.ip_address(peer_ip))
                        except ValueError:
                            peer_ip = None
                    if peer_ip and peer_ip not in allowed_ips:
                        logger.warning(f"Resolved IP mismatch for {url}: {peer_ip}")
                        return None

        encoding = response.encoding if response else "utf-8"
        text = b"".join(chunks).decode(encoding or "utf-8", errors="replace")

        soup = BeautifulSoup(text, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        # Get text
        text = soup.get_text(separator="\n", strip=True)

        # Clean up whitespace
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None


def _chunk_markdown_content(content: str, chunk_size: int, max_chunks: int) -> List[str]:
    """
    Chunk content with markdown awareness.

    Splits at markdown headers first (##, ###, etc.) to keep related content together,
    then further splits oversized sections by size. This ensures that function
    descriptions, API endpoints, etc. aren't split across chunks.

    Args:
        content: The text content to chunk
        chunk_size: Maximum characters per chunk
        max_chunks: Maximum number of chunks to create

    Returns:
        List of content chunks
    """
    # First, split at markdown headers (# ## ### #### etc.)
    # Pattern matches newline followed by 1-6 # characters and a space
    header_pattern = re.compile(r'\n(?=#{1,6}\s)')
    sections = header_pattern.split(content)

    chunks = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # If section fits in chunk_size, add it directly
        if len(section) <= chunk_size:
            chunks.append(section)
        else:
            # Section is too large - split by paragraphs first
            paragraphs = re.split(r'\n\n+', section)
            current_chunk = []
            current_size = 0

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                para_len = len(para) + 2  # +2 for paragraph separator

                if current_size + para_len > chunk_size and current_chunk:
                    # Flush current chunk
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = []
                    current_size = 0

                # If single paragraph is too large, split by words
                if para_len > chunk_size:
                    words = para.split()
                    word_chunk = []
                    word_size = 0

                    for word in words:
                        word_len = len(word) + 1
                        if word_size + word_len > chunk_size and word_chunk:
                            if current_chunk:
                                chunks.append('\n\n'.join(current_chunk))
                                current_chunk = []
                                current_size = 0
                            chunks.append(' '.join(word_chunk))
                            word_chunk = [word]
                            word_size = word_len
                        else:
                            word_chunk.append(word)
                            word_size += word_len

                    if word_chunk:
                        current_chunk.append(' '.join(word_chunk))
                        current_size += word_size
                else:
                    current_chunk.append(para)
                    current_size += para_len

            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))

        # Check max chunks limit
        if len(chunks) >= max_chunks:
            logger.warning(f"Reached max chunks ({max_chunks}), stopping")
            break

    return chunks[:max_chunks]


# ============================================================================
# Tool 14: INGEST_DOC - Import external documentation
# ============================================================================
@mcp.tool()
@with_request_id
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
    url_error, allowed_ips = _validate_url(url)
    if url_error:
        return {"error": url_error, "url": url}

    ctx = await get_project_context(project_path)

    content = await _fetch_and_extract(url, allowed_ips=allowed_ips)

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

    # Chunk the content with markdown-aware splitting
    # This preserves document structure by splitting at headers first,
    # ensuring function descriptions, API endpoints, etc. stay together
    chunks = _chunk_markdown_content(content, chunk_size, MAX_CHUNKS)

    if not chunks:
        return {
            "error": "Failed to chunk content",
            "url": url
        }

    # Store each chunk as a learning
    memories_created = []
    for i, chunk in enumerate(chunks):
        memory = await ctx.memory_manager.remember(
            category='learning',
            content=chunk[:500] + "..." if len(chunk) > 500 else chunk,
            rationale=f"Ingested from {url} (chunk {i+1}/{len(chunks)})",
            tags=['docs', 'ingested', topic],
            context={'source_url': url, 'chunk_index': i, 'total_chunks': len(chunks)},
            project_path=ctx.project_path
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
@with_request_id
async def propose_refactor(
    file_path: str,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate refactor suggestions for a file based on memory context.

    Combines:
    - File-specific memories (past decisions, warnings)
    - Causal history (what decisions LED TO the current state)
    - TODO/FIXME comments in the file
    - Relevant rules and patterns

    Returns structured context that helps the AI agent propose
    informed refactoring decisions, including WHY the code evolved
    the way it did.

    Args:
        file_path: The file to analyze for refactoring
        project_path: Path to the project root (for multi-project support)

    Returns:
        Combined context with memories, causal_history, todos, and suggested actions.
        The causal_history field traces backward through linked memories to show
        what decisions led to each memory associated with the file.

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
        "causal_history": [],
        "todos": [],
        "rules": {},
        "constraints": [],
        "opportunities": []
    }

    # Get file-specific memories
    file_memories = await ctx.memory_manager.recall_for_file(file_path, project_path=ctx.project_path)
    result["memories"] = file_memories

    # Trace causal chains for each memory to understand WHY the code evolved this way
    seen_chain_ids: set[int] = set()
    for category in ['decisions', 'patterns', 'warnings', 'learnings']:
        for mem in file_memories.get(category, []):
            mem_id = mem.get('id')
            if mem_id and mem_id not in seen_chain_ids:
                # Trace backward to find what led to this decision
                chain_result = await ctx.memory_manager.trace_chain(
                    memory_id=mem_id,
                    direction="backward",
                    max_depth=3  # Keep chains concise
                )
                if chain_result.get('chain'):
                    result["causal_history"].append({
                        "memory_id": mem_id,
                        "memory_content": mem.get('content', '')[:100],
                        "ancestors": [
                            {
                                "id": c["id"],
                                "category": c.get("category"),
                                "content": c.get("content", "")[:100],
                                "relationship": c.get("relationship"),
                                "depth": c.get("depth")
                            }
                            for c in chain_result["chain"]
                        ]
                    })
                    # Track IDs to avoid duplicate chain traces
                    seen_chain_ids.add(mem_id)
                    for c in chain_result["chain"]:
                        seen_chain_ids.add(c["id"])

    # Resolve file path relative to project directory
    absolute_file_path, error = _resolve_within_project(ctx.project_path, file_path)
    if error or absolute_file_path is None:
        result["error"] = error or "Invalid file path"
        return result

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
    num_causal_chains = len(result["causal_history"])

    result["message"] = (
        f"Analysis for {file_path}: "
        f"{num_memories} memories, "
        f"{num_constraints} constraints, "
        f"{num_opportunities} opportunities"
    )

    if num_causal_chains > 0:
        result["message"] += f" | {num_causal_chains} causal chains explain WHY code evolved this way"

    if num_constraints > 0:
        result["message"] += " | Review constraints before refactoring!"

    return result


# ============================================================================
# Tool 16: REBUILD_INDEX - Force rebuild of search indexes
# ============================================================================
@mcp.tool()
@with_request_id
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
@with_request_id
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
                "file_path_relative": m.file_path_relative,
                "keywords": m.keywords,
                "is_permanent": m.is_permanent,
                "outcome": m.outcome,
                "worked": m.worked,
                "pinned": m.pinned,
                "archived": m.archived,
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
@with_request_id
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

    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
        if parsed.tzinfo:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    memories_imported = 0
    rules_imported = 0

    async with ctx.db_manager.get_session() as session:
        if not merge:
            await session.execute(delete(Memory))
            await session.execute(delete(Rule))

        # Import memories
        for mem_data in data.get("memories", []):
            # Decode vector if present
            vector_bytes = None
            if mem_data.get("vector_embedding"):
                try:
                    vector_bytes = base64.b64decode(mem_data["vector_embedding"])
                except Exception:
                    pass

            # Normalize file_path if present and project_path is available
            from .memory import _normalize_file_path
            file_path_abs = mem_data.get("file_path")
            file_path_rel = mem_data.get("file_path_relative")
            if file_path_abs and ctx.project_path:
                file_path_abs, file_path_rel = _normalize_file_path(file_path_abs, ctx.project_path)

            memory = Memory(
                category=mem_data["category"],
                content=mem_data["content"],
                rationale=mem_data.get("rationale"),
                context=mem_data.get("context", {}),
                tags=mem_data.get("tags", []),
                file_path=file_path_abs,
                file_path_relative=file_path_rel,
                keywords=mem_data.get("keywords"),
                is_permanent=mem_data.get("is_permanent", False),
                outcome=mem_data.get("outcome"),
                worked=mem_data.get("worked"),
                pinned=mem_data.get("pinned", False),
                archived=mem_data.get("archived", False),
                created_at=_parse_datetime(mem_data.get("created_at")),
                updated_at=_parse_datetime(mem_data.get("updated_at")),
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
@with_request_id
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


# ============================================================================
# Graph Memory Tools - Explicit relationship edges between memories
# ============================================================================

@mcp.tool()
@with_request_id
async def link_memories(
    source_id: int,
    target_id: int,
    relationship: str,
    description: Optional[str] = None,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create an explicit relationship between two memories.

    Use this to build a knowledge graph of how decisions connect:
    - "led_to": Decision A caused or resulted in Pattern B
    - "supersedes": New approach replaces an old one
    - "depends_on": Pattern A requires Decision B to be valid
    - "conflicts_with": Warning contradicts a decision
    - "related_to": General association

    Args:
        source_id: The "from" memory ID
        target_id: The "to" memory ID
        relationship: One of: led_to, supersedes, depends_on, conflicts_with, related_to
        description: Optional context explaining this relationship
        project_path: Project root path

    Returns:
        Status of the link operation

    Examples:
        link_memories(42, 58, "led_to", "Database choice led to this caching pattern")
        link_memories(99, 42, "supersedes", "New auth approach replaces old one")
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)
    return await ctx.memory_manager.link_memories(
        source_id=source_id,
        target_id=target_id,
        relationship=relationship,
        description=description
    )


@mcp.tool()
@with_request_id
async def unlink_memories(
    source_id: int,
    target_id: int,
    relationship: Optional[str] = None,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Remove a relationship between two memories.

    Args:
        source_id: The "from" memory ID
        target_id: The "to" memory ID
        relationship: Specific relationship to remove (if None, removes all between the pair)
        project_path: Project root path

    Returns:
        Status of the unlink operation
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)
    return await ctx.memory_manager.unlink_memories(
        source_id=source_id,
        target_id=target_id,
        relationship=relationship
    )


@mcp.tool()
@with_request_id
async def trace_chain(
    memory_id: int,
    direction: str = "both",
    relationship_types: Optional[List[str]] = None,
    max_depth: int = 10,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Traverse the memory graph from a starting point.

    Use this to understand causal chains and dependencies:
    - "What decisions led to this pattern?"
    - "What depends on this library choice?"
    - "What's the full context around this warning?"

    Args:
        memory_id: Starting memory ID
        direction: "forward" (descendants), "backward" (ancestors), or "both"
        relationship_types: Filter to specific types (default: all)
        max_depth: How far to traverse (default: 10)
        project_path: Project root path

    Returns:
        Chain of connected memories with relationship info

    Examples:
        trace_chain(42, direction="backward")  # What led to this?
        trace_chain(42, direction="forward", relationship_types=["depends_on"])
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)
    return await ctx.memory_manager.trace_chain(
        memory_id=memory_id,
        direction=direction,
        relationship_types=relationship_types,
        max_depth=max_depth
    )


@mcp.tool()
@with_request_id
async def get_graph(
    memory_ids: Optional[List[int]] = None,
    topic: Optional[str] = None,
    format: str = "json",
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get a subgraph of memories and their relationships.

    Returns nodes (memories) and edges (relationships) for visualization
    or analysis. Can output as JSON or Mermaid diagram.

    Args:
        memory_ids: Specific memory IDs to include
        topic: Topic to search for (alternative to memory_ids)
        format: "json" or "mermaid" for diagram output
        project_path: Project root path

    Returns:
        Graph structure with nodes, edges, and optional mermaid diagram

    Examples:
        get_graph(memory_ids=[42, 58, 99])
        get_graph(topic="authentication", format="mermaid")
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)
    return await ctx.memory_manager.get_graph(
        memory_ids=memory_ids,
        topic=topic,
        format=format
    )


@mcp.tool()
@with_request_id
async def prune_memories(
    older_than_days: int = 90,
    categories: Optional[List[str]] = None,
    min_recall_count: int = 5,
    protect_successful: bool = True,
    dry_run: bool = True,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Prune old, low-value memories with saliency-based protection.

    By default, only affects episodic memories (decisions, learnings).
    Protected memories (never pruned):
    - Permanent memories (patterns, warnings)
    - Pinned memories
    - Memories with outcomes recorded
    - Frequently accessed memories (recall_count >= min_recall_count)
    - Successful decisions (worked=True) if protect_successful is True

    Args:
        older_than_days: Only prune memories older than this
        categories: Limit to these categories (default: decision, learning)
        min_recall_count: Protect memories accessed at least this many times (default: 5)
        protect_successful: Protect memories with worked=True (default: True)
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
        # Find prunable memories with saliency-based protection
        query = select(Memory).where(
            Memory.category.in_(categories),
            Memory.created_at < cutoff,
            Memory.is_permanent == False,  # noqa: E712
            Memory.pinned == False,  # noqa: E712
            Memory.outcome.is_(None),  # Don't prune memories with outcomes
            or_(Memory.archived == False, Memory.archived.is_(None)),  # noqa: E712
            or_(Memory.recall_count < min_recall_count, Memory.recall_count.is_(None))  # Saliency protection
        )

        # Optionally protect successful decisions
        if protect_successful:
            query = query.where(or_(Memory.worked != True, Memory.worked.is_(None)))  # noqa: E712

        result = await session.execute(query)
        to_prune = result.scalars().all()

        if dry_run:
            return {
                "dry_run": True,
                "would_prune": len(to_prune),
                "categories": categories,
                "older_than_days": older_than_days,
                "min_recall_count": min_recall_count,
                "protect_successful": protect_successful,
                "samples": [
                    {
                        "id": m.id,
                        "content": m.content[:50],
                        "recall_count": getattr(m, 'recall_count', 0) or 0,
                        "created_at": m.created_at.isoformat()
                    }
                    for m in to_prune[:5]
                ]
            }

        # Actually delete
        for memory in to_prune:
            await session.delete(memory)

    # Rebuild index to remove pruned documents
    await ctx.memory_manager.rebuild_index()

    return {
        "pruned": len(to_prune),
        "categories": categories,
        "older_than_days": older_than_days,
        "min_recall_count": min_recall_count,
        "message": f"Pruned {len(to_prune)} old memories (protected: pinned, outcomes, recall_count>={min_recall_count}, successful)"
    }


@mcp.tool()
@with_request_id
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
@with_request_id
async def cleanup_memories(
    dry_run: bool = True,
    merge_duplicates: bool = True,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Clean up stale and duplicate memories.

    Identifies duplicates by:
    - Same category + normalized content + file_path

    In dry_run mode: returns preview of what would be cleaned
    When merging: keeps newest, preserves outcomes from others

    Args:
        dry_run: Preview what would be cleaned (default: True)
        merge_duplicates: Merge duplicate memories (keep newest, preserve outcomes)
        project_path: Project root path

    Returns:
        Preview of duplicates (dry_run=True) or merge results (dry_run=False)

    Examples:
        cleanup_memories()  # Preview duplicates
        cleanup_memories(dry_run=False)  # Actually merge duplicates
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    async with ctx.db_manager.get_session() as session:
        result = await session.execute(select(Memory))
        all_memories = result.scalars().all()

        # Group by (category, normalized_content, file_path)
        groups = {}
        for mem in all_memories:
            # Normalize content for comparison (lowercase, collapse whitespace)
            normalized = ' '.join(mem.content.lower().split())
            key = (mem.category, normalized, mem.file_path or '')

            if key not in groups:
                groups[key] = []
            groups[key].append(mem)

        # Find duplicates (groups with more than 1 memory)
        duplicates = {k: v for k, v in groups.items() if len(v) > 1}

        if dry_run:
            return {
                "dry_run": True,
                "duplicate_groups": len(duplicates),
                "total_duplicates": sum(len(v) - 1 for v in duplicates.values()),
                "samples": [
                    {
                        "content": mems[0].content[:50],
                        "count": len(mems),
                        "ids": [m.id for m in mems]
                    }
                    for mems in list(duplicates.values())[:5]
                ]
            }

        # Merge duplicates: keep newest, preserve outcomes
        merged = 0
        if merge_duplicates:
            for key, mems in duplicates.items():
                def _to_naive(dt_value: Optional[datetime]) -> datetime:
                    if not dt_value:
                        return datetime.min
                    return dt_value.replace(tzinfo=None) if dt_value.tzinfo else dt_value

                def _outcome_timestamp(mem: Memory) -> datetime:
                    return _to_naive(mem.updated_at or mem.created_at)

                # Sort by created_at descending (newest first)
                mems.sort(key=lambda m: _to_naive(m.created_at), reverse=True)
                keeper = mems[0]

                # Pick the most recent outcome across duplicates (if any)
                outcome_source = None
                for candidate in mems:
                    if candidate.outcome:
                        if outcome_source is None or _outcome_timestamp(candidate) > _outcome_timestamp(outcome_source):
                            outcome_source = candidate

                if outcome_source:
                    keeper.outcome = outcome_source.outcome
                    keeper.worked = outcome_source.worked

                # Merge outcomes, tags, and metadata from others
                for dupe in mems[1:]:
                    # Preserve pinned status (if any duplicate is pinned, keep pinned)
                    if dupe.pinned and not keeper.pinned:
                        keeper.pinned = True

                    # If keeper is archived but duplicate isn't, unarchive
                    if not dupe.archived and keeper.archived:
                        keeper.archived = False

                    # Merge tags (union of all tags)
                    if dupe.tags:
                        keeper_tags = set(keeper.tags or [])
                        keeper_tags.update(dupe.tags or [])
                        keeper.tags = list(keeper_tags)

                # Update keeper's updated_at timestamp
                keeper.updated_at = datetime.now(timezone.utc)

                # Flush changes to keeper before deleting duplicates
                await session.flush()

                # Delete duplicates
                for dupe in mems[1:]:
                    await session.delete(dupe)
                    merged += 1

    # Rebuild index to reflect merged/deleted documents
    await ctx.memory_manager.rebuild_index()

    return {
        "merged": merged,
        "duplicate_groups": len(duplicates),
        "message": f"Merged {merged} duplicate memories"
    }


# ============================================================================
# Tool: COMPACT_MEMORIES - Consolidate episodic memories into summaries
# ============================================================================
@mcp.tool()
@with_request_id
async def compact_memories(
    summary: str,
    limit: int = 10,
    topic: Optional[str] = None,
    dry_run: bool = True,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Compact recent episodic memories into a single summary.

    Consolidates multiple decision/learning memories into one summary,
    archives the originals, and preserves history via graph edges.
    Use this to reduce recall noise while maintaining audit trails.

    Args:
        summary: The summary text (must be at least 50 characters)
        limit: Max number of memories to compact (default: 10)
        topic: Optional topic filter (matches content, rationale, or tags)
        dry_run: Preview candidates without changes (default: True)
        project_path: Project root path (for multi-project HTTP server support)

    Returns:
        Result with status, summary_id, compacted_count, etc.

    Examples:
        compact_memories("Summary of auth work...", limit=5, dry_run=True)
        compact_memories("Summary of DB decisions...", topic="database", dry_run=False)
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    return await ctx.memory_manager.compact_memories(
        summary=summary,
        limit=limit,
        topic=topic,
        dry_run=dry_run
    )


@mcp.tool()
@with_request_id
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
# Code Understanding Tools (Phase 2)
# ============================================================================

@mcp.tool()
@with_request_id
async def index_project(
    path: Optional[str] = None,
    patterns: Optional[List[str]] = None,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Index a project's code structure for understanding.

    Parses source files using tree-sitter to extract:
    - Classes, functions, methods
    - Signatures and docstrings
    - File locations

    Indexed entities can be searched with find_code() and
    analyzed with analyze_impact().

    Args:
        path: Path to index (defaults to project root)
        patterns: Glob patterns for files (defaults to all supported languages)
        project_path: Project root path

    Returns:
        Indexing statistics (entities indexed, files processed)
    """
    try:
        from .code_indexer import CodeIndexManager, is_available
    except ImportError:
        from daem0nmcp.code_indexer import CodeIndexManager, is_available

    if not is_available():
        return {
            "error": "Code indexing not available - install tree-sitter-languages",
            "indexed": 0
        }

    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    # Get Qdrant store if available
    qdrant = None
    try:
        from .qdrant_store import QdrantVectorStore
        qdrant_path = str(Path(ctx.storage_path) / "qdrant")
        qdrant = QdrantVectorStore(path=qdrant_path)
    except Exception:
        pass

    indexer = CodeIndexManager(db=ctx.db_manager, qdrant=qdrant)

    target_path = path or ctx.project_path
    result = await indexer.index_project(target_path, patterns)

    return {
        "result": result,
        "message": f"Indexed {result.get('indexed', 0)} code entities from {result.get('files_processed', 0)} files"
    }


@mcp.tool()
@with_request_id
async def find_code(
    query: str,
    project_path: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Semantic search across indexed code entities.

    Finds classes, functions, and methods that match your query.
    Uses vector similarity for natural language understanding.

    Example queries:
    - "user authentication"
    - "database connection handling"
    - "API request validation"

    Args:
        query: Search query (natural language)
        project_path: Project root path
        limit: Maximum results (default: 20)

    Returns:
        Matching code entities with relevance scores
    """
    try:
        from .code_indexer import CodeIndexManager, is_available
    except ImportError:
        from daem0nmcp.code_indexer import CodeIndexManager, is_available

    if not is_available():
        return {
            "error": "Code indexing not available - install tree-sitter-languages",
            "results": []
        }

    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    # Get Qdrant store if available
    qdrant = None
    try:
        from .qdrant_store import QdrantVectorStore
        qdrant_path = str(Path(ctx.storage_path) / "qdrant")
        qdrant = QdrantVectorStore(path=qdrant_path)
    except Exception:
        pass

    indexer = CodeIndexManager(db=ctx.db_manager, qdrant=qdrant)

    results = await indexer.search_entities(query, ctx.project_path, limit)

    return {
        "query": query,
        "results": results,
        "count": len(results)
    }


@mcp.tool()
@with_request_id
async def analyze_impact(
    entity_name: str,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyze what would be affected by changing a code entity.

    Helps understand the blast radius of changes by finding:
    - Files that would be affected
    - Other entities that depend on this one
    - Call sites and usage patterns

    Args:
        entity_name: Name of the function/class/method to analyze
        project_path: Project root path

    Returns:
        Impact analysis with affected files and entities
    """
    try:
        from .code_indexer import CodeIndexManager, is_available
    except ImportError:
        from daem0nmcp.code_indexer import CodeIndexManager, is_available

    if not is_available():
        return {
            "error": "Code indexing not available - install tree-sitter-languages",
            "entity": entity_name,
            "found": False
        }

    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    indexer = CodeIndexManager(db=ctx.db_manager, qdrant=None)

    result = await indexer.analyze_impact(entity_name, ctx.project_path)

    return {"result": result}


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
