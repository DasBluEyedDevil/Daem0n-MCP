# Codebase Concerns

**Analysis Date:** 2026-01-22

## Tech Debt

**Community Matching Algorithm:**
- Issue: Substring matching for topic-to-community filtering is simplistic and misses semantic relationships
- Files: `daem0nmcp/memory.py` (line 2274)
- Impact: Communities not matched when keywords don't contain exact substrings (e.g., "authentication" won't match "auth + jwt")
- Fix approach: Implement TF-IDF or semantic similarity scoring for community matching using existing similarity infrastructure

**Windows Stdio Handling:**
- Issue: Documented issue with stdio hanging on Windows platforms
- Files: `daem0nmcp/server.py` (line 4)
- Impact: MCP server can hang on Windows without manual environment configuration (PYTHONUNBUFFERED=1)
- Fix approach: Wrap server initialization with automatic Windows buffering detection or switch to line-buffered mode

**TODO Configuration Comment:**
- Issue: Incomplete configuration documentation
- Files: `daem0nmcp/config.py` (line 44)
- Impact: Unclear what TODO scanner configuration actually encompasses
- Fix approach: Complete the documentation with actual configuration options and defaults

## Known Bugs

**Event Queue Overflow in File Watcher:**
- Symptoms: File change events silently dropped when watcher queue is full, no retry mechanism
- Files: `daem0nmcp/watcher.py` (line 284-285)
- Trigger: Rapid file changes exceeding internal queue capacity during batch operations (e.g., git operations)
- Workaround: Increase debounce window or reduce watcher frequency via configuration
- Notes: Only logs warning, doesn't re-queue events when queue fills up

**SQLite Concurrent Write Conflicts:**
- Symptoms: Potential database locking issues under high concurrent load
- Files: `daem0nmcp/database.py` (lines 42-67)
- Current mitigation: WAL mode enabled, NullPool used to avoid cross-context connection pooling, 30-second busy timeout
- Notes: Still at risk under sustained concurrent writes; SQLite has inherent single-writer limitation

## Security Considerations

**Subprocess Invocation in Pre-commit Hook:**
- Risk: Subprocess invocation uses user-provided arguments without strict validation
- Files: `daem0nmcp/cli.py` (lines 463-468)
- Current mitigation: Uses `check=False` to handle errors gracefully, subprocess.SubprocessError caught
- Recommendations: Validate staged file paths, use absolute paths, consider explicit command list construction rather than shell execution

**File Path Normalization on Windows:**
- Risk: Case-sensitive path matching issues could lead to repeated indexing or memory misses
- Files: `daem0nmcp/memory.py` (lines 91-94)
- Current mitigation: Case-folding implemented for Windows (`.lower()`) in `_normalize_file_path()`
- Recommendations: Ensure all path comparisons throughout codebase use normalized paths consistently

**Vector Model Lazy Loading:**
- Risk: Global mutable state (`_model` global) shared across async contexts could cause thread-safety issues
- Files: `daem0nmcp/vectors.py` (lines 21-39)
- Current mitigation: Model loaded once and cached, SentenceTransformer is thread-safe for inference
- Recommendations: Document thread-safety assumptions, consider explicit initialization on startup rather than lazy loading

**Input Validation in Environment Configuration:**
- Risk: Config loading from environment variables with weak type validation
- Files: `daem0nmcp/config.py` (lines 15-95)
- Current mitigation: Pydantic Settings used with type hints and Field validators
- Recommendations: Add explicit bounds checking for numeric configs (max_content_size, timeouts, etc.)

## Performance Bottlenecks

**Large File Scanning in TODO Scanner:**
- Problem: Entire project recursively scanned for TODO/FIXME comments on every scan request
- Files: `daem0nmcp/server.py` (lines 2227-2320)
- Cause: No incremental scanning, no caching of scan results, file-by-file regex matching
- Improvement path: Implement incremental scanning, cache results with file mtime tracking, batch regex compilation

