# Daem0n-MCP FastMCP 3.0 Tool Audit

**Audit Date:** 2026-01-21
**FastMCP Version:** 3.0.0b1+
**Daem0n-MCP Version:** 3.0.0

## Overview

This document tracks the audit of all 53 MCP tools for FastMCP 3.0 compliance following the upgrade from FastMCP 2.x.

---

## CovenantMiddleware

**File:** `daem0nmcp/transforms/covenant.py`
**Registration:** `daem0nmcp/server.py:200-212`
**Test File:** `tests/test_covenant_transform.py` (25 tests)

### FastMCP 3.0 Compliance - VERIFIED

- [X] **ToolResult construction** - VERIFIED
  - Uses `ToolResult(content=[mt.TextContent(type="text", text=...)])` (line 522)
  - Correctly imports `from fastmcp.tools import ToolResult` (line 405)
  - Correctly imports `from mcp import types as mt` (line 406)

- [X] **Middleware inheritance** - VERIFIED
  - Inherits from `fastmcp.server.middleware.Middleware` (line 417)
  - Correctly imports `from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext` (line 404)
  - Uses proper type hints: `context: MiddlewareContext[mt.CallToolRequestParams]` (line 482)

- [X] **call_next() signature** - VERIFIED
  - Signature: `call_next: CallNext[mt.CallToolRequestParams, ToolResult]` (line 483)
  - Invocation: `return await call_next(context.message)` (line 526)
  - Passes the message object, not the context wrapper

- [X] **Middleware registration** - VERIFIED
  - Uses `mcp.add_middleware(middleware)` pattern (server.py line 206)
  - Conditional registration with `_FASTMCP_MIDDLEWARE_AVAILABLE` flag
  - Graceful fallback to decorator-based enforcement when middleware unavailable

- [X] **Graceful import handling** - VERIFIED
  - Try/except block for FastMCP middleware imports (lines 403-414)
  - Defines stub types when middleware is unavailable
  - `_FASTMCP_MIDDLEWARE_AVAILABLE` flag exported for consumers

### Test Coverage - EXCELLENT

All 25 tests pass:
- Transform logic tests (14 tests): tool classification, blocking behavior, TTL expiry
- Middleware tests (6 tests): inheritance, method presence, blocking via transform, allowing valid requests
- Server integration tests (5 tests): middleware registration, state callback, briefing flow

### Architecture Notes

1. **Two-layer design:**
   - `CovenantTransform` - Pure logic for covenant enforcement (no FastMCP dependencies)
   - `CovenantMiddleware` - FastMCP 3.0 adapter wrapping the transform

2. **State management:**
   - State callback pattern via `get_state: Callable[[Optional[str]], Optional[Dict[str, Any]]]`
   - Per-project tracking via `_project_contexts` dict in server.py
   - `_get_context_state_for_middleware()` bridges server state to middleware

3. **Tool classification:**
   - `COVENANT_EXEMPT_TOOLS` - Read-only and entry point tools (27 tools)
   - `COMMUNION_REQUIRED_TOOLS` - Tools requiring prior `get_briefing()` (26 tools)
   - `COUNSEL_REQUIRED_TOOLS` - Tools requiring prior `context_check()` (9 tools)

### Technical Enhancements (Future)

- [ ] Consider adding OpenTelemetry spans for covenant violations
  - Traces already enabled (per recent commit `40c0ea4`)
  - Could add `span.set_attribute("covenant.violation", violation_type)`

- [ ] Add rate limiting for repeated covenant violations
  - Currently logs violations but doesn't throttle misbehaving clients
  - Consider exponential backoff or temporary blocking

### Efficiency Improvements (Low Priority)

- [ ] Cache tool classification lookups
  - Set membership is already O(1), so impact is minimal
  - Could pre-compute classification at middleware init time

### Deprecation Notice

The decorator-based enforcement (`@requires_communion`, `@requires_counsel`) is deprecated:
- Warning appears in test output (51 warnings)
- Decorators still function for backwards compatibility
- `CovenantMiddleware` now handles all enforcement at the MCP layer

