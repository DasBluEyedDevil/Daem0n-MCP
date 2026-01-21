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
14. Active working context (MemGPT-style always-hot memories)

42 Tools:
- remember: Store a decision, pattern, warning, or learning (with file association)
- recall: Retrieve relevant memories for a topic (semantic search)
- recall_for_file: Get all memories for a specific file
- recall_by_entity: Get all memories mentioning a specific code entity
- list_entities: List most frequently mentioned entities
- backfill_entities: Extract entities from all existing memories
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
- link_projects: Create a link to another project for cross-repo memory awareness
- unlink_projects: Remove a link to another project
- list_linked_projects: List all linked projects
- set_active_context: Add a memory to the active working context
- get_active_context: Get all memories in the active working context
- remove_from_active_context: Remove a memory from active context
- clear_active_context: Clear all memories from active context
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
    from fastmcp import FastMCP
except ImportError:
    print("ERROR: fastmcp not installed. Run: pip install fastmcp>=3.0.0b1", file=sys.stderr)
    sys.exit(1)

try:
    from .config import settings
    from .database import DatabaseManager
    from .memory import MemoryManager
    from .rules import RulesEngine
    from .models import Memory, Rule, CodeEntity
    from . import __version__
    from . import vectors
    from .logging_config import StructuredFormatter, with_request_id, request_id_var, set_release_callback
    from .covenant import set_context_callback
    from .transforms.covenant import CovenantMiddleware, _FASTMCP_MIDDLEWARE_AVAILABLE
    from .rwlock import RWLock
except ImportError:
    # For fastmcp run which executes server.py directly
    from daem0nmcp.config import settings
    from daem0nmcp.database import DatabaseManager
    from daem0nmcp.memory import MemoryManager
    from daem0nmcp.rules import RulesEngine
    from daem0nmcp.models import Memory, Rule, CodeEntity
    from daem0nmcp import __version__
    from daem0nmcp import vectors
    from daem0nmcp.logging_config import StructuredFormatter, with_request_id, request_id_var, set_release_callback
    from daem0nmcp.covenant import set_context_callback
    from daem0nmcp.transforms.covenant import CovenantMiddleware, _FASTMCP_MIDDLEWARE_AVAILABLE
    from daem0nmcp.rwlock import RWLock
from sqlalchemy import select, delete, or_, func
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
    # Covenant state tracking
    briefed: bool = False  # True after get_briefing called
    context_checks: List[Dict[str, Any]] = field(default_factory=list)  # Timestamped context checks


# Cache of project contexts by normalized path
_project_contexts: Dict[str, ProjectContext] = {}
_context_locks: Dict[str, asyncio.Lock] = {}
_contexts_lock = RWLock()  # RWLock for context access: multiple readers, exclusive writers
_task_contexts: Dict[asyncio.Task, Dict[str, int]] = {}
_task_contexts_lock = asyncio.Lock()
_last_eviction: float = 0.0
_EVICTION_INTERVAL_SECONDS: float = 60.0

# Default project path (ONLY used if DAEM0NMCP_PROJECT_ROOT is explicitly set)
_default_project_path: Optional[str] = os.environ.get('DAEM0NMCP_PROJECT_ROOT')


def _get_context_for_covenant(project_path: str) -> Optional[ProjectContext]:
    """
    Get a project context for covenant enforcement.

    This is called by the covenant decorators to check session state.
    """
    try:
        normalized = str(Path(project_path).resolve())
        return _project_contexts.get(normalized)
    except Exception:
        return None


# Register the callback for covenant enforcement
set_context_callback(_get_context_for_covenant)


