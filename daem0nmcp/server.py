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

15 Tools:
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
"""

import sys
import os
import re
import logging
import atexit
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

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
from sqlalchemy import select, desc

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("Daem0nMCP")

# Initialize core modules
storage_path = settings.get_storage_path()
db_manager = DatabaseManager(storage_path)
memory_manager = MemoryManager(db_manager)
rules_engine = RulesEngine(db_manager)

logger.info(f"Daem0nMCP Server initialized (storage: {storage_path})")


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
    file_path: Optional[str] = None
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
    await db_manager.init_db()
    return await memory_manager.remember(
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
    limit: int = 10
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
        limit: Max memories per category (default: 10)

    Returns:
        Categorized memories with relevance scores and failure warnings

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

    Uses SEMANTIC matching - "creating REST endpoint" will match rules about "adding API routes".

    Call this BEFORE taking any significant action to get:
    - Matching rules for this type of action
    - Combined must_do / must_not guidance
    - Relevant warnings
    - Questions to consider

    Args:
        action: Description of what you're about to do
        context: Optional context (files involved, etc.)

    Returns:
        Matching rules and combined guidance with severity indicator

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

    IMPORTANT: Failed decisions become implicit warnings that get BOOSTED
    in future recalls. This is how the system learns.

    Use this after implementing a decision to track:
    - What actually happened
    - Whether it worked out

    Args:
        memory_id: The ID of the memory (returned from 'remember')
        outcome: Description of what happened
        worked: Did it work? True/False

    Returns:
        Updated memory, with suggestions if it failed

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
# Helper: Git awareness
# ============================================================================
def _get_git_changes(since_date: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    """Get git changes since a given date."""
    try:
        # Check if we're in a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=5
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

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            git_info["recent_commits"] = result.stdout.strip().split("\n")

        # Get changed files (uncommitted)
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5
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
            timeout=5
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
        project_path: Optional project path (uses default if not specified)
        focus_areas: Optional list of topics to pre-fetch memories for

    Returns:
        Complete session briefing with actionable context

    Example:
        get_briefing()  # Basic briefing
        get_briefing(focus_areas=["authentication", "API"])  # With pre-loaded context
    """
    await db_manager.init_db()

    # Get statistics with learning insights
    stats = await memory_manager.get_statistics()

    # Get most recent memory timestamp for git awareness
    last_memory_date = None

    async with db_manager.get_session() as session:
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

    # Get git changes since last memory
    git_changes = _get_git_changes(last_memory_date)

    # Pre-fetch memories for focus areas if specified
    focus_memories = {}
    if focus_areas:
        for area in focus_areas[:3]:  # Limit to 3 areas
            memories = await memory_manager.recall(area, limit=5)
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
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Search across all memories with semantic similarity.

    Use this when you need to find specific memories by content.
    Uses TF-IDF matching for better results than exact text search.

    Args:
        query: Search text
        limit: Maximum results (default: 20)

    Returns:
        Matching memories ranked by relevance
    """
    await db_manager.init_db()
    return await memory_manager.search(query=query, limit=limit)


# ============================================================================
# Tool 8: LIST_RULES - See all configured rules
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
        List of rules with their guidance
    """
    await db_manager.init_db()
    return await rules_engine.list_rules(enabled_only=enabled_only, limit=limit)


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
# Tool 10: FIND_RELATED - Discover connected memories
# ============================================================================
@mcp.tool()
async def find_related(
    memory_id: int,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Find memories related to a specific memory.

    Useful for exploring connected decisions and understanding context.
    Uses semantic similarity to find related content.

    Args:
        memory_id: ID of the memory to find related content for
        limit: Maximum related memories to return (default: 5)

    Returns:
        List of related memories with similarity scores

    Example:
        # After seeing a decision about auth, find related patterns/warnings
        find_related(42)
    """
    await db_manager.init_db()
    return await memory_manager.find_related(memory_id=memory_id, limit=limit)


# ============================================================================
# Tool 11: CONTEXT_CHECK - Quick relevance check for current work
# ============================================================================
@mcp.tool()
async def context_check(
    description: str
) -> Dict[str, Any]:
    """
    Quick check for any relevant memories and rules for what you're about to do.

    Combines recall and check_rules in one call. Use this as a fast
    pre-flight check before making changes.

    Args:
        description: Brief description of what you're working on

    Returns:
        Combined results: relevant memories, matching rules, and any warnings

    Example:
        context_check("modifying the user authentication flow")
    """
    await db_manager.init_db()

    # Get relevant memories
    memories = await memory_manager.recall(description, limit=5)

    # Check rules
    rules = await rules_engine.check_rules(description)

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
    limit: int = 10
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

    Returns:
        Memories organized by category with warning indicators

    Example:
        recall_for_file("api/handlers.py")
        recall_for_file("src/components/Auth.tsx")
    """
    await db_manager.init_db()
    return await memory_manager.recall_for_file(file_path=file_path, limit=limit)


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
    types: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Scan the codebase for TODO, FIXME, HACK, XXX, and BUG comments.

    Tech debt finder - discovers and optionally tracks code comments that
    indicate incomplete work, known issues, or workarounds.

    Args:
        path: Directory to scan (defaults to current directory)
        auto_remember: If True, automatically create warning memories for each TODO
        types: Filter to specific types (e.g., ["FIXME", "HACK"]) - default: all

    Returns:
        List of found items grouped by type, with file locations

    Examples:
        scan_todos()  # Scan current directory
        scan_todos(types=["FIXME", "HACK"])  # Only critical items
        scan_todos(auto_remember=True)  # Scan and save as warnings
    """
    await db_manager.init_db()

    scan_path = path or os.getcwd()
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
    async with db_manager.get_session() as session:
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
                memory = await memory_manager.remember(
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
def _fetch_and_extract(url: str) -> Optional[str]:
    """Fetch URL and extract text content."""
    try:
        import httpx
        from bs4 import BeautifulSoup
    except ImportError:
        return None

    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

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
    chunk_size: int = 2000
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

    Returns:
        Summary of ingested content

    Examples:
        ingest_doc("https://stripe.com/docs/api/charges", "stripe-charges")
        ingest_doc("https://react.dev/reference/react/hooks", "react-hooks")
    """
    await db_manager.init_db()

    content = _fetch_and_extract(url)

    if content is None:
        return {
            "error": "Failed to fetch URL. Make sure httpx and beautifulsoup4 are installed: pip install daem0nmcp[web]",
            "url": url
        }

    if not content.strip():
        return {
            "error": "No text content found at URL",
            "url": url
        }

    # Chunk the content
    chunks = []
    words = content.split()
    current_chunk = []
    current_size = 0

    for word in words:
        word_len = len(word) + 1  # +1 for space
        if current_size + word_len > chunk_size and current_chunk:
            chunks.append(' '.join(current_chunk))
            current_chunk = [word]
            current_size = word_len
        else:
            current_chunk.append(word)
            current_size += word_len

    if current_chunk:
        chunks.append(' '.join(current_chunk))

    # Store each chunk as a learning
    memories_created = []
    for i, chunk in enumerate(chunks):
        memory = await memory_manager.remember(
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
        "message": f"Ingested {len(chunks)} chunks from {url}. Use recall('{topic}') to retrieve.",
        "memory_ids": [m.get('id') for m in memories_created if 'id' in m]
    }


# ============================================================================
# Tool 15: PROPOSE_REFACTOR - Generate refactor suggestions
# ============================================================================
@mcp.tool()
async def propose_refactor(
    file_path: str
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

    Returns:
        Combined context with memories, todos, and suggested actions

    Example:
        propose_refactor("src/auth/handlers.py")
    """
    await db_manager.init_db()

    result = {
        "file_path": file_path,
        "memories": {},
        "todos": [],
        "rules": {},
        "constraints": [],
        "opportunities": []
    }

    # Get file-specific memories
    file_memories = await memory_manager.recall_for_file(file_path)
    result["memories"] = file_memories

    # Scan for TODOs in this specific file
    if os.path.exists(file_path):
        file_todos = _scan_for_todos(os.path.dirname(file_path) or ".", max_files=1)
        result["todos"] = [t for t in file_todos if t['file'].endswith(os.path.basename(file_path))]

    # Check relevant rules
    filename = os.path.basename(file_path)
    rules = await rules_engine.check_rules(f"refactoring {filename}")
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
# Cleanup
# ============================================================================
def cleanup():
    """Cleanup on exit."""
    import asyncio
    try:
        # Try to get the running loop if one exists
        try:
            loop = asyncio.get_running_loop()
            # If there's a running loop, schedule cleanup
            loop.create_task(db_manager.close())
        except RuntimeError:
            # No running loop - try to create one for cleanup
            # Only do this if the engine was actually created
            if db_manager._engine is not None:
                asyncio.run(db_manager.close())
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