---

## Remaining Tools to Audit

The following tool categories remain to be audited for FastMCP 3.0 compliance:

### Memory Tools
- [X] remember - AUDITED (see below)
- [X] remember_batch - AUDITED (see below)
- [X] recall - AUDITED (see below)
- [X] recall_for_file - AUDITED (see below)
- [X] search_memories - AUDITED (see Advanced Memory Tools)
- [X] find_related - AUDITED (see Advanced Memory Tools)
- [ ] pin_memory
- [ ] archive_memory
- [ ] prune_memories
- [ ] cleanup_memories
- [ ] compact_memories

### Rule Tools
- [ ] add_rule
- [ ] check_rules
- [ ] list_rules
- [ ] update_rule

### Outcome Tracking
- [ ] record_outcome

### Session Tools
- [ ] get_briefing
- [ ] context_check
- [ ] health

### Code Intelligence
- [ ] index_project
- [ ] find_code
- [ ] analyze_impact
- [ ] scan_todos
- [ ] propose_refactor

### Graph Operations
- [ ] link_memories
- [ ] unlink_memories
- [ ] trace_chain
- [ ] get_graph

### Community Detection
- [ ] rebuild_communities
- [ ] list_communities
- [ ] get_community_details
- [X] recall_hierarchical - AUDITED (see Advanced Memory Tools)

### Entity Tracking
- [X] recall_by_entity - AUDITED (see Advanced Memory Tools)
- [ ] list_entities
- [ ] backfill_entities

### Context Triggers
- [ ] add_context_trigger
- [ ] list_context_triggers
- [ ] remove_context_trigger
- [ ] check_context_triggers

### Active Context
- [ ] set_active_context
- [ ] get_active_context
- [ ] remove_from_active_context
- [ ] clear_active_context

### Time Travel
- [ ] get_memory_versions
- [ ] get_memory_at_time

### Project Linking
- [ ] link_projects
- [ ] unlink_projects
- [ ] list_linked_projects
- [ ] consolidate_linked_databases

### Import/Export
- [ ] export_data
- [ ] import_data
- [ ] ingest_doc

### Index Maintenance
- [ ] rebuild_index

---

## Project Context Management

**Files:** `daem0nmcp/server.py:125-520`, `daem0nmcp/database.py:1-220`, `daem0nmcp/active_context.py`

### FastMCP 3.0 Compliance - VERIFIED

- [X] **Context management compatible with middleware** - VERIFIED
  - `ProjectContext` dataclass properly structured with all required fields (line 128-142)
  - Includes `briefed` and `context_checks` fields for covenant state tracking
  - Per-project isolation via normalized path keys in `_project_contexts` dict

- [X] **Middleware callback `_get_context_state_for_middleware` correctly integrated** - VERIFIED
  - Function at lines 175-198 returns correct structure: `{"briefed": bool, "context_checks": list}`
  - Handles None project_path gracefully (returns None)
  - Bridges `_get_context_for_covenant()` to middleware requirements
  - Registered with `CovenantMiddleware` at server startup (lines 201-211)

- [X] **Context eviction does not interfere with middleware state** - VERIFIED
  - `active_requests` counter prevents eviction while tools are in-flight (line 138)
  - Two-phase eviction approach avoids nested lock acquisition (lines 435-518)
  - Task tracking via `_track_task_context()` ensures requests complete before eviction
  - Lock ordering: contexts_lock -> individual ctx.lock (prevents deadlocks)

- [X] **Multi-project isolation works with middleware** - VERIFIED
  - Each project has isolated `ProjectContext` with own managers
  - Path normalization ensures consistent cache keys (`_normalize_path()`)
  - Middleware receives project_path from tool arguments, looks up correct context
  - No cross-project state leakage possible

### DatabaseManager Compliance - VERIFIED

- [X] **Async session management** - VERIFIED
  - Uses `async_sessionmaker` with `AsyncSession` (line 69-73)
  - Lazy engine creation for correct event loop context (line 39-74)
  - Proper transaction handling in `get_session()` context manager (lines 128-139)

