# External Integrations

**Analysis Date:** 2026-01-22

## APIs & External Services

**Web Content Ingestion:**
- HTTP(S) URLs - Fetched via httpx for external documentation
  - Tool: `ingest_doc` in `daem0nmcp/server.py`
  - Client: httpx AsyncClient (max 1 connection, no keepalive)
  - Parser: BeautifulSoup4 for HTML/XML extraction
  - Security: URL scheme validation (http/https only), content-length limits (1MB)
  - Timeout: Configurable via `DAEM0NMCP_INGEST_TIMEOUT` (default: 30s)
  - Max chunks: 50 per ingestion (configurable via `DAEM0NMCP_MAX_CHUNKS`)

**Git Integration:**
- Git CLI commands (subprocess-based, not library)
  - Used in: `daem0nmcp/server.py` → `_get_git_history_summary()`, `_get_git_changes()`
  - Purpose: Bootstrapping context (git log summary), detecting changes since last session
  - Commands: `git rev-parse --git-dir`, `git log`, `git diff`
  - Timeout: 10 seconds per command
  - Graceful fallback if git not available or not a repo

**MCP Protocol:**
- FastMCP 3.0+ - Model Context Protocol server
  - Location: `daem0nmcp/server.py`
  - Provides tool definitions and execution
  - 42 tools exposed via MCP interface
  - Middleware support for covenant enforcement

## Data Storage

**Databases:**
- SQLite (local file-based, no server)
  - Connection: `sqlite+aiosqlite:///{project_path}/.daem0nmcp/storage/daem0nmcp.db`
  - Client: SQLAlchemy 2.0+ (async)
  - Async driver: aiosqlite 0.19+
  - Connection pool: NullPool (each operation gets fresh connection)
  - PRAGMA configurations: WAL mode, synchronous=NORMAL, 64MB cache, foreign keys enabled
  - Performance optimized for concurrent async access

**Vector Storage:**
- Qdrant (local or remote)
  - Location: `{project_path}/.daem0nmcp/storage/qdrant` (local default)
  - Remote: Configurable via `DAEM0NMCP_QDRANT_URL` + `DAEM0NMCP_QDRANT_API_KEY`
  - Client: qdrant-client (supports local file mode and cloud instances)
  - Collections: `daem0n_memories`, `daem0n_code_entities`
  - Embedding dimension: 384 (all-MiniLM-L6-v2)
  - Distance metric: Cosine similarity
  - Implementation: `daem0nmcp/qdrant_store.py`

**File Storage:**
- Local filesystem only
  - Memories, rules, vectors stored in SQLite + Qdrant
  - Project exports as JSON: `daem0nmcp/server.py` → `export_data()` tool
  - Project imports from JSON: `daem0nmcp/server.py` → `import_data()` tool

**Caching:**
- In-memory caching of embeddings model (lazy loaded, shared)
- BM25 index cached in memory (rebuilt on demand)
- Project context caching with TTL: 1 hour default (configurable via `DAEM0NMCP_CONTEXT_TTL_SECONDS`)
- LRU-style context eviction based on TTL

## Authentication & Identity

**Auth Provider:**
- Custom (none - MCP is invoked by AI client which handles auth)
- Covenant enforcement: Custom middleware for tool access control
  - Middleware: `daem0nmcp/enforcement.py` → `CovenantMiddleware`
  - Requirements: `get_briefing` (communion) before any tool use
  - Requirements: `context_check` (counsel) before major operations
  - Tracking: SessionState table in database

**Access Control:**
- Per-project isolation (project_path parameter required)
- Covenant-based tool access gating
- Pending decision threshold enforcement (blocks commits, default: 24 hours)

## Monitoring & Observability

**Error Tracking:**
- None (no external error tracking service)
- Exceptions logged locally via Python logging module
- Server can export structured logs for client processing

**Logs:**
- Python logging module (stdlib)
  - Level: Configurable via `DAEM0NMCP_LOG_LEVEL` (default: INFO)
  - Format: Standard logging format
  - Log level propagation through all modules
  - No structured logging service integration by default

**Tracing (Optional):**
- OpenTelemetry integration (disabled by default)
  - Enable: Set `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317`
  - Service name: Configurable via `OTEL_SERVICE_NAME` (default: daem0nmcp)
  - SDK: opentelemetry-sdk 1.20+
  - Exporter: opentelemetry-exporter-otlp 1.20+
  - Implementation: `daem0nmcp/tracing.py` (detection and helpers)
  - FastMCP 3.0 provides native OpenTelemetry support