def _get_context_state_for_middleware(project_path: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Get covenant state for middleware enforcement.

    This callback is used by CovenantMiddleware to check session state.
    It returns the state dict expected by CovenantTransform.check_tool_access().

    Args:
        project_path: Project path to look up (may be None for some tools)

    Returns:
        Dict with 'briefed' and 'context_checks' keys, or None if no context
    """
    if project_path is None:
        return None

    ctx = _get_context_for_covenant(project_path)
    if ctx is None:
        return None

    return {
        "briefed": ctx.briefed,
        "context_checks": ctx.context_checks,
    }


# Register CovenantMiddleware with FastMCP server (if available)
if _FASTMCP_MIDDLEWARE_AVAILABLE:
    _covenant_middleware = CovenantMiddleware(
        get_state=_get_context_state_for_middleware,
    )
    mcp.add_middleware(_covenant_middleware)
    logger.info("CovenantMiddleware registered with FastMCP server")
else:
    logger.warning(
        "FastMCP 3.0 middleware not available - falling back to decorator-based enforcement"
    )


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


def _check_covenant_communion(project_path: str) -> Optional[Dict[str, Any]]:
    """
    Check if communion (get_briefing) was performed for this project.

    This function provides direct covenant enforcement for tool calls that
    bypass the FastMCP middleware (e.g., direct function calls in tests).

    Args:
        project_path: Project to check

    Returns:
        Violation dict if communion required, None if communion complete
    """
    from .covenant import CovenantViolation

    ctx = _get_context_for_covenant(project_path)
    if ctx is None or not ctx.briefed:
        return CovenantViolation.communion_required(project_path)
    return None


def _check_covenant_counsel(tool_name: str, project_path: str) -> Optional[Dict[str, Any]]:
    """
    Check if counsel (context_check) was sought for this project.

    This function provides direct covenant enforcement for tool calls that
    bypass the FastMCP middleware (e.g., direct function calls in tests).

    Args:
        tool_name: Name of the tool being called
        project_path: Project to check

    Returns:
        Violation dict if counsel required, None if counsel is fresh
    """
    from .covenant import CovenantViolation, COUNSEL_TTL_SECONDS

    # First check communion
    communion_violation = _check_covenant_communion(project_path)
    if communion_violation:
        return communion_violation

    ctx = _get_context_for_covenant(project_path)
    if ctx is None:
        return CovenantViolation.counsel_required(tool_name, project_path)

    context_checks = ctx.context_checks
    if not context_checks:
        return CovenantViolation.counsel_required(tool_name, project_path)

    # Find the most recent context check and verify it's still fresh
    now = datetime.now(timezone.utc)
    most_recent_age = None

    for check in context_checks:
        if isinstance(check, dict) and "timestamp" in check:
            try:
                check_time = datetime.fromisoformat(check["timestamp"])
                if check_time.tzinfo is None:
                    check_time = check_time.replace(tzinfo=timezone.utc)
                age = (now - check_time).total_seconds()
                if most_recent_age is None or age < most_recent_age:
                    most_recent_age = age
            except (ValueError, TypeError):
                continue

    if most_recent_age is None:
        return CovenantViolation.counsel_required(tool_name, project_path)

    if most_recent_age > COUNSEL_TTL_SECONDS:
        return CovenantViolation.counsel_expired(tool_name, project_path, int(most_recent_age))

    return None  # Counsel is fresh


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
    Thread-safe with RWLock for concurrent access to prevent race conditions.

    Uses double-checked locking pattern with RWLock:
    - Fast path uses read lock (allows concurrent readers)
    - Slow path uses write lock (exclusive access for context creation)

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

    # Fast path with read lock: context exists and is initialized
    # Multiple concurrent readers can check simultaneously
    async with _contexts_lock.read():
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

    # Slow path: need to create context, requires write lock
    async with _contexts_lock.write():
        # Double-check after acquiring write lock (another writer may have created it)
        if normalized in _project_contexts:
            ctx = _project_contexts[normalized]
            if ctx.initialized:
                now = time.time()
                ctx.last_accessed = now
                _maybe_schedule_eviction(now)
                await _track_task_context(ctx)
                return ctx

        # Get or create per-project lock for initialization
        if normalized not in _context_locks:
            _context_locks[normalized] = asyncio.Lock()
        lock = _context_locks[normalized]

    # Initialize under project-specific lock (outside RWLock to avoid holding it during I/O)
    async with lock:
        # Triple-check: another task may have initialized while we waited for per-project lock
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

        # Store in cache under write lock
        async with _contexts_lock.write():
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
    async with _contexts_lock.read():
        for path, ctx in _project_contexts.items():
            if (now - ctx.last_accessed) <= CONTEXT_TTL_SECONDS:
                continue
            # Skip if path-level lock is held
            if _context_locks.get(path) and _context_locks[path].locked():
                continue
            ttl_candidates.append(path)

    # Phase 2: Process TTL candidates individually
    for path in ttl_candidates:
        async with _contexts_lock.write():
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
        async with _contexts_lock.write():
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
    async with _contexts_lock.write():
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
@mcp.tool(version="3.0.0")
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
    Store a memory (decision/pattern/warning/learning).
    Auto-detects conflicts with past failures. Patterns and warnings are permanent.

    Args:
        category: One of 'decision', 'pattern', 'warning', 'learning'
        content: What to remember
        rationale: Why this matters
        context: Structured context dict
        tags: List of tags for retrieval
        file_path: Associate with a file
        project_path: Project root
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    effective_path = project_path or _default_project_path

    # Covenant enforcement: remember requires counsel (which implies communion)
    violation = _check_covenant_counsel("remember", effective_path)
    if violation:
        return violation

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
@mcp.tool(version="3.0.0")
@with_request_id
async def remember_batch(
    memories: List[Dict[str, Any]],
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Store multiple memories atomically. Efficient for bulk imports.

    Args:
        memories: List of dicts with category, content, rationale (opt), tags (opt), file_path (opt)
        project_path: Project root
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
@mcp.tool(version="3.0.0")
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
    project_path: Optional[str] = None,
    include_linked: bool = False,
    condensed: bool = False
) -> Dict[str, Any]:
    """
    Semantic search for memories using TF-IDF. Results weighted by relevance, recency, importance.

    Args:
        topic: What to search for
        categories: Filter by category
        tags: Filter by tags
        file_path: Filter by file
        offset/limit: Pagination
        since/until: Date range (ISO format)
        project_path: Project root
        include_linked: Search linked projects
        condensed: Compress output (~75% token reduction)
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    effective_path = project_path or _default_project_path

    # Covenant enforcement: recall requires communion (briefing)
    violation = _check_covenant_communion(effective_path)
    if violation:
        return violation

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
        project_path=ctx.project_path,
        include_linked=include_linked,
        condensed=condensed
    )


# ============================================================================
# Tool 3: ADD_RULE - Create a decision tree node
# ============================================================================
@mcp.tool(version="3.0.0")
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
    Add a decision tree rule. Rules are matched semantically.

    Args:
        trigger: What activates this rule (natural language)
        must_do: Required actions
        must_not: Forbidden actions
        ask_first: Questions to consider
        warnings: Past experience warnings
        priority: Higher = shown first
        project_path: Project root
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
@mcp.tool(version="3.0.0")
@with_request_id
async def check_rules(
    action: str,
    context: Optional[Dict[str, Any]] = None,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Check if an action matches any rules. Call before significant changes.

    Args:
        action: What you're about to do
        context: Optional context dict
        project_path: Project root
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)
    return await ctx.rules_engine.check_rules(action=action, context=context)