**In-Memory Vector Index Growth:**
- Problem: VectorIndex stores all vectors in memory (Dict[int, List[float]]), unbounded growth
- Files: `daem0nmcp/vectors.py` (lines 84-100)
- Cause: No eviction policy, no size bounds enforcement
- Improvement path: Implement LRU eviction, configurable size limits, periodic cleanup based on memory pressure

**TTL Cache Without Expiration:**
- Problem: Cache entries only expire on access, not actively cleaned
- Files: `daem0nmcp/cache.py` (lines 18-128)
- Cause: No background cleanup task, stale entries accumulate in memory
- Improvement path: Add optional background cleanup thread, implement configurable max cache age

**Substring-Based Community Filtering:**
- Problem: O(n) substring matching for each memory against all communities
- Files: `daem0nmcp/memory.py` (lines 2273-2279)
- Cause: No index on community names, no ranking/early termination
- Improvement path: Pre-compute TF-IDF vectors for communities, use vector similarity with configurable threshold

## Fragile Areas

**Database Session Management:**
- Files: `daem0nmcp/database.py` (lines 128-139)
- Why fragile: Async context manager with implicit rollback on exception, but no explicit error logging of rollback reason
- Safe modification: Always wrap database operations with explicit try-except to log actual error before rollback
- Test coverage: Session tests exist but don't cover all rollback scenarios (constraint violations, partial writes)

**File Watcher Event Processing Loop:**
- Files: `daem0nmcp/watcher.py` (lines 315-430)
- Why fragile: Thread-safe event queue with `call_soon_threadsafe()` to async loop, but assumes loop is always running
- Safe modification: Add explicit loop lifecycle checks, implement timeout for queue operations
- Test coverage: Minimal testing of concurrent file changes; no tests for queue overflow scenarios

**Async Context Manager Nesting in Server:**
- Files: `daem0nmcp/server.py` (multiple tools, typical pattern at 567-605)
- Why fragile: Multiple nested async context managers without explicit exception boundaries
- Safe modification: Extract context acquisition to helper functions with clear error handling paths
- Test coverage: Tool tests don't cover all context manager exception scenarios

**Migration System:**
- Files: `daem0nmcp/migrations/`, `daem0nmcp/config.py` (lines 87-101)
- Why fragile: Manual migration runner called at startup without full rollback capability
- Safe modification: Implement version tracking with rollback capability, add dry-run mode
- Test coverage: No migration rollback tests; only forward migration tested

## Scaling Limits

**SQLite Single-Writer Limitation:**
- Current capacity: Designed for single concurrent writer, multiple readers
- Limit: High-frequency memory writes under 10+ concurrent clients will serialize on WAL checkpoint
- Scaling path: Migrate to PostgreSQL with connection pooling for >100 concurrent users, or implement sharding by project

**Vector Model Memory Footprint:**
- Current capacity: all-MiniLM-L6-v2 model ~80MB, loads on first use
- Limit: Embedding 1000+ memories per session can consume 100s of MB for vectors in memory
- Scaling path: Implement model sharding, use quantized models, or delegate to external embedding service

**In-Memory Index Data Structures:**
- Current capacity: TTL cache with 100-entry default, VectorIndex unbounded
- Limit: Cache hit rate degrades with >500 active memories, VectorIndex grows without bounds
- Scaling path: Add configurable size limits, implement lazy loading from database, consider Redis for distributed caching

**File Watcher Event Queue:**
- Current capacity: Default queue size not explicitly set; depends on asyncio.Queue defaults
- Limit: Rapid file modifications (>100/sec) will overflow queue, dropping events silently
- Scaling path: Make queue size configurable, implement batching, consider separate worker pool for processing

## Dependencies at Risk

**FastMCP Breaking Changes:**
- Risk: Recent migration from `mcp.server.fastmcp` to `fastmcp` (v3.0.0b1) is a breaking change
- Files: `daem0nmcp/server.py` (lines 75-100)
- Impact: Requires exact version pin; incompatible with MCP < 3.0
- Migration plan: Document upgrade path clearly; consider feature flags for backward compatibility if extended support needed

