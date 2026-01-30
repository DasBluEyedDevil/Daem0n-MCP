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
15. MCP Apps UI resources for visual interfaces (v5.0)

60 Tools:
- remember: Store a decision, pattern, warning, or learning (with file association)
- recall: Retrieve relevant memories for a topic (semantic search)
- verify_facts: Verify factual claims in text against stored knowledge
- compress_context: Compress context using LLMLingua-2 for token reduction
- execute_python: Execute Python code in isolated sandbox
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

import atexit
import logging

# ============================================================================
# Step 1: Import shared MCP instance (must be first)
# ============================================================================
try:
    from .mcp_instance import mcp  # noqa: F401
    from .config import settings
    from .database import DatabaseManager
    from .memory import MemoryManager
    from .rules import RulesEngine
    from .models import Memory, Rule, CodeEntity  # noqa: F401
    from . import __version__  # noqa: F401
    from . import vectors  # noqa: F401
    from .logging_config import StructuredFormatter, with_request_id, request_id_var, set_release_callback  # noqa: F401
    from .covenant import set_context_callback  # noqa: F401
    from .transforms.covenant import CovenantMiddleware, _FASTMCP_MIDDLEWARE_AVAILABLE
    from .agency import (  # noqa: F401
        SandboxExecutor,
        CapabilityScope,
        CapabilityManager,
        check_capability,
    )
    from .rwlock import RWLock  # noqa: F401
    from .ui.resources import register_ui_resources
except ImportError:
    from daem0nmcp.mcp_instance import mcp  # noqa: F401
    from daem0nmcp.config import settings
    from daem0nmcp.database import DatabaseManager
    from daem0nmcp.memory import MemoryManager
    from daem0nmcp.rules import RulesEngine
    from daem0nmcp.models import Memory, Rule, CodeEntity  # noqa: F401
    from daem0nmcp import __version__  # noqa: F401
    from daem0nmcp import vectors  # noqa: F401
    from daem0nmcp.logging_config import StructuredFormatter, with_request_id, request_id_var, set_release_callback  # noqa: F401
    from daem0nmcp.covenant import set_context_callback  # noqa: F401
    from daem0nmcp.transforms.covenant import CovenantMiddleware, _FASTMCP_MIDDLEWARE_AVAILABLE
    from daem0nmcp.agency import (  # noqa: F401
        SandboxExecutor,
        CapabilityScope,
        CapabilityManager,
        check_capability,
    )
    from daem0nmcp.rwlock import RWLock  # noqa: F401
    from daem0nmcp.ui.resources import register_ui_resources

# ============================================================================
# Step 2: Import context_manager symbols (re-exported for backward compat)
# ============================================================================
try:
    from .context_manager import (  # noqa: F401
        ProjectContext, get_project_context, evict_stale_contexts,
        cleanup_all_contexts, _project_contexts, _context_locks,
        _normalize_path, _default_project_path, MAX_PROJECT_CONTEXTS,
        CONTEXT_TTL_SECONDS, _missing_project_path_error,
        _check_covenant_communion, _check_covenant_counsel,
        _get_context_for_covenant, _get_context_state_for_middleware,
        _resolve_within_project, _track_task_context,
        _release_current_task_contexts, _contexts_lock,
        _task_contexts, _task_contexts_lock,
        _EVICTION_INTERVAL_SECONDS, _maybe_schedule_eviction,
        _get_storage_for_project,
    )
except ImportError:
    from daem0nmcp.context_manager import (  # noqa: F401
        ProjectContext, get_project_context, evict_stale_contexts,
        cleanup_all_contexts, _project_contexts, _context_locks,
        _normalize_path, _default_project_path, MAX_PROJECT_CONTEXTS,
        CONTEXT_TTL_SECONDS, _missing_project_path_error,
        _check_covenant_communion, _check_covenant_counsel,
        _get_context_for_covenant, _get_context_state_for_middleware,
        _resolve_within_project, _track_task_context,
        _release_current_task_contexts, _contexts_lock,
        _task_contexts, _task_contexts_lock,
        _EVICTION_INTERVAL_SECONDS, _maybe_schedule_eviction,
        _get_storage_for_project,
    )

from sqlalchemy import select, delete, or_, func  # noqa: F401
from dataclasses import dataclass, field  # noqa: F401

# Logging is configured by mcp_instance.py (imported above)
logger = logging.getLogger(__name__)

# Register UI resources for MCP Apps (v5.0)
register_ui_resources(mcp)

# ============================================================================
# Step 3: Import tool modules (triggers @mcp.tool / @mcp.resource registration)
# ============================================================================
try:
    from .tools import memory as _memory_tools  # noqa: F401
    from .tools import rules as _rules_tools  # noqa: F401
    from .tools import briefing as _briefing_tools  # noqa: F401
    from .tools import verification as _verification_tools  # noqa: F401
    from .tools import code_tools as _code_tools  # noqa: F401
    from .tools import maintenance as _maintenance_tools  # noqa: F401
    from .tools import graph_tools as _graph_tools  # noqa: F401
    from .tools import context_tools as _context_tools  # noqa: F401
    from .tools import federation as _federation_tools  # noqa: F401
    from .tools import agency_tools as _agency_tools  # noqa: F401
    from .tools import temporal as _temporal_tools  # noqa: F401
    from .tools import entity_tools as _entity_tools  # noqa: F401
    from .tools import resources as _resources  # noqa: F401
    from .tools import workflows as _workflows  # noqa: F401