# ============================================================================
# Tool 5: RECORD_OUTCOME - Track if a decision worked
# ============================================================================
@mcp.tool(version="3.0.0")
@with_request_id
async def record_outcome(
    memory_id: int,
    outcome: str,
    worked: bool,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Record whether a decision worked. Failed outcomes get boosted in future searches.

    Args:
        memory_id: ID from remember()
        outcome: What happened
        worked: True/False
        project_path: Project root
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)
    effective_project_path = project_path or _default_project_path
    return await ctx.memory_manager.record_outcome(
        memory_id=memory_id,
        outcome=outcome,
        worked=worked,
        project_path=effective_project_path
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

        # Get recent decisions (last 5) - truncate content for token efficiency
        result = await session.execute(
            select(Memory)
            .where(Memory.category == 'decision')
            .order_by(Memory.created_at.desc())
            .limit(5)
        )
        recent_decisions = [
            {
                "id": m.id,
                "content": m.content[:200] + "..." if len(m.content) > 200 else m.content,
                "worked": m.worked,
                "created_at": m.created_at.isoformat()
            }
            for m in result.scalars().all()
        ]

        # Get active warnings - truncate content for token efficiency
        result = await session.execute(
            select(Memory)
            .where(Memory.category == 'warning')
            .order_by(Memory.created_at.desc())
            .limit(10)
        )
        active_warnings = [
            {"id": m.id, "content": m.content[:200] + "..." if len(m.content) > 200 else m.content}
            for m in result.scalars().all()
        ]

        # Get FAILED decisions - these are critical (truncate for token efficiency)
        result = await session.execute(
            select(Memory)
            .where(Memory.worked == False)  # noqa: E712
            .order_by(Memory.created_at.desc())
            .limit(5)
        )
        failed_approaches = [
            {
                "id": m.id,
                "content": m.content[:200] + "..." if len(m.content) > 200 else m.content,
                "outcome": (m.outcome[:150] + "...") if m.outcome and len(m.outcome) > 150 else m.outcome,
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
            area, limit=5, project_path=ctx.project_path,
            condensed=True  # Use condensed mode for token efficiency
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


async def _get_linked_projects_summary(ctx: ProjectContext) -> List[Dict[str, Any]]:
    """
    Get summary of linked projects with warning/memory counts.

    Args:
        ctx: Project context with db_manager and project_path

    Returns:
        List of dicts with path, relationship, label, available, warning_count, memory_count
    """
    from .links import LinkManager

    link_mgr = LinkManager(ctx.db_manager)
    links = await link_mgr.list_linked_projects(ctx.project_path)

    summaries = []
    for link in links:
        linked_path = link["linked_path"]
        linked_storage = Path(linked_path) / ".daem0nmcp" / "storage"

        summary = {
            "path": linked_path,
            "relationship": link["relationship"],
            "label": link.get("label"),
            "available": False,
            "warning_count": 0,
            "memory_count": 0
        }

        if linked_storage.exists():
            try:
                linked_db = DatabaseManager(str(linked_storage))
                await linked_db.init_db()

                linked_memory = MemoryManager(linked_db)
                stats = await linked_memory.get_statistics()

                summary["available"] = True
                summary["warning_count"] = stats.get("by_category", {}).get("warning", 0)
                summary["memory_count"] = stats.get("total_memories", 0)
            except Exception as e:
                logger.warning(f"Could not get summary for linked project {linked_path}: {e}")

        summaries.append(summary)

    return summaries


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
@mcp.tool(version="3.0.0")
@with_request_id
async def get_briefing(
    project_path: Optional[str] = None,
    focus_areas: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Session start - call FIRST. Returns stats, recent decisions, warnings, failed approaches, git changes.

    Args:
        project_path: Project root (REQUIRED)
        focus_areas: Topics to pre-fetch
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

    # Get linked projects summary
    linked_summary = await _get_linked_projects_summary(ctx)

    # Build actionable message
    message = _build_briefing_message(
        stats=stats,
        bootstrap_result=bootstrap_result,
        failed_approaches=recent_context["failed_approaches"],
        active_warnings=recent_context["active_warnings"],
        git_changes=git_changes
    )

    # Mark this project as briefed (Sacred Covenant: communion complete)
    ctx.briefed = True

    # Get active working context
    active_context = {"count": 0, "items": [], "max_count": 10}
    try:
        try:
            from .active_context import ActiveContextManager
        except ImportError:
            from daem0nmcp.active_context import ActiveContextManager

        acm = ActiveContextManager(ctx.db_manager)
        active_context = await acm.get_active_context(ctx.project_path, condensed=True)

        # Clean up expired items
        await acm.cleanup_expired(ctx.project_path)
    except Exception as e:
        logger.warning(f"Failed to fetch active context: {e}")
        active_context["error"] = str(e)

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
        "linked_projects": linked_summary,
        "active_context": active_context,
        "message": message
    }


# ============================================================================
# Tool 7: SEARCH - Full text search across memories
# ============================================================================
@mcp.tool(version="3.0.0")
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
    Full-text search across all memories with TF-IDF ranking.

    Args:
        query: Search text
        limit/offset: Pagination
        include_meta: Return pagination metadata
        highlight: Include matched term excerpts
        highlight_start/end: Tags for highlighting
        project_path: Project root
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
@mcp.tool(version="3.0.0")
@with_request_id
async def list_rules(
    enabled_only: bool = True,
    limit: int = 50,
    project_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all configured rules.

    Args:
        enabled_only: Only show enabled rules
        limit: Max results
        project_path: Project root
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)
    return await ctx.rules_engine.list_rules(enabled_only=enabled_only, limit=limit)


# ============================================================================
# Tool 9: UPDATE_RULE - Modify existing rules
# ============================================================================
@mcp.tool(version="3.0.0")
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
        rule_id: ID of rule to update
        must_do/must_not/ask_first/warnings: New lists (replace existing)
        priority: New priority
        enabled: Enable/disable
        project_path: Project root
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
@mcp.tool(version="3.0.0")
@with_request_id
async def find_related(
    memory_id: int,
    limit: int = 5,
    project_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Find memories semantically related to a specific memory.

    Args:
        memory_id: Memory to find relations for
        limit: Max results
        project_path: Project root
    """
    # Require project_path for multi-project support
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)
    return await ctx.memory_manager.find_related(memory_id=memory_id, limit=limit)


# ============================================================================
# Tool 11: CONTEXT_CHECK - Quick relevance check for current work
# ============================================================================
@mcp.tool(version="3.0.0")
@with_request_id
async def context_check(
    description: str,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Pre-flight check combining recall + check_rules. Issues preflight token valid for 5 min.

    Args:
        description: What you're about to do
        project_path: Project root
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
    if not isinstance(rules, dict):
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

    # From rules (defensive check for None)
    guidance = rules.get('guidance') if rules else None
    if guidance and guidance.get('warnings'):
        for w in guidance['warnings']:
            warnings.append({
                "source": "rule",
                "content": w
            })

    has_concerns = len(warnings) > 0 or (rules and rules.get('has_blockers', False))

    # Record this context check (Sacred Covenant: counsel sought)
    ctx.context_checks.append({
        "description": description,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    # Issue preflight token as proof of consultation
    from .covenant import PreflightToken
    from .enforcement import get_session_id

    token = PreflightToken.issue(
        action=description,
        session_id=get_session_id(ctx.project_path),
        project_path=ctx.project_path,
    )

    return {
        "description": description,
        "has_concerns": has_concerns,
        "memories_found": memories.get('found', 0),
        "rules_matched": rules.get('matched_rules', 0) if rules else 0,
        "warnings": warnings,
        "must_do": guidance.get('must_do', []) if guidance else [],
        "must_not": guidance.get('must_not', []) if guidance else [],
        "ask_first": guidance.get('ask_first', []) if guidance else [],
        "preflight_token": token.serialize(),
        "message": (
            "⚠️ Review warnings before proceeding" if has_concerns else
            "✓ No concerns found, but always use good judgment"
        )
    }


# ============================================================================
# Tool 12: RECALL_FOR_FILE - Get memories for a specific file
# ============================================================================
@mcp.tool(version="3.0.0")
@with_request_id
async def recall_for_file(
    file_path: str,
    limit: int = 10,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get all memories associated with a specific file.

    Args:
        file_path: File to look up
        limit: Max results
        project_path: Project root
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
@mcp.tool(version="3.0.0")
@with_request_id
async def scan_todos(
    path: Optional[str] = None,
    auto_remember: bool = False,
    types: Optional[List[str]] = None,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Scan codebase for TODO/FIXME/HACK/XXX/BUG comments.

    Args:
        path: Directory to scan
        auto_remember: Save as warning memories
        types: Filter to specific types
        project_path: Project root
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
@mcp.tool(version="3.0.0")
@with_request_id
async def ingest_doc(
    url: str,
    topic: str,
    chunk_size: int = 2000,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch external docs from URL and store as learnings. Content is chunked.

    Args:
        url: URL to fetch
        topic: Tag for organizing
        chunk_size: Max chars per chunk
        project_path: Project root
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
@mcp.tool(version="3.0.0")
@with_request_id
async def propose_refactor(
    file_path: str,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate refactor suggestions combining file memories, causal history, TODOs, and rules.

    Args:
        file_path: File to analyze
        project_path: Project root
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
@mcp.tool(version="3.0.0")
@with_request_id
async def rebuild_index(
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Force rebuild of TF-IDF/vector indexes. Use if search seems stale.

    Args:
        project_path: Project root
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


@mcp.tool(version="3.0.0")
@with_request_id
async def export_data(
    project_path: Optional[str] = None,
    include_vectors: bool = False
) -> Dict[str, Any]:
    """
    Export all memories and rules as JSON for backup/migration.

    Args:
        project_path: Project root
        include_vectors: Include embeddings (large)
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


@mcp.tool(version="3.0.0")
@with_request_id
async def import_data(
    data: Dict[str, Any],
    project_path: Optional[str] = None,
    merge: bool = True
) -> Dict[str, Any]:
    """
    Import memories/rules from exported JSON.

    Args:
        data: Exported data structure
        merge: Add to existing (True) or replace all (False)
        project_path: Project root
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


@mcp.tool(version="3.0.0")
@with_request_id
async def pin_memory(
    memory_id: int,
    pinned: bool = True,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Pin/unpin a memory. Pinned: never pruned, boosted in recall, permanent.

    Args:
        memory_id: Memory to pin
        pinned: True to pin, False to unpin
        project_path: Project root
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

@mcp.tool(version="3.0.0")
@with_request_id
async def link_memories(
    source_id: int,
    target_id: int,
    relationship: str,
    description: Optional[str] = None,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create relationship between memories. Types: led_to, supersedes, depends_on, conflicts_with, related_to.

    Args:
        source_id: From memory ID
        target_id: To memory ID
        relationship: Relationship type
        description: Optional context
        project_path: Project root
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


@mcp.tool(version="3.0.0")
@with_request_id
async def unlink_memories(
    source_id: int,
    target_id: int,
    relationship: Optional[str] = None,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Remove relationship between memories.

    Args:
        source_id: From memory ID
        target_id: To memory ID
        relationship: Specific type to remove (None = all)
        project_path: Project root
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)
    return await ctx.memory_manager.unlink_memories(
        source_id=source_id,
        target_id=target_id,
        relationship=relationship
    )


@mcp.tool(version="3.0.0")
@with_request_id
async def trace_chain(
    memory_id: int,
    direction: str = "both",
    relationship_types: Optional[List[str]] = None,
    max_depth: int = 10,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Traverse memory graph to understand causal chains and dependencies.

    Args:
        memory_id: Starting point
        direction: forward/backward/both
        relationship_types: Filter by type
        max_depth: How far to traverse
        project_path: Project root
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


@mcp.tool(version="3.0.0")
@with_request_id
async def get_graph(
    memory_ids: Optional[List[int]] = None,
    topic: Optional[str] = None,
    format: str = "json",
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get subgraph of memories and relationships as JSON or Mermaid diagram.

    Args:
        memory_ids: Specific IDs to include
        topic: Alternative to memory_ids
        format: json or mermaid
        project_path: Project root
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)
    return await ctx.memory_manager.get_graph(
        memory_ids=memory_ids,
        topic=topic,
        format=format
    )


@mcp.tool(version="3.0.0")
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
    Prune old low-value memories. Protected: permanent, pinned, with outcomes, frequently accessed.

    Args:
        older_than_days: Age threshold
        categories: Limit to these categories
        min_recall_count: Protect if accessed >= N times
        protect_successful: Protect worked=True
        dry_run: Preview only
        project_path: Project root
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


@mcp.tool(version="3.0.0")
@with_request_id
async def archive_memory(
    memory_id: int,
    archived: bool = True,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Archive/unarchive a memory. Archived = hidden from recall but preserved.

    Args:
        memory_id: Memory to archive
        archived: True to archive, False to restore
        project_path: Project root
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


@mcp.tool(version="3.0.0")
@with_request_id
async def cleanup_memories(
    dry_run: bool = True,
    merge_duplicates: bool = True,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Merge duplicate memories (same category + content + file_path). Keeps newest.

    Args:
        dry_run: Preview only
        merge_duplicates: Actually merge
        project_path: Project root
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
@mcp.tool(version="3.0.0")
@with_request_id
async def compact_memories(
    summary: str,
    limit: int = 10,
    topic: Optional[str] = None,
    dry_run: bool = True,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Consolidate recent episodic memories into a summary. Originals archived with graph links.

    Args:
        summary: Summary text (min 50 chars)
        limit: Max memories to compact
        topic: Filter by topic
        dry_run: Preview only
        project_path: Project root
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


@mcp.tool(version="3.0.0")
@with_request_id
async def health(
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get server health, version, and statistics.

    Args:
        project_path: Project root
    """
    import time

    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)
    stats = await ctx.memory_manager.get_statistics()

    # Get rule count
    rules = await ctx.rules_engine.list_rules(enabled_only=False, limit=1000)

    # Code entity stats
    async with ctx.db_manager.get_session() as session:
        result = await session.execute(select(func.count(CodeEntity.id)))
        entity_count = result.scalar() or 0

        result = await session.execute(select(func.max(CodeEntity.indexed_at)))
        last_indexed = result.scalar()

        result = await session.execute(
            select(CodeEntity.entity_type, func.count(CodeEntity.id))
            .group_by(CodeEntity.entity_type)
        )
        entities_by_type = {row[0]: row[1] for row in result.all()}

    # Index freshness
    index_age_seconds = None
    index_stale = False
    if last_indexed:
        now = datetime.now(timezone.utc)
        if last_indexed.tzinfo is None:
            last_indexed = last_indexed.replace(tzinfo=timezone.utc)
        index_age_seconds = (now - last_indexed).total_seconds()
        index_stale = index_age_seconds > 86400  # 24 hours

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
        "timestamp": time.time(),
        # Code index stats
        "code_entities_count": entity_count,
        "entities_by_type": entities_by_type,
        "last_indexed_at": last_indexed.isoformat() if last_indexed else None,
        "index_age_seconds": index_age_seconds,
        "index_stale": index_stale,
    }


# ============================================================================
# Code Understanding Tools (Phase 2)
# ============================================================================

@mcp.tool(version="3.0.0")
@with_request_id
async def index_project(
    path: Optional[str] = None,
    patterns: Optional[List[str]] = None,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Index code structure using tree-sitter. Extracts classes, functions, methods with signatures.

    Args:
        path: Path to index
        patterns: Glob patterns for files
        project_path: Project root
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


@mcp.tool(version="3.0.0")
@with_request_id
async def find_code(
    query: str,
    project_path: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Semantic search across indexed code entities using vector similarity.

    Args:
        query: Natural language query
        limit: Max results
        project_path: Project root
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


@mcp.tool(version="3.0.0")
@with_request_id
async def analyze_impact(
    entity_name: str,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyze blast radius of changing a code entity. Finds affected files and dependents.

    Args:
        entity_name: Function/class/method name
        project_path: Project root
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
# LINKED PROJECTS - Cross-project memory awareness
# ============================================================================
@mcp.tool(version="3.0.0")
@with_request_id
async def link_projects(
    linked_path: str,
    relationship: str = "related",
    label: Optional[str] = None,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Link to another project for cross-project memory reading (write isolation preserved).

    Args:
        linked_path: Path to link
        relationship: same-project/upstream/downstream/related
        label: Optional human-readable label
        project_path: Project root
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    try:
        from .links import LinkManager
    except ImportError:
        from daem0nmcp.links import LinkManager

    link_mgr = LinkManager(ctx.db_manager)
    return await link_mgr.link_projects(
        source_path=ctx.project_path,
        linked_path=linked_path,
        relationship=relationship,
        label=label
    )


@mcp.tool(version="3.0.0")
@with_request_id
async def unlink_projects(
    linked_path: str,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Remove project link.

    Args:
        linked_path: Path to unlink
        project_path: Project root
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    try:
        from .links import LinkManager
    except ImportError:
        from daem0nmcp.links import LinkManager

    link_mgr = LinkManager(ctx.db_manager)
    return await link_mgr.unlink_projects(
        source_path=ctx.project_path,
        linked_path=linked_path
    )


@mcp.tool(version="3.0.0")
@with_request_id
async def list_linked_projects(
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    List all linked projects.

    Args:
        project_path: Project root
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    try:
        from .links import LinkManager
    except ImportError:
        from daem0nmcp.links import LinkManager

    link_mgr = LinkManager(ctx.db_manager)
    links = await link_mgr.list_linked_projects(source_path=ctx.project_path)
    return {"links": links}


@mcp.tool(version="3.0.0")
@with_request_id
async def consolidate_linked_databases(
    archive_sources: bool = False,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Merge memories from all linked projects into this one. For monorepo transitions.

    Args:
        archive_sources: Rename source .daem0nmcp to .daem0nmcp.archived
        project_path: Project root
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    try:
        from .links import LinkManager
    except ImportError:
        from daem0nmcp.links import LinkManager

    link_mgr = LinkManager(ctx.db_manager)
    return await link_mgr.consolidate_linked_databases(
        target_path=ctx.project_path,
        archive_sources=archive_sources
    )


# ============================================================================
# Active Working Context Tools (MemGPT-style always-hot memories)
# ============================================================================

@mcp.tool(version="3.0.0")
@with_request_id
async def set_active_context(
    memory_id: int,
    reason: Optional[str] = None,
    priority: int = 0,
    expires_in_hours: Optional[int] = None,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Add memory to always-hot working context. Auto-included in briefings.

    Args:
        memory_id: Memory to add
        reason: Why it should stay hot
        priority: Higher = shown first
        expires_in_hours: Auto-remove after N hours
        project_path: Project root
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    try:
        from .active_context import ActiveContextManager
    except ImportError:
        from daem0nmcp.active_context import ActiveContextManager

    ctx = await get_project_context(project_path)
    acm = ActiveContextManager(ctx.db_manager)

    expires_at = None
    if expires_in_hours:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)

    return await acm.add_to_context(
        project_path=ctx.project_path,
        memory_id=memory_id,
        reason=reason,
        priority=priority,
        expires_at=expires_at
    )


@mcp.tool(version="3.0.0")
@with_request_id
async def get_active_context(
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get all always-hot memories ordered by priority.

    Args:
        project_path: Project root
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    try:
        from .active_context import ActiveContextManager
    except ImportError:
        from daem0nmcp.active_context import ActiveContextManager

    ctx = await get_project_context(project_path)
    acm = ActiveContextManager(ctx.db_manager)

    return await acm.get_active_context(ctx.project_path)


@mcp.tool(version="3.0.0")
@with_request_id
async def remove_from_active_context(
    memory_id: int,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Remove memory from active context.

    Args:
        memory_id: Memory to remove
        project_path: Project root
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    try:
        from .active_context import ActiveContextManager
    except ImportError:
        from daem0nmcp.active_context import ActiveContextManager

    ctx = await get_project_context(project_path)
    acm = ActiveContextManager(ctx.db_manager)

    return await acm.remove_from_context(ctx.project_path, memory_id)


@mcp.tool(version="3.0.0")
@with_request_id
async def clear_active_context(
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Clear all active context memories. Use when switching focus.

    Args:
        project_path: Project root
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    try:
        from .active_context import ActiveContextManager
    except ImportError:
        from daem0nmcp.active_context import ActiveContextManager

    ctx = await get_project_context(project_path)
    acm = ActiveContextManager(ctx.db_manager)

    return await acm.clear_context(ctx.project_path)


# ============================================================================
# TEMPORAL VERSIONING - Memory History Tools
# ============================================================================


@mcp.tool(version="3.0.0")
@with_request_id
async def get_memory_versions(
    memory_id: int,
    limit: int = 50,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get version history showing how a memory evolved over time.

    Args:
        memory_id: Memory to query
        limit: Max versions
        project_path: Project root
    """
    if project_path is None and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)
    versions = await ctx.memory_manager.get_memory_versions(memory_id, limit)

    return {
        "memory_id": memory_id,
        "version_count": len(versions),
        "versions": versions
    }


@mcp.tool(version="3.0.0")
@with_request_id
async def get_memory_at_time(
    memory_id: int,
    timestamp: str,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get memory state at a specific point in time.

    Args:
        memory_id: Memory to query
        timestamp: ISO format timestamp
        project_path: Project root
    """
    if project_path is None and not _default_project_path:
        return _missing_project_path_error()

    try:
        point_in_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    except ValueError as e:
        return {"error": f"Invalid timestamp format: {e}"}

    ctx = await get_project_context(project_path)
    historical = await ctx.memory_manager.get_memory_at_time(memory_id, point_in_time)

    if historical is None:
        return {
            "error": "NOT_FOUND",
            "message": f"Memory {memory_id} did not exist at {timestamp}"
        }

    return historical


# ============================================================================
# COMMUNITY MANAGEMENT TOOLS - GraphRAG-style Hierarchical Summarization
# ============================================================================


@mcp.tool(version="3.0.0")
@with_request_id
async def rebuild_communities(
    min_community_size: int = 2,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Detect memory communities based on tag co-occurrence. Auto-generates summaries.

    Args:
        min_community_size: Min members per community
        project_path: Project root
    """
    if project_path is None and not _default_project_path:
        return _missing_project_path_error()

    from .communities import CommunityManager

    ctx = await get_project_context(project_path)
    cm = CommunityManager(ctx.db_manager)

    # Detect communities
    communities = await cm.detect_communities(
        project_path=project_path or _default_project_path,
        min_community_size=min_community_size
    )

    # Save to database
    result = await cm.save_communities(
        project_path or _default_project_path,
        communities
    )

    return {
        "status": "rebuilt",
        "communities_found": len(communities),
        **result
    }


@mcp.tool(version="3.0.0")
@with_request_id
async def list_communities(
    level: Optional[int] = None,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    List all memory communities with summaries.

    Args:
        level: Filter by hierarchy level
        project_path: Project root
    """
    if project_path is None and not _default_project_path:
        return _missing_project_path_error()

    from .communities import CommunityManager

    ctx = await get_project_context(project_path)
    cm = CommunityManager(ctx.db_manager)

    communities = await cm.get_communities(
        project_path or _default_project_path,
        level
    )

    return {
        "count": len(communities),
        "communities": communities
    }


@mcp.tool(version="3.0.0")
@with_request_id
async def get_community_details(
    community_id: int,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get full community details including all member memories.

    Args:
        community_id: Community to expand
        project_path: Project root
    """
    if project_path is None and not _default_project_path:
        return _missing_project_path_error()

    from .communities import CommunityManager

    ctx = await get_project_context(project_path)
    cm = CommunityManager(ctx.db_manager)

    return await cm.get_community_members(community_id)


@mcp.tool(version="3.0.0")
@with_request_id
async def recall_hierarchical(
    topic: str,
    include_members: bool = False,
    limit: int = 10,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    GraphRAG-style layered recall: community summaries first, then individual memories.

    Args:
        topic: What to search for
        include_members: Include full member content
        limit: Max results per layer
        project_path: Project root
    """
    if project_path is None and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    return await ctx.memory_manager.recall_hierarchical(
        topic=topic,
        project_path=project_path or _default_project_path,
        include_members=include_members,
        limit=limit
    )


# ============================================================================
# Entity Query Tools - Query memories by extracted entities
# ============================================================================
@mcp.tool(version="3.0.0")
@with_request_id
async def recall_by_entity(
    entity_name: str,
    entity_type: Optional[str] = None,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get all memories mentioning a specific entity (class/function/file).

    Args:
        entity_name: Entity to search for
        entity_type: Optional type filter
        project_path: Project root
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    # Import EntityManager locally
    try:
        from .entity_manager import EntityManager
    except ImportError:
        from daem0nmcp.entity_manager import EntityManager

    entity_manager = EntityManager(ctx.db_manager)
    return await entity_manager.get_memories_for_entity(
        entity_name=entity_name,
        project_path=ctx.project_path,
        entity_type=entity_type
    )


@mcp.tool(version="3.0.0")
@with_request_id
async def list_entities(
    entity_type: Optional[str] = None,
    limit: int = 20,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    List most frequently mentioned entities.

    Args:
        entity_type: Optional type filter
        limit: Max results
        project_path: Project root
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    # Import EntityManager locally
    try:
        from .entity_manager import EntityManager
    except ImportError:
        from daem0nmcp.entity_manager import EntityManager

    entity_manager = EntityManager(ctx.db_manager)
    entities = await entity_manager.get_popular_entities(
        project_path=ctx.project_path,
        entity_type=entity_type,
        limit=limit
    )

    return {
        "count": len(entities),
        "entities": entities
    }


@mcp.tool(version="3.0.0")
@with_request_id
async def backfill_entities(
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract entities from all existing memories. Safe to run multiple times.

    Args:
        project_path: Project root
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    # Import EntityManager locally
    try:
        from .entity_manager import EntityManager
    except ImportError:
        from daem0nmcp.entity_manager import EntityManager

    entity_manager = EntityManager(ctx.db_manager)

    # Query all non-archived memories
    async with ctx.db_manager.get_session() as session:
        result = await session.execute(
            select(Memory).where(
                or_(Memory.archived == False, Memory.archived.is_(None))
            )
        )
        memories = result.scalars().all()

    memories_processed = 0
    total_entities_extracted = 0

    for memory in memories:
        extraction_result = await entity_manager.process_memory(
            memory_id=memory.id,
            content=memory.content,
            project_path=ctx.project_path,
            rationale=memory.rationale
        )
        memories_processed += 1
        total_entities_extracted += extraction_result.get("entities_found", 0)

    return {
        "status": "completed",
        "memories_processed": memories_processed,
        "entities_extracted": total_entities_extracted,
        "message": f"Processed {memories_processed} memories, extracted {total_entities_extracted} entities"
    }


# ============================================================================
# CONTEXT TRIGGER TOOLS - Auto-recall based on patterns
# ============================================================================

@mcp.tool(version="3.0.0")
@with_request_id
async def add_context_trigger(
    trigger_type: str,
    pattern: str,
    recall_topic: str,
    recall_categories: Optional[List[str]] = None,
    priority: int = 0,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create auto-recall trigger. Types: file_pattern (glob), tag_match (regex), entity_match (regex).

    Args:
        trigger_type: file_pattern/tag_match/entity_match
        pattern: Glob or regex pattern
        recall_topic: Topic to recall when triggered
        recall_categories: Optional category filter
        priority: Higher = evaluated first
        project_path: Project root
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    project_path = project_path or _default_project_path

    try:
        from .context_triggers import ContextTriggerManager
    except ImportError:
        from daem0nmcp.context_triggers import ContextTriggerManager

    ctx = await get_project_context(project_path)
    tm = ContextTriggerManager(ctx.db_manager)

    return await tm.add_trigger(
        project_path=project_path,
        trigger_type=trigger_type,
        pattern=pattern,
        recall_topic=recall_topic,
        recall_categories=recall_categories,
        priority=priority
    )


@mcp.tool(version="3.0.0")
@with_request_id
async def list_context_triggers(
    active_only: bool = True,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    List all configured context triggers.

    Args:
        active_only: Only return active triggers
        project_path: Project root
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    project_path = project_path or _default_project_path

    try:
        from .context_triggers import ContextTriggerManager
    except ImportError:
        from daem0nmcp.context_triggers import ContextTriggerManager

    ctx = await get_project_context(project_path)
    tm = ContextTriggerManager(ctx.db_manager)

    triggers = await tm.list_triggers(
        project_path=project_path,
        active_only=active_only
    )

    return {
        "triggers": triggers,
        "count": len(triggers),
        "active_only": active_only
    }


@mcp.tool(version="3.0.0")
@with_request_id
async def remove_context_trigger(
    trigger_id: int,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Remove a context trigger.

    Args:
        trigger_id: ID of trigger to remove
        project_path: Project root
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    project_path = project_path or _default_project_path

    try:
        from .context_triggers import ContextTriggerManager
    except ImportError:
        from daem0nmcp.context_triggers import ContextTriggerManager

    ctx = await get_project_context(project_path)
    tm = ContextTriggerManager(ctx.db_manager)

    return await tm.remove_trigger(
        trigger_id=trigger_id,
        project_path=project_path
    )


@mcp.tool(version="3.0.0")
@with_request_id
async def check_context_triggers(
    file_path: Optional[str] = None,
    tags: Optional[List[str]] = None,
    entities: Optional[List[str]] = None,
    limit: int = 5,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Check which triggers match context and get auto-recalled memories.

    Args:
        file_path: Match against file_pattern triggers
        tags: Match against tag_match triggers
        entities: Match against entity_match triggers
        limit: Max memories per trigger
        project_path: Project root
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    project_path = project_path or _default_project_path

    try:
        from .context_triggers import ContextTriggerManager
    except ImportError:
        from daem0nmcp.context_triggers import ContextTriggerManager

    ctx = await get_project_context(project_path)
    tm = ContextTriggerManager(ctx.db_manager)

    return await tm.get_triggered_context(
        project_path=project_path,
        file_path=file_path,
        tags=tags,
        entities=entities,
        limit=limit
    )


# ============================================================================
# MCP RESOURCES - Automatic Context Injection
# ============================================================================
# These resources are automatically injected into the context window
# by MCP clients that support resource subscriptions.
# The _*_resource_impl functions are the testable implementations,
# while the @mcp.resource decorated functions are the MCP protocol wrappers.

async def _warnings_resource_impl(project_path: str, db_manager: DatabaseManager) -> str:
    """
    Implementation: Get active warnings for a project.

    Args:
        project_path: Path to the project root
        db_manager: Database manager to query

    Returns:
        Formatted markdown string of active warnings
    """
    try:
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Memory).where(
                    Memory.category == "warning",
                    or_(Memory.archived == False, Memory.archived.is_(None)),
                ).order_by(Memory.created_at.desc()).limit(10)
            )
            warnings = result.scalars().all()

        if not warnings:
            return "No active warnings for this project."

        lines = ["# Active Warnings", ""]
        for w in warnings:
            lines.append(f"- {w.content}")
            if w.rationale:
                lines.append(f"  Reason: {w.rationale}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error fetching warnings resource: {e}")
        return f"Error: {e}"


async def _failed_resource_impl(project_path: str, db_manager: DatabaseManager) -> str:
    """
    Implementation: Get failed approaches to avoid repeating.

    These are decisions where worked=False.

    Args:
        project_path: Path to the project root
        db_manager: Database manager to query

    Returns:
        Formatted markdown string of failed approaches
    """
    try:
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Memory).where(
                    Memory.worked == False,
                    or_(Memory.archived == False, Memory.archived.is_(None)),
                ).order_by(Memory.created_at.desc()).limit(10)
            )
            failed = result.scalars().all()

        if not failed:
            return "No failed approaches recorded."

        lines = ["# Failed Approaches (Do Not Repeat)", ""]
        for f in failed:
            lines.append(f"- {f.content}")
            if f.outcome:
                lines.append(f"  Outcome: {f.outcome}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error fetching failed resource: {e}")
        return f"Error: {e}"


async def _rules_resource_impl(project_path: str, db_manager: DatabaseManager) -> str:
    """
    Implementation: Get high-priority rules for a project.

    Returns top 5 rules by priority.

    Args:
        project_path: Path to the project root
        db_manager: Database manager to query

    Returns:
        Formatted markdown string of rules
    """
    try:
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Rule).where(Rule.enabled == True)
                .order_by(Rule.priority.desc())
                .limit(5)
            )
            rules = result.scalars().all()

        if not rules:
            return "No rules defined for this project."

        lines = ["# Project Rules", ""]
        for r in rules:
            lines.append(f"## {r.trigger}")
            if r.must_do:
                lines.append("Must do:")
                for item in r.must_do:
                    lines.append(f"  - {item}")
            if r.must_not:
                lines.append("Must NOT:")
                for item in r.must_not:
                    lines.append(f"  - {item}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error fetching rules resource: {e}")
        return f"Error: {e}"


async def _context_resource_impl(project_path: str, db_manager: DatabaseManager) -> str:
    """
    Implementation: Get combined project context.

    Combines warnings, failed approaches, and rules into one context document.

    Args:
        project_path: Path to the project root
        db_manager: Database manager to query

    Returns:
        Formatted markdown string with all context sections
    """
    try:
        warnings = await _warnings_resource_impl(project_path, db_manager)
        failed = await _failed_resource_impl(project_path, db_manager)
        rules = await _rules_resource_impl(project_path, db_manager)

        return f"""# Daem0n Project Context

{warnings}

---

{failed}

---

{rules}
"""

    except Exception as e:
        logger.error(f"Error fetching context resource: {e}")
        return f"Error: {e}"


@mcp.resource("daem0n://warnings/{project_path}")
async def warnings_resource(project_path: str) -> str:
    """
    Active warnings for this project.

    Automatically injected - no tool call needed.
    MCP clients subscribing to this resource get automatic updates.
    """
    try:
        ctx = await get_project_context(project_path)
        return await _warnings_resource_impl(project_path, ctx.db_manager)
    except Exception as e:
        logger.error(f"Error in warnings_resource: {e}")
        return f"Error: {e}"


@mcp.resource("daem0n://failed/{project_path}")
async def failed_resource(project_path: str) -> str:
    """
    Failed approaches to avoid repeating.

    These are decisions where worked=False.
    """
    try:
        ctx = await get_project_context(project_path)
        return await _failed_resource_impl(project_path, ctx.db_manager)
    except Exception as e:
        logger.error(f"Error in failed_resource: {e}")
        return f"Error: {e}"


@mcp.resource("daem0n://rules/{project_path}")
async def rules_resource(project_path: str) -> str:
    """
    High-priority rules for this project.

    Top 5 rules by priority.
    """
    try:
        ctx = await get_project_context(project_path)
        return await _rules_resource_impl(project_path, ctx.db_manager)
    except Exception as e:
        logger.error(f"Error in rules_resource: {e}")
        return f"Error: {e}"


@mcp.resource("daem0n://context/{project_path}")
async def context_resource(project_path: str) -> str:
    """
    Combined project context - warnings, failed approaches, and rules.

    This is the main resource for automatic context injection.
    Subscribe to this for complete project awareness.
    """
    try:
        ctx = await get_project_context(project_path)
        return await _context_resource_impl(project_path, ctx.db_manager)
    except Exception as e:
        logger.error(f"Error in context_resource: {e}")
        return f"Error: {e}"


async def get_triggered_context_resource(
    file_path: str,
    project_path: Optional[str] = None
) -> str:
    """
    MCP Resource implementation for dynamic context injection based on file path.

    When an AI tool accesses this resource with a file path,
    it returns auto-recalled memories based on matching triggers.

    Args:
        file_path: The file path to check triggers against
        project_path: Project root path (defaults to _default_project_path or cwd)

    Returns:
        JSON string with triggered context or error message
    """
    import json

    project_path = project_path or _default_project_path or os.getcwd()

    try:
        from .context_triggers import ContextTriggerManager
    except ImportError:
        from daem0nmcp.context_triggers import ContextTriggerManager

    try:
        ctx = await get_project_context(project_path)
        tm = ContextTriggerManager(ctx.db_manager)

        result = await tm.get_triggered_context(
            project_path=project_path,
            file_path=file_path
        )

        if not result["triggers"]:
            return json.dumps({
                "file": file_path,
                "triggers_matched": 0,
                "context": [],
                "message": "No triggers matched for this file"
            })

        # Format for easy reading
        output = {
            "file": file_path,
            "triggers_matched": len(result["triggers"]),
            "topics_recalled": result.get("topics_recalled", []),
            "context": []
        }

        # Include memory context for each topic
        for topic, recall_result in result.get("memories", {}).items():
            topic_context = {
                "topic": topic,
                "memories": []
            }

            # Extract memories from the recall result
            for category in ["decision", "pattern", "warning", "learning"]:
                category_memories = recall_result.get(category, [])
                for m in category_memories:
                    topic_context["memories"].append({
                        "category": category,
                        "content": m.get("content", ""),
                        "worked": m.get("worked")
                    })

            output["context"].append(topic_context)

        return json.dumps(output, indent=2)

    except Exception as e:
        logger.error(f"Error in get_triggered_context_resource: {e}")
        return json.dumps({
            "file": file_path,
            "error": str(e)
        })


@mcp.resource("daem0n://triggered/{file_path}")
async def triggered_context_resource(file_path: str) -> str:
    """
    MCP Resource for dynamic context injection based on file path.

    When an AI tool accesses this resource with a file path,
    it returns auto-recalled memories based on matching triggers.

    Usage: Access daem0n://triggered/src/auth/service.py
    Returns: Contextually relevant memories for that file
    """
    return await get_triggered_context_resource(file_path)


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
