# Architecture

**Analysis Date:** 2026-01-22

## Pattern Overview

**Overall:** Layered multi-tenant MCP server with hybrid semantic search, covenant-enforced workflow, and pluggable components.

**Key Characteristics:**
- Multi-project isolation: Each project gets isolated `ProjectContext` with separate database, memory, and rules managers
- Async-first design: All I/O operations use SQLAlchemy async with aiosqlite
- Hybrid retrieval: BM25 keyword search + vector embeddings fused via Reciprocal Rank Fusion
- Covenant enforcement: Sacred Covenant protocol enforced via FastMCP 3.0 middleware + decorators (belt and suspenders)
- Incremental indexing: Memories indexed via TF-IDF, BM25, and optional vector embeddings with change detection

## Layers

**API Layer:**
- Purpose: Exposes 50+ MCP tools via FastMCP 3.0 server
- Location: `daem0nmcp/server.py` (main tool definitions)
- Contains: Tool handlers, request routing, project context management
- Depends on: All manager layers, covenant enforcement
- Used by: Claude Code, other MCP clients

**Memory/Recall Layer:**
- Purpose: Semantic storage and retrieval of memories (decisions, patterns, warnings, learnings)
- Location: `daem0nmcp/memory.py`
- Contains: Memory CRUD, outcome tracking, time-based decay, conflict detection
- Depends on: Database, similarity engines (TF-IDF, BM25, vectors), caching
- Used by: API layer, rules engine, briefing builder

**Rules Engine:**
- Purpose: Decision tree enforcement for consistent AI behavior
- Location: `daem0nmcp/rules.py`
- Contains: Rule matching, semantic trigger matching via TF-IDF
- Depends on: Database, similarity engine
- Used by: API layer, context_check tool

**Similarity & Search Layer:**
- Purpose: Multiple retrieval algorithms to surface relevant memories
- Location: `daem0nmcp/similarity.py`, `daem0nmcp/bm25_index.py`, `daem0nmcp/vectors.py`, `daem0nmcp/fusion.py`
- Contains:
  - `TFIDFIndex`: Traditional term frequency-inverse document frequency vectorization
  - `BM25Index`: Okapi BM25 for better keyword saturation and document length normalization
  - `VectorIndex`: sentence-transformers embeddings with Qdrant backend
  - `RRFHybridSearch`: Reciprocal Rank Fusion combining BM25 + vector results
- Depends on: Database, external libraries (rank-bm25, sentence-transformers, qdrant-client)
- Used by: Memory layer for all recall operations

**Specialized Components:**
- `recall_planner.py`: TiMem-style complexity classification (simple/medium/complex queries) to reduce context
- `surprise.py`: Titans-inspired novelty detection scoring memories 0.0-1.0
- `prompt_templates.py`: AutoPDL-inspired modular prompt system with sections and A/B testing
- `tool_search.py`: Dynamic MCP tool discovery to prevent context bloat
- `communities.py`: GraphRAG-style community detection via tag co-occurrence for hierarchical recall
- `active_context.py`: MemGPT-style always-hot memory layer (max 10 items)
- `context_triggers.py`: Auto-recall patterns (file patterns, tag matching, entity matching)
- `code_indexer.py`: Tree-sitter AST parsing for multi-language code understanding
- `entity_manager.py`: Automatic entity extraction and entity-based recall

**Enforcement Layer:**
- Purpose: Sacred Covenant enforcement via middleware and decorators
- Location: `daem0nmcp/covenant.py`, `daem0nmcp/transforms/covenant.py`
- Contains:
  - Communion requirement (must call `get_briefing()` first)
  - Counsel requirement (must call `context_check()` before mutations)
  - Preflight tokens (cryptographic proof of consultation, TTL=5 minutes)
  - Tool classification (exempt, communion-only, counsel-required)
- Depends on: FastMCP server, context state tracking
- Used by: FastMCP middleware for all tool calls

**Database Layer:**
- Purpose: SQLite-backed async persistence
- Location: `daem0nmcp/database.py`, `daem0nmcp/models.py`
- Contains: DatabaseManager (connection pooling, PRAGMA tuning), 10+ SQLAlchemy ORM models
- Depends on: SQLAlchemy async, aiosqlite
- Used by: All manager layers

**CLI Layer:**
- Purpose: Command-line interface for pre-commit hooks, migrations, manual operations
- Location: `daem0nmcp/cli.py`
- Contains: check, briefing, scan-todos, migrate, pre-commit, status, record-outcome, install-hooks, watch, index, remember commands
- Depends on: All manager layers, git operations
- Used by: Git hooks, external scripts, developer operations

## Data Flow

**Memory Creation (remember → store):**

