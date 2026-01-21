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
- [ ] remember
- [ ] remember_batch
- [ ] recall
- [ ] recall_for_file
- [ ] search_memories
- [ ] find_related
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
- [ ] recall_hierarchical

### Entity Tracking
- [ ] recall_by_entity
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