**SentenceTransformer Model Downloads:**
- Risk: Model auto-downloads on first use from HuggingFace, no offline mode or caching strategy
- Files: `daem0nmcp/vectors.py` (line 36)
- Impact: First startup requires network access and 100+ MB download, can timeout in restricted environments
- Migration plan: Pre-download model during installation, cache locally, add fallback to simpler embedder

**Qdrant Client Compatibility:**
- Risk: Direct HTTP client usage may have version mismatches with server
- Files: `daem0nmcp/memory.py` (line 32) imports ResponseHandlingException, UnexpectedResponse
- Impact: Unhandled response exceptions could crash memory recall operations
- Migration plan: Add comprehensive exception handling for all Qdrant operations, add version negotiation

**Tree-Sitter Language Pack:**
- Risk: Pre-compiled wheels not available for all platforms, Python version-dependent
- Files: `daem0nmcp/code_indexer.py` uses tree-sitter parsing
- Impact: Installation failures on Python 3.14+, binary incompatibility on some platforms
- Migration plan: Add fallback AST parser, document supported platforms clearly

## Missing Critical Features

**Distributed Tracing:**
- Problem: Correlation IDs implemented but tracing integration incomplete
- Blocks: Can't trace requests across multiple tools or debug performance bottlenecks in complex flows
- Files: `daem0nmcp/logging_config.py` has request_id_var but OpenTelemetry integration is optional extra

**Incremental Indexing:**
- Problem: No incremental code indexing; rebuilding index scans entire codebase
- Blocks: Large codebases (10k+ files) experience long initialization times and high CPU usage
- Files: `daem0nmcp/code_indexer.py` lacks delta-based indexing

**Graceful Shutdown:**
- Problem: File watcher and background tasks have no coordinated shutdown
- Blocks: Server may lose in-flight work on SIGTERM, no drain mechanism for pending operations
- Files: `daem0nmcp/watcher.py` and `daem0nmcp/server.py` lack atexit handlers for file watcher

**Batch Operations:**
- Problem: No batch API for bulk memory operations (store multiple, delete multiple)
- Blocks: Importing large external datasets or cleanup operations require N tool calls
- Files: All memory operations are single-item; no batch helper tools

## Test Coverage Gaps

**Database Transaction Failures:**
- What's not tested: Rollback behavior under constraint violations, unique key conflicts, deadlock scenarios
- Files: `daem0nmcp/database.py`, all test files using database
- Risk: Transactional integrity issues could corrupt memory relationships silently
- Priority: High

**Async/Threading Edge Cases:**
- What's not tested: Queue overflow in file watcher, concurrent memory updates, session cleanup under exceptions
- Files: `daem0nmcp/watcher.py`, `daem0nmcp/database.py`
- Risk: Data races and resource leaks under high load
- Priority: High

**Windows Path Handling:**
- What's not tested: Case-insensitive matching with mixed case files, UNC paths, long path names
- Files: `daem0nmcp/memory.py` path normalization functions
- Risk: File association failures on Windows, path comparison bugs
- Priority: Medium

**Vector Index Memory Limits:**
- What's not tested: Behavior when vectors exceed available memory, concurrent vector operations
- Files: `daem0nmcp/vectors.py` VectorIndex class
- Risk: Out-of-memory crashes without graceful degradation
- Priority: Medium

**Migration Edge Cases:**
- What's not tested: Schema version downgrades, partial migration failures, corruption recovery
- Files: `daem0nmcp/migrations/`, `daem0nmcp/database.py`
- Risk: Database corruption on failed upgrades, difficult recovery
- Priority: Medium

**Qdrant Connection Failures:**
- What's not tested: Timeout recovery, connection pooling under network errors, vector encoding fallback
- Files: `daem0nmcp/memory.py` Qdrant integration
- Risk: Memory recall hangs on network issues, no fallback to TF-IDF only
- Priority: High

---

*Concerns audit: 2026-01-22*