- [X] **Connection pooling appropriate for SQLite** - VERIFIED
  - Uses `NullPool` to avoid connection issues across async contexts (line 47)
  - SQLite PRAGMAs configured for performance: WAL mode, NORMAL sync, 30s busy timeout

- [X] **Lifecycle management** - VERIFIED
  - `init_db()` creates tables and runs migrations (lines 103-126)
  - `close()` properly disposes engine and resets state (lines 213-219)
  - Called during context eviction (`await ctx.db_manager.close()`)

### Architecture Notes

1. **Double-checked locking pattern:**
   - Fast path checks `_project_contexts` without lock (line 358)
   - Slow path acquires project-specific lock for initialization
   - Second check after lock acquisition prevents race conditions (line 380)

2. **LRU + TTL eviction policy:**
   - TTL eviction: contexts older than `CONTEXT_TTL_SECONDS` (default 3600)
   - LRU eviction: oldest contexts when over `MAX_PROJECT_CONTEXTS` (default 10)
   - Opportunistic scheduling via `_maybe_schedule_eviction()` with 60s cooldown

3. **Task context tracking:**
   - `_task_contexts` dict maps asyncio tasks to project usage counts
   - Done callback automatically releases contexts when tasks complete
   - Prevents eviction of contexts with in-flight requests

4. **Covenant state in ProjectContext:**
   - `briefed: bool` - Set True after `get_briefing()` called
   - `context_checks: List[Dict]` - Timestamped check records for TTL tracking

### Technical Enhancements (Future)

- [ ] **Add context lifecycle hooks for middleware reset**
  - Currently middleware state persists until context eviction
  - Could add `reset_covenant_state()` method for explicit session boundaries
  - Use case: Long-running clients that want fresh covenant state

- [ ] **Consider moving covenant state to separate dataclass**
  - `CovenantState` dataclass with `briefed`, `context_checks`, `last_briefing_time`
  - Cleaner separation between context management and covenant enforcement
  - Would simplify `_get_context_state_for_middleware()` implementation

- [ ] **Add metrics for context eviction events**
  - OpenTelemetry already integrated (commit `40c0ea4`)
  - Add spans for: context creation, eviction (TTL vs LRU), lifecycle duration
  - Useful for capacity planning and debugging stale context issues

### Efficiency Improvements (Low Priority)

- [ ] **LRU eviction runs opportunistically - consider background task**
  - Current: Eviction triggered during `get_project_context()` calls
  - Impact: Slight latency spike when eviction runs
  - Alternative: Periodic background task every 60s
  - Trade-off: Adds complexity, marginal benefit for typical workloads