except ImportError:
    from daem0nmcp.tools import memory as _memory_tools  # noqa: F401
    from daem0nmcp.tools import rules as _rules_tools  # noqa: F401
    from daem0nmcp.tools import briefing as _briefing_tools  # noqa: F401
    from daem0nmcp.tools import verification as _verification_tools  # noqa: F401
    from daem0nmcp.tools import code_tools as _code_tools  # noqa: F401
    from daem0nmcp.tools import maintenance as _maintenance_tools  # noqa: F401
    from daem0nmcp.tools import graph_tools as _graph_tools  # noqa: F401
    from daem0nmcp.tools import context_tools as _context_tools  # noqa: F401
    from daem0nmcp.tools import federation as _federation_tools  # noqa: F401
    from daem0nmcp.tools import agency_tools as _agency_tools  # noqa: F401
    from daem0nmcp.tools import temporal as _temporal_tools  # noqa: F401
    from daem0nmcp.tools import entity_tools as _entity_tools  # noqa: F401
    from daem0nmcp.tools import resources as _resources  # noqa: F401
    from daem0nmcp.tools import workflows as _workflows  # noqa: F401

# ============================================================================
# Step 4: Re-export ALL public symbols (backward compatibility)
# Tests and workflow modules import these from daem0nmcp.server
# ============================================================================

# --- Memory tools (17) ---
from .tools.memory import (  # noqa: F401
    remember, remember_batch, recall, recall_visual,
    record_outcome, recall_for_file, recall_by_entity,
    recall_hierarchical, search_memories, find_related,
    get_related_memories, get_memory_versions, get_memory_at_time,
    compact_memories, cleanup_memories, archive_memory, pin_memory,
)

# --- Rules tools (4) ---
from .tools.rules import (  # noqa: F401
    add_rule, check_rules, list_rules, update_rule,
)

# --- Briefing tools (7+) and helpers ---
from .tools.briefing import (  # noqa: F401
    get_briefing, get_briefing_visual, get_covenant_status,
    get_covenant_status_visual, context_check, check_for_updates,
    health,
    # Private helpers needed by tests
    _extract_project_identity, _extract_architecture,
    _extract_conventions, _extract_entry_points,
    _scan_todos_for_bootstrap, _extract_project_instructions,
    _get_git_changes, _bootstrap_project_context,
    _prefetch_focus_areas,
)

# --- Verification tools (1) ---
from .tools.verification import verify_facts  # noqa: F401

# --- Code tools (5+) and helpers ---
from .tools.code_tools import (  # noqa: F401
    scan_todos, index_project, find_code, analyze_impact,
    propose_refactor,
    # Private helpers needed by tests
    _scan_for_todos, TODO_PATTERN,
)

# --- Maintenance tools (4) ---
from .tools.maintenance import (  # noqa: F401
    rebuild_index, export_data, import_data, prune_memories,
)

# --- Graph tools (10) ---
from .tools.graph_tools import (  # noqa: F401
    link_memories, unlink_memories, trace_chain, get_graph,
    get_graph_visual, get_graph_stats,
    rebuild_communities, list_communities, list_communities_visual,
    get_community_details,
)

# --- Context tools (8) ---
from .tools.context_tools import (  # noqa: F401
    set_active_context, get_active_context,
    remove_from_active_context, clear_active_context,
    add_context_trigger, list_context_triggers,
    remove_context_trigger, check_context_triggers,
)

# --- Federation tools (4) ---
from .tools.federation import (  # noqa: F401
    link_projects, unlink_projects, list_linked_projects,
    consolidate_linked_databases,
)

# --- Agency tools (3+) and helpers ---
from .tools.agency_tools import (  # noqa: F401
    compress_context, execute_python, ingest_doc,
    # Private helpers/globals needed by tests
    _sandbox_executor, _capability_manager,
    _fetch_and_extract, _validate_url,
    _chunk_markdown_content, _resolve_public_ips,
    MAX_CONTENT_SIZE, MAX_CHUNKS, INGEST_TIMEOUT, ALLOWED_URL_SCHEMES,
)

# --- Temporal tools (2) ---
from .tools.temporal import (  # noqa: F401
    trace_causal_path, trace_evolution,
)

# --- Entity tools (2) ---
from .tools.entity_tools import (  # noqa: F401
    list_entities, backfill_entities,
)

# --- Resource implementations (5 resources + impls) ---
from .tools.resources import (  # noqa: F401
    _warnings_resource_impl, _failed_resource_impl,
    _rules_resource_impl, _context_resource_impl,
    get_triggered_context_resource,
    warnings_resource, failed_resource,
    rules_resource, context_resource,
    triggered_context_resource,
)

# --- Workflow tools (8) ---
from .tools.workflows import (  # noqa: F401
    commune, consult, inscribe, reflect,
    understand, govern, explore, maintain,
)

# Import workflow error types
try:
    from .workflows.errors import WorkflowError  # noqa: F401
except ImportError:
    from daem0nmcp.workflows.errors import WorkflowError  # noqa: F401


# ============================================================================
# Step 5: Composition root setup
# ============================================================================

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

# Legacy global references for backward compatibility
# These point to the default project context
storage_path = settings.get_storage_path()
db_manager = DatabaseManager(storage_path)
memory_manager = MemoryManager(db_manager)
rules_engine = RulesEngine(db_manager)

logger.info(f"Daem0nMCP Server initialized (default storage: {storage_path})")


# ============================================================================
# Step 6: Cleanup & lifecycle
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
# Step 7: Entry point
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