1. User calls `remember(category, content, rationale, file_path)`
2. API layer calls `_check_covenant_communion()` to verify `get_briefing()` already called
3. Memory is normalized: file paths canonicalized, keywords extracted
4. Conflict detection runs via `detect_conflict()` against recent memories
5. Vector embeddings generated via `vectors.encode()` (async)
6. TF-IDF, BM25, and vector indices updated
7. Memory inserted into `memories` table with timestamps
8. Changelog entry created in `memory_versions` table (auto-versioning)
9. Response includes conflict warnings, duplicate alerts, related memories

**Memory Recall (recall → search → rank → return):**

1. User calls `recall(topic, condensed=False)`
2. Query complexity classified via `classify_query_complexity()` (simple/medium/complex)
3. Query routed to retrieval based on complexity:
   - **Simple**: Community summaries only (50% context reduction)
   - **Medium**: Summaries + key raw memories
   - **Complex**: Full raw memory access
4. Parallel retrieval:
   - BM25 search on keywords via `BM25Index.search()`
   - Vector search via Qdrant `VectorIndex.search()`
   - Both return ranked lists of (memory_id, score) tuples
5. Reciprocal Rank Fusion fuses results: `reciprocal_rank_fusion()`
6. Decay weight applied: `calculate_memory_decay(created_at, half_life=30 days)`
7. Boost multipliers applied: Failed decisions 1.5x, warnings 1.2x
8. Surprise scores applied if available (novelty boost)
9. Results filtered by diversity: `search_diversity_max_per_file=3`
10. Results ranked by: semantic_relevance × decay_weight × boost_multipliers × surprise_score
11. Condensed mode truncates content/rationale if `condensed=True`
12. `recall_count` incremented on memory (for saliency tracking)
13. Results cached with `get_recall_cache()`

**Rule Matching (context_check → rule evaluation):**

1. User calls `context_check(action_description)`
2. Rules TF-IDF index ensured via `_ensure_index()` with freshness check
3. Query matched against all enabled rules via `TFIDFIndex.search()`
4. Matching rules ranked by similarity
5. For each matched rule:
   - Get `trigger` description
   - Return `must_do` list (required actions)
   - Return `must_not` list (forbidden actions)
   - Return `ask_first` list (decision questions)
   - Include rule-linked warnings from past failures
6. Counsel token generated: HMAC(secret, timestamp, project_path) valid for 5 minutes
7. Response includes covenant state (communion status, counsel token)

**Session Start (get_briefing):**

1. User calls `get_briefing(focus_areas=["topic1", "topic2"])`
2. Sets `ProjectContext.briefed = True` (Covenant communion complete)
3. First run: Bootstrap extracts 7 memory categories automatically:
   - Project identity (README, manifests)
   - Architecture notes
   - Conventions/coding style
   - Entry points
   - TODOs/FIXMEs
   - Instructions
   - Git history summary
4. Subsequent runs: Fetch recent context:
   - Git changes since last session
   - Recently modified files
   - Pending decisions
   - Active warnings
5. For each focus area, pre-fetch with condensed mode:
   - `recall(focus_area, condensed=True)`
6. Build hierarchical briefing:
   - Stats (memory counts, rules, git changes)
   - Recent decisions
   - Failed approaches (boosted to top)
   - Warnings
   - Git diff summary
   - Linked projects summary
   - Bootstrap summary (first run only)
   - Pre-fetched focus area contexts
7. Return single bundled briefing message

**Covenant Enforcement Flow:**

1. Tool call received by MCP server
2. CovenantMiddleware intercepts via `on_call_tool()` hook
3. Check tool classification:
   - Exempt tools (health, get_briefing, context_check) → Allow
   - Covenant tools → Continue to state check
4. Get project state via `_get_context_state_for_middleware(project_path)`
5. For communion-required tools:
   - Check if `ProjectContext.briefed == True`
   - If False → Return `CovenantViolation.communion_required()` with remedy ("call get_briefing()")
6. For counsel-required tools:
   - Check if `ProjectContext.context_checks` has fresh token (< 5 min old)
   - If not → Return `CovenantViolation.counsel_required()` with remedy ("call context_check()")
7. If all checks pass → Allow tool execution

**State Management:**

- **Project Contexts**: Cached in `_project_contexts` dict, keyed by normalized project path
- **Context Locking**: RWLock protects concurrent access (multiple readers, exclusive writers)
- **LRU Eviction**: Stale contexts evicted every 60 seconds if `last_accessed > TTL (1 hour)`
- **Task Tracking**: `_task_contexts` tracks which contexts are active per async task
- **Eviction Prevention**: `active_requests` counter prevents eviction during ongoing operations

## Key Abstractions

**ProjectContext:**
- Purpose: Encapsulates all managers for a specific project
- Examples: `daem0nmcp/server.py` (lines 130-145)
- Pattern: Singleton per project path with lazy initialization and eviction