## File System Monitoring (Optional)

**Watcher Daemon:**
- Watchdog 3.0+ - Cross-platform file system monitoring
  - Enable: `DAEM0NMCP_WATCHER_ENABLED=true`
  - Debounce: Configurable via `DAEM0NMCP_WATCHER_DEBOUNCE_SECONDS` (default: 1.0s)
  - Implementation: `daem0nmcp/watcher.py` → `FileWatcher`
  - Purpose: Detect file changes, trigger memory recalls, send notifications
  - Supported channels:
    - System notifications (desktop): `daem0nmcp/channels/system_notify.py` (plyer 2.1+)
    - Log file: `daem0nmcp/channels/log_notify.py` (writes to log file)
    - Editor polling: `daem0nmcp/channels/editor_poll.py` (creates polling file for IDE integration)

**Notifications:**
- Desktop system notifications via plyer 2.1+ (cross-platform)
  - Platform support: Windows, macOS, Linux
  - Timeout: Configurable per notification
  - Implementation: `daem0nmcp/channels/system_notify.py`
  - Requires platform-specific notification permissions

## CI/CD & Deployment

**Hosting:**
- Self-hosted (runs as standalone process)
- Communicates via MCP protocol (stdio-based)
- Suitable for local development or AI client servers

**CI Pipeline:**
- None detected (no GitHub Actions or external CI integration)
- Testing via pytest locally

**Entry Point:**
- Command: `daem0nmcp` (setuptools script) → `daem0nmcp.server:main()`
- Or: `python -m daem0nmcp` (module main)
- Or: Direct import and instantiation in code

## Environment Configuration

**Required env vars:**
- None (all optional with sensible defaults)

**Critical env vars (if using features):**
- `DAEM0NMCP_PROJECT_ROOT` - Project root for context
- `DAEM0NMCP_STORAGE_PATH` - Custom storage location (auto-detects in project)
- `DAEM0NMCP_QDRANT_URL` - Remote Qdrant instance (if not using local)
- `DAEM0NMCP_QDRANT_API_KEY` - API key for remote Qdrant (if needed)
- `OTEL_EXPORTER_OTLP_ENDPOINT` - Tracing endpoint (if enabling observability)

**Secrets location:**
- Environment variables only (no secrets file support)
- `DAEM0NMCP_QDRANT_API_KEY` should be passed via secure environment mechanism
- No hard-coded credentials in codebase

## Webhooks & Callbacks

**Incoming:**
- None detected (MCP tools handle all communication)

**Outgoing:**
- None detected (system reactive only, no outbound webhooks)

## Search Integration

**Semantic Search:**
- sentence-transformers all-MiniLM-L6-v2 model
  - Auto-downloads on first use (cached in ~/.cache/huggingface/)
  - Generates 384-dimensional vectors
  - Used by Qdrant for vector similarity
  - Used by hybrid search combining BM25 + vectors

**Keyword Search:**
- rank-bm25 (Okapi BM25) for keyword-based retrieval
  - Implementation: `daem0nmcp/bm25_index.py`
  - Tuning parameters configurable:
    - `DAEM0NMCP_BM25_K1` - Term frequency saturation (default: 1.5)
    - `DAEM0NMCP_BM25_B` - Document length normalization (default: 0.75)
  - RRF (Reciprocal Rank Fusion) combines results
    - `DAEM0NMCP_RRF_K` - Dampening constant (default: 60)

**Hybrid Search:**
- Combines BM25 + vector similarity via RRF
  - Weight configurable: `DAEM0NMCP_HYBRID_VECTOR_WEIGHT` (default: 0.3)
  - 0.0 = TF-IDF only, 1.0 = vectors only

## Code Understanding

**Language Support:**
- tree-sitter language pack for syntax tree parsing
  - Implementation: `daem0nmcp/code_indexer.py`
  - Supports multiple languages (configurable via `DAEM0NMCP_INDEX_LANGUAGES`)
  - Parse tree caching (max 200 entries, configurable)
  - Phase 2 feature (code entity indexing)

**Entity Extraction:**
- Custom regex-based entity extraction (no external NLP service)
  - Implementation: `daem0nmcp/entity_extractor.py`
  - Extracts functions, classes, variables, patterns
  - Supports Python, JavaScript, TypeScript syntax patterns
  - Integration: `daem0nmcp/entity_manager.py` → stores in SQLite

---

*Integration audit: 2026-01-22*