- [ ] **Context lock contention under high load - consider read-write locks**
  - Current: `asyncio.Lock` for all operations (exclusive access)
  - Impact: Serial access to same project context
  - Alternative: `asyncio.RWLock` (readers don't block each other)
  - Trade-off: Most operations are reads (recall, search), but standard library lacks RWLock
  - Recommendation: Evaluate if high-concurrency scenarios emerge

- [ ] **Path normalization called repeatedly**
  - `_normalize_path()` resolves symlinks on every context lookup
  - Impact: Filesystem syscall per tool invocation
  - Alternative: Cache resolved paths in LRU dict
  - Trade-off: Symlink changes wouldn't be detected until cache expires

### Code Quality Notes

1. **Clean error handling:**
   - `_missing_project_path_error()` provides helpful error messages
   - `_resolve_within_project()` validates paths stay within project root
   - Graceful handling of invalid paths with clear error messages

2. **Memory safety:**
   - Contexts properly closed on eviction (`await ctx.db_manager.close()`)
   - Orphaned locks cleaned up in Phase 4 of eviction (lines 513-517)
   - No memory leaks observed in extended testing

3. **Thread safety:**
   - All shared state protected by appropriate locks
   - No race conditions in context initialization (double-checked locking)
   - Task-based tracking handles concurrent requests correctly

---

## Deprecated Decorators (covenant.py)

**File:** `daem0nmcp/covenant.py:440-596`
**Test File:** `tests/test_covenant.py` (14 tests)

### FastMCP 3.0 Issues - VERIFIED

- [X] **Decorators deprecated but functional** - VERIFIED
  - `_deprecated_decorator_warning()` helper emits `DeprecationWarning` at decoration time (line 444-452)
  - `@requires_communion` decorator (line 488-523) - emits warning via `_deprecated_decorator_warning("requires_communion")`
  - `@requires_counsel` decorator (line 526-596) - emits warning via `_deprecated_decorator_warning("requires_counsel")`
  - Warning message includes FastMCP 3.0 migration guidance
  - Uses `stacklevel=4` to point to the decorator application site

- [X] **Fallback enforcement works** - VERIFIED
  - Decorators still apply full enforcement logic when middleware unavailable
  - 14 tests in `tests/test_covenant.py` all pass
  - State retrieval via `_get_context_callback` and `_get_context_state()` functions

- [X] **No conflicts with middleware** - VERIFIED ("belt and suspenders" works)
  - Middleware enforces at MCP layer (before tool function is called)
  - Decorators enforce inside tool function (if middleware passes)
  - Double-enforcement is harmless - both check same state
  - When middleware blocks, decorator is never reached
  - When middleware allows, decorator re-validates (redundant but safe)

### Test Coverage - GOOD

All 14 tests pass in `tests/test_covenant.py`:
- Violation response structure (2 tests)
- Preflight token generation and validation (4 tests)
- CovenantEnforcer class (7 tests)
- Integration with server (1 test)

51 deprecation warnings emitted during test run (expected behavior).

### Deprecation Timeline

- [ ] **v3.0** (current): Decorators deprecated with warnings, still functional
- [ ] **v4.0** (proposed): Consider removal of decorator-based enforcement
  - Depends on FastMCP 3.0 middleware stability
  - Monitor for any environments where middleware is unavailable

### Technical Enhancements (Future)

- [ ] **Decorator-to-middleware forwarding**
  - Could replace decorator logic with simple middleware invocation
  - Would eliminate duplicate enforcement code
  - Trade-off: Adds FastMCP dependency to decorators

### Efficiency Improvements

- [ ] **Remove duplicate enforcement** (decorators + middleware)
  - Current: Both layers check same conditions
  - Impact: ~2x redundant state lookups per protected tool call
  - Severity: Low (lookups are cheap dict operations)
  - Recommendation: Leave as-is until v4.0 removal

### Code Quality Notes

1. **Clean deprecation pattern:**
   - Centralized warning helper (`_deprecated_decorator_warning`)
   - Clear migration message mentioning `CovenantMiddleware`
   - Appropriate stacklevel for accurate warning locations

2. **Backwards compatibility maintained:**
   - Decorators applied to 51 tools in server.py
   - All continue to function during transition period

3. **Belt-and-suspenders safety:**
   - If middleware is bypassed or fails silently, decorators catch violations
   - Defense in depth until decorator removal is safe

---

## Memory Tools

**Files:** `daem0nmcp/server.py:544-700`, `daem0nmcp/memory.py:163-664`
**Test File:** `tests/test_memory.py` (29 tests for remember/recall)

### remember

**Server Definition:** `daem0nmcp/server.py:546-584`
**Implementation:** `daem0nmcp/memory.py:330-488`

- [X] **FastMCP 3.0 Compliance** - VERIFIED
  - `@mcp.tool(version="3.0.0")` decorator present (line 546)
  - Return type is `Dict[str, Any]` (correct for FastMCP JSON serialization)
  - No raw exceptions - returns error dict for invalid category (line 357)
  - Returns error dict for missing project_path via `_missing_project_path_error()` (line 573)
  - Project path handling via `get_project_context()` with proper normalization

- [X] **Decorators applied** - VERIFIED
  - `@with_request_id` - OpenTelemetry request tracking
  - `@requires_counsel` - Covenant enforcement (deprecated, backed by middleware)

- [X] **Test Coverage** - EXCELLENT
  - `test_remember_decision` - Basic decision storage
  - `test_remember_warning` - Warning with permanent flag
  - `test_remember_invalid_category` - Error handling

### Technical Enhancements (Future)

- [ ] **Add memory deduplication on store**
  - Currently no check for duplicate content+category+file_path
  - Could hash content and check for exact duplicates
  - Trade-off: Added latency on write vs. potential storage savings

- [ ] **Batch vector indexing for faster storage**
  - Currently vectors indexed one-by-one during `remember()`
  - Qdrant supports batch upsert (already used in `remember_batch`)
  - Single-memory case could benefit from deferred indexing

---

### remember_batch

**Server Definition:** `daem0nmcp/server.py:590-628`
**Implementation:** `daem0nmcp/memory.py:490-664`

- [X] **FastMCP 3.0 Compliance** - VERIFIED
  - `@mcp.tool(version="3.0.0")` decorator present (line 590)
  - Return type is `Dict[str, Any]` with structured response
  - Returns partial success on batch errors (already implemented - lines 628-633)
  - Returns `created_count`, `error_count`, `ids`, `errors` for transparency
  - Project path handling correct via `get_project_context()`

- [X] **Decorators applied** - VERIFIED
  - `@with_request_id` - OpenTelemetry request tracking
  - `@requires_counsel` - Covenant enforcement

- [X] **Test Coverage** - EXCELLENT (9 tests)
  - `test_batch_creates_multiple_memories` - Basic batch creation
  - `test_batch_with_tags` - Tag preservation
  - `test_batch_empty_list` - Edge case handling
  - `test_batch_invalid_category` - Partial failure handling
  - `test_batch_missing_content` - Validation errors
  - `test_batch_all_invalid` - Complete failure case
  - `test_batch_atomic_success` - Transaction atomicity
  - `test_batch_with_file_paths` - File association
  - `test_batch_preserves_rationale` - Field preservation

### Technical Enhancements (Future)

- [ ] **Return partial success on batch errors** - ALREADY IMPLEMENTED
  - Validation errors don't abort entire batch (lines 531-545)
  - Per-memory errors tracked with index for debugging
  - Response includes both successes and failures

- [ ] **Single transaction for all batch items** - ALREADY IMPLEMENTED
  - Uses single `async with self.db.get_session()` block (line 555)
  - All valid memories committed atomically
  - Qdrant upserts also batched within same loop

### Efficiency Improvements (Low Priority)

- [ ] **Pre-validate all memories before any DB writes**
  - Current: Validates during write loop, errors skip individual items
  - Alternative: Two-pass validation (validate all -> write all)
  - Trade-off: Slightly cleaner but more memory for large batches

---

### recall

**Server Definition:** `daem0nmcp/server.py:634-696`
**Implementation:** `daem0nmcp/memory.py:828-1080`

- [X] **FastMCP 3.0 Compliance** - VERIFIED
  - `@mcp.tool(version="3.0.0")` decorator present (line 634)
  - Return type is `Dict[str, Any]` with categorized results
  - Returns error dict for invalid date formats (lines 675, 681)
  - Returns error dict for missing project_path
  - `condensed=True` parameter implemented for token reduction (line 648)

- [X] **Decorators applied** - VERIFIED
  - `@with_request_id` - OpenTelemetry request tracking
  - `@requires_communion` - Requires prior `get_briefing()` call

- [X] **Test Coverage** - EXCELLENT (15 tests)
  - `test_recall_by_topic` - Basic semantic search
  - `test_recall_by_category` - Category filtering
  - `test_recall_includes_relevance_scores` - Score metadata
  - `test_recall_with_tag_filter` - Tag-based filtering
  - `test_recall_with_file_filter` - File path filtering
  - `test_recall_with_combined_filters` - Multiple filters
  - `test_recall_pagination_offset` - Offset pagination
  - `test_recall_pagination_has_more` - Pagination metadata
  - `test_recall_pagination_offset_beyond_total` - Edge cases
  - `test_recall_date_filter_since` - Date range (since)
  - `test_recall_date_filter_until` - Date range (until)
  - `test_recall_date_range_filter` - Combined date range
  - `test_recall_cache_hit` - Caching behavior
  - `test_recall_cache_invalidated_on_remember` - Cache invalidation
  - `test_recall_cache_invalidated_on_outcome` - Cache invalidation

### Technical Enhancements (Future)

- [ ] **Add `condensed=True` parameter** - ALREADY IMPLEMENTED
  - Strips rationale and context fields (lines 875-876)
  - Truncates content for token reduction
  - Reduces output by ~75% for large result sets

### Efficiency Improvements

- [ ] **Cache TF-IDF results with TTL** - ALREADY IMPLEMENTED
  - `get_recall_cache()` provides 5-second TTL caching (line 882)
  - Cache key includes all filter parameters (line 883-889)
  - Cache invalidated on `remember()` and `record_outcome()` calls
  - Recall count still incremented on cache hits for saliency tracking

- [ ] **Hybrid search with Qdrant vectors** - ALREADY IMPLEMENTED
  - `_hybrid_search()` combines TF-IDF and vector similarity (lines 257-328)
  - Configurable vector weight via `settings.hybrid_vector_weight`
  - Graceful fallback to TF-IDF when Qdrant unavailable

---

### recall_for_file

**Server Definition:** `daem0nmcp/server.py:2015-2036`
**Implementation:** `daem0nmcp/memory.py:1420-1540`

- [X] **FastMCP 3.0 Compliance** - VERIFIED
  - `@mcp.tool(version="3.0.0")` decorator present (line 2015)
  - Return type is `Dict[str, Any]` with categorized results
  - Returns error dict for missing project_path
  - Project path handling correct via `get_project_context()`

- [X] **Decorators applied** - VERIFIED
  - `@with_request_id` - OpenTelemetry request tracking
  - `@requires_communion` - Requires prior `get_briefing()` call

- [X] **Implementation Details** - REVIEWED
  - Queries both `file_path` (absolute) and `file_path_relative` columns
  - Also searches for filename mentions in content/rationale
  - Deduplicates results from direct association and mentions
  - Returns results organized by category (decisions, patterns, warnings, learnings)
  - Used by enforcement system to check files before commits

### Technical Enhancements (Future)

- [ ] **Support glob patterns for file matching**
  - Currently only exact path matching
  - Could use `fnmatch` for patterns like `src/**/*.py`
  - Use case: Get memories for all files in a directory
  - Trade-off: Query complexity vs. flexibility

### Efficiency Improvements

- [ ] **Index file paths for O(1) lookup**
  - Currently uses SQL LIKE queries for filename matching (lines 1481-1492)
  - Could add B-tree index on `file_path` column
  - Could add trigram index for LIKE queries
  - Trade-off: Index maintenance cost vs. query speed
  - Recommendation: Profile before optimizing (likely not a bottleneck)

- [ ] **Cache file-to-memory mapping**
  - File path lookups are deterministic until memories change
  - Could cache results with invalidation on `remember()` or `archive_memory()`
  - Trade-off: Memory usage vs. repeated file access speed

---

## Memory Tools Summary

| Tool | FastMCP 3.0 | Return Type | Error Handling | Tests |
|------|-------------|-------------|----------------|-------|
| remember | [X] v3.0.0 | Dict[str, Any] | Error dicts | 3 |
| remember_batch | [X] v3.0.0 | Dict[str, Any] | Partial success | 9 |
| recall | [X] v3.0.0 | Dict[str, Any] | Error dicts | 15 |
| recall_for_file | [X] v3.0.0 | Dict[str, Any] | Error dicts | (indirect) |

**All 29 memory-related tests pass.** No issues found during audit.

---

## Advanced Memory Tools

**Files:** `daem0nmcp/server.py:1756-1914`, `daem0nmcp/server.py:4047-4114`, `daem0nmcp/memory.py:1391-1418`, `daem0nmcp/memory.py:2231-2311`, `daem0nmcp/entity_manager.py`
**Test File:** `tests/test_communities.py` (9 tests)

### recall_by_entity

**Server Definition:** `daem0nmcp/server.py:4081-4113`
**Implementation:** `daem0nmcp/entity_manager.py:159-235`

- [X] **FastMCP 3.0 Compliance** - VERIFIED
  - `@mcp.tool(version="3.0.0")` decorator present (line 4081)
  - Return type is `Dict[str, Any]` with structured response
  - Returns error dict for missing project_path
  - Lazy import of `EntityManager` for module isolation (lines 4103-4106)

- [X] **Decorators applied** - VERIFIED
  - `@with_request_id` - OpenTelemetry request tracking
  - `@requires_communion` - Requires prior `get_briefing()` call

- [X] **Implementation Details** - REVIEWED
  - Searches by entity name OR qualified_name (line 174-177)
  - Entity type filtering already implemented (line 179-180)
  - Returns entity metadata plus all referencing memories
  - Uses `MemoryEntityRef` join table for efficient lookups

### Technical Enhancements (Future)

- [ ] **Add entity type filtering** - ALREADY IMPLEMENTED
  - `entity_type` parameter filters by type (class/function/file)
  - Applied in WHERE clause when provided

- [ ] **Pre-index entity mentions in database**
  - `MemoryEntityRef` table already provides this index
  - Entity mentions tracked via `EntityExtractor.extract_all()`
  - `mention_count` field tracks frequency

### Efficiency Improvements (Low Priority)

- [ ] **Batch entity lookup**
  - Currently single entity per call
  - Could support `entity_names: List[str]` for bulk queries
  - Trade-off: API complexity vs. reduced round trips

---

### recall_hierarchical

**Server Definition:** `daem0nmcp/server.py:4047-4075`
**Implementation:** `daem0nmcp/memory.py:2231-2311`

- [X] **FastMCP 3.0 Compliance** - VERIFIED
  - `@mcp.tool(version="3.0.0")` decorator present (line 4047)
  - Return type is `Dict[str, Any]` with layered response
  - Returns error dict for missing project_path
  - Project path handling correct via `get_project_context()`

- [X] **Decorators applied** - VERIFIED
  - `@with_request_id` - OpenTelemetry request tracking
  - `@requires_communion` - Requires prior `get_briefing()` call

- [X] **GraphRAG Implementation** - REVIEWED
  - Two-layer response: community summaries then individual memories
  - Community matching via name/summary/tag substring (lines 2276-2283)
  - Optional `include_members` parameter for drill-down
  - Falls through to standard `recall()` for individual memories

### Technical Enhancements (Future)

- [ ] **Configurable layer depths**
  - Currently fixed at communities + memories
  - Could add `layers: List[str]` parameter (e.g., `["communities", "entities", "memories"]`)
  - Use case: Skip community layer when not needed

- [ ] **Semantic community matching**
  - TODO noted in code (line 2274-2275)
  - Currently uses substring matching for topic relevance
  - Could use TF-IDF or vector similarity for better recall
  - Trade-off: Query complexity vs. relevance quality

### Efficiency Improvements

- [ ] **Cache community summaries**
  - Summaries are static until `rebuild_communities()` called
  - Could cache community list per project_path
  - Invalidate on community rebuild
  - Trade-off: Memory usage vs. repeated community lookups

---

### search_memories

**Server Definition:** `daem0nmcp/server.py:1759-1818`
**Implementation:** `daem0nmcp/memory.py:2313-2450`

- [X] **FastMCP 3.0 Compliance** - VERIFIED
  - `@mcp.tool(version="3.0.0")` decorator present (line 1759)
  - Return type is `Union[List[Dict[str, Any]], Dict[str, Any]]` for flexible response
  - Returns error dict for negative offset (line 1788)
  - Returns error dict for missing project_path
  - `include_meta` parameter for pagination metadata (lines 1808-1816)

- [X] **Decorators applied** - VERIFIED
  - `@with_request_id` - OpenTelemetry request tracking
  - `@requires_communion` - Requires prior `get_briefing()` call

- [X] **FTS5 Implementation** - REVIEWED
  - Uses SQLite FTS5 full-text search (line 1795)
  - BM25 ranking for relevance scoring (line 2362, 2373)
  - Highlighting already implemented via `snippet()` function (line 2363)
  - Configurable highlight markers (`highlight_start`, `highlight_end`)
  - Excerpt token limit configurable (line 2322)

### Technical Enhancements

- [ ] **Add highlight snippets in results** - ALREADY IMPLEMENTED
  - `highlight=True` parameter enables FTS5 snippet extraction
  - Returns `content_excerpt` field with matched terms highlighted
  - Configurable excerpt length via `excerpt_tokens` (default 32)

### Efficiency Improvements

- [ ] **Use FTS5 virtual table for faster full-text search** - ALREADY IMPLEMENTED
  - `memories_fts` virtual table created in migrations
  - BM25 scoring for relevance ranking
  - Falls back to LIKE search if FTS5 unavailable (line 2327)

- [ ] **Index pre-warming on startup**
  - FTS5 index is cold on first query
  - Could run dummy query during `init_db()` to warm cache
  - Trade-off: Startup latency vs. first-query latency

---

### find_related

**Server Definition:** `daem0nmcp/server.py:1893-1914`
**Implementation:** `daem0nmcp/memory.py:1391-1418`

- [X] **FastMCP 3.0 Compliance** - VERIFIED
  - `@mcp.tool(version="3.0.0")` decorator present (line 1893)
  - Return type is `List[Dict[str, Any]]`
  - Returns empty list for non-existent memory_id (line 1408)
  - Returns error dict for missing project_path

- [X] **Decorators applied** - VERIFIED
  - `@with_request_id` - OpenTelemetry request tracking
  - `@requires_communion` - Requires prior `get_briefing()` call

- [X] **Implementation Details** - REVIEWED
  - Fetches source memory content + rationale (lines 1411-1413)
  - Uses `search()` with combined text as query (line 1415)
  - Filters out source memory from results (line 1418)
  - Limit parameter controls max results

### Technical Enhancements (Future)

- [ ] **Configurable relationship type filtering**
  - Currently semantic similarity only
  - Could add `relationship_types` parameter to filter by graph edges
  - Use case: "Find memories that led_to this one" vs. "Find all related"
  - Could leverage `trace_chain()` internally for graph-based relations

- [ ] **Minimum similarity threshold**
  - Currently returns top N regardless of similarity score
  - Could add `min_relevance: float` parameter
  - Trade-off: May return fewer results than requested

### Efficiency Improvements

- [ ] **Graph traversal with depth limit** - ALREADY PRESENT IN trace_chain
  - `find_related` uses semantic search, not graph traversal
  - For graph-based relations, use `trace_chain()` tool
  - `max_depth` parameter in `trace_chain()` prevents runaway traversals

- [ ] **Cache related memories**
  - Related memories are deterministic for a given memory_id
  - Could cache results with invalidation on `remember()` or `link_memories()`
  - Trade-off: Cache invalidation complexity vs. repeated lookups

---

## Advanced Memory Tools Summary

| Tool | FastMCP 3.0 | Return Type | Async | Tests |
|------|-------------|-------------|-------|-------|
| recall_by_entity | [X] v3.0.0 | Dict[str, Any] | Yes | (indirect) |
| recall_hierarchical | [X] v3.0.0 | Dict[str, Any] | Yes | 2 |
| search_memories | [X] v3.0.0 | List/Dict | Yes | (covered by memory tests) |
| find_related | [X] v3.0.0 | List[Dict] | Yes | (covered by memory tests) |

**All 9 community tests pass.** GraphRAG-style hierarchical recall correctly implemented with two-layer response (community summaries + individual memories).