**Memory Model:**
- Purpose: Core data type representing any stored information
- Examples: `daem0nmcp/models.py` (Memory table), Fact table (for verified static knowledge)
- Fields: category, content, rationale, context, tags, file_path, vector_embedding, outcome, surprise_score, importance_score
- Pattern: Immutable creates, versioned updates, time-decaying relevance

**TFIDFIndex:**
- Purpose: Build and query term importance vectors for similarity matching
- Examples: `daem0nmcp/similarity.py`
- Pattern: Lazy-loaded, rebuild on content changes, used for both memory and rule matching

**RRFHybridSearch:**
- Purpose: Combine multiple ranked lists using Reciprocal Rank Fusion
- Examples: `daem0nmcp/fusion.py`
- Pattern: Pluggable architecture - accepts BM25Index, VectorIndex, and custom rankers
- Formula: score(d) = Σ 1 / (k + rank(d)) across all rankers

**Covenant Violation:**
- Purpose: Structured error response with remediation guidance
- Examples: `daem0nmcp/covenant.py` (lines 200+)
- Pattern: Contains error code, message, specific tool call remedy, and state requirements

## Entry Points

**MCP Server:**
- Location: `daem0nmcp/server.py` (lines 2800+, `main()` function)
- Triggers: `python -m daem0nmcp.server` or `fastmcp run daem0nmcp.server`
- Responsibilities:
  - Initialize FastMCP server with CovenantMiddleware
  - Register 50+ tool handlers
  - Handle project context lifecycle (creation, eviction, cleanup)
  - Route all MCP tool calls to appropriate handlers

**CLI Interface:**
- Location: `daem0nmcp/cli.py` (lines 200+, `main()` function)
- Triggers: `python -m daem0nmcp.cli <command>`
- Responsibilities:
  - Parse CLI arguments (command, options, file paths)
  - Initialize single project context
  - Execute async operations and format output
  - Integrate with git hooks and external tools

**Pre-Commit Hook:**
- Location: `daem0nmcp/enforcement.py`
- Triggers: Git pre-commit hook during `git commit`
- Responsibilities:
  - Check staged files against memories and rules
  - Block commits if decisions lack outcomes (>24h old)
  - Block commits if modifying files with known failed approaches
  - Warn on pending decisions

**File Watcher Daemon:**
- Location: `daem0nmcp/watcher.py`
- Triggers: `python -m daem0nmcp.cli watch`
- Responsibilities:
  - Watch project files for changes
  - Send notifications via system, log file, or editor poll channels
  - Emit events when modified files have associated memories
  - Run continuously in background

## Error Handling

**Strategy:** Structured error responses with actionable remediation

**Patterns:**
- **Covenant Violations**: Include specific tool call remedy and state requirements
- **Database Errors**: Retry with exponential backoff for transient failures
- **Vector Encoding Errors**: Graceful fallback to TF-IDF/BM25 only (no vectors)
- **File Access Errors**: Return relative paths when absolute paths not accessible
- **Memory Conflicts**: Return conflict warnings alongside successful storage (non-fatal)
- **Async Timeouts**: Cancel pending operations and clean up contexts

**Example Structures:**
```python
# Covenant violation (covenant.py)
{
    "error": "COMMUNION_REQUIRED",
    "message": "Must call get_briefing() first",
    "remedy": "Call: mcp__daem0nmcp__get_briefing(project_path='...')",
    "state": {"briefed": False}
}

# Memory conflict detection (memory.py)
{
    "id": 42,
    "message": "Memory stored successfully",
    "conflicts": [
        {"id": 35, "reason": "Similar memory exists", "similarity": 0.92}
    ],
    "related": [...]
}
```

## Cross-Cutting Concerns

**Logging:** Structured logging via Python logging module with request IDs for tracing
- Request ID tracking via `with_request_id()` context manager
- Custom StructuredFormatter for JSON-compatible output
- Configuration via `DAEM0NMCP_LOG_LEVEL` env var (default: INFO)

**Validation:** Multi-layer validation
- Content size limits: `max_content_size=1MB` for ingestion
- File path normalization: `_normalize_file_path()` handles Windows case-folding
- URL validation: Strict IP/hostname validation for ingestion security
- Covenant token validation: HMAC-based validation with TTL checks

**Authentication:** MCP protocol level
- Project path identification: Each tool call must include project_path
- Covenant token proof: Cryptographic tokens for counsel TTL validation
- No per-user auth (multi-project isolation via project_path)

**Caching:**
- Memory recall cache: `get_recall_cache()` with configurable TTL
- Rules index cache: TF-IDF index cached until database changes detected
- BM25 index cache: Rebuilt on document changes, not persisted
- Parse tree cache: AST caching in code indexer for unchanged files
- Project context cache: LRU eviction per-project, singleton per path

---

*Architecture analysis: 2026-01-22*
