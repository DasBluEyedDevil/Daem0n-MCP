# Technology Stack

**Analysis Date:** 2026-01-22

## Languages

**Primary:**
- Python 3.10+ (requires >=3.10) - Core runtime for entire system
- Tested on Python 3.10, 3.11, 3.12, 3.14

## Runtime

**Environment:**
- Python 3.10+ required
- asyncio-based event loop for async operations
- Supports Windows, macOS, Linux

**Package Manager:**
- uv (modern Python package manager with lockfile)
- Lockfile: `uv.lock` present (484KB)
- Alternative: pip/setuptools supported via `pyproject.toml`

## Frameworks

**Core MCP:**
- FastMCP 3.0+ - Model Context Protocol server framework with built-in OpenTelemetry support
  - Location: `daem0nmcp/server.py`
  - Provides middleware system for covenant enforcement

**Database/ORM:**
- SQLAlchemy 2.0+ - Async SQL toolkit with support for async contexts
- aiosqlite 0.19+ - Async SQLite driver (sqlite3 compatibility for async)
- greenlet 3.0+ - Required for SQLAlchemy async coroutine support

**Vector Database:**
- Qdrant (local mode) - Persistent vector storage for semantic embeddings
  - Collections: `daem0n_memories`, `daem0n_code_entities`
  - Embedding dimension: 384 (all-MiniLM-L6-v2 output)
  - Distance metric: Cosine similarity

**Search & Retrieval:**
- sentence-transformers 2.2+ - Semantic embeddings (model: all-MiniLM-L6-v2)
- rank-bm25 0.2.2+ - BM25 Okapi algorithm for keyword-based retrieval
- numpy 1.24+ - Vector operations and numerical computing

**Configuration:**
- pydantic-settings 2.0+ - Environment-based settings with validation
  - Prefix: `DAEM0NMCP_` for environment variables
  - Supports .env file loading

**Web Content Processing:**
- httpx 0.25+ - Async HTTP client for URL fetching
- beautifulsoup4 4.12+ - HTML/XML parsing for web ingestion
- Both optional for ingest_doc tool functionality

**File System Monitoring:**
- watchdog 3.0+ - Cross-platform file system event monitoring
- plyer 2.1+ - Cross-platform desktop notifications (Windows, macOS, Linux)

**Code Understanding:**
- tree-sitter-language-pack 0.13+ - Language-agnostic parsing and syntax trees

## Testing

**Testing Framework:**
- pytest 7.0+ - Test runner
- pytest-asyncio 0.23+ - Async test support (auto mode)
  - asyncio_mode = "auto"
  - asyncio_default_fixture_loop_scope = "function"
- Location: `tests/` directory
- Configuration: `pytest.ini` + `pyproject.toml`

**Test Execution:**
```bash
pytest                    # Run all tests
pytest tests/            # Explicit test directory
pytest -v               # Verbose output
pytest --tb=short       # Short traceback format
```

## Key Dependencies

**Critical:**
- fastmcp>=3.0.0b1 - Core MCP server framework (beta required for middleware support)
- sqlalchemy>=2.0.0 - Async ORM required for async database operations
- qdrant-client>=1.7.0 - Vector storage client (critical for memory retrieval)
- sentence-transformers>=2.2.0 - Semantic understanding (used by all memory recalls)

**Infrastructure:**
- aiosqlite>=0.19.0 - Async SQLite driver (bridges sync SQLite to async)
- greenlet>=3.0.0 - Enables SQLAlchemy async sessions
- pydantic-settings>=2.0.0 - Configuration management with validation
- watchdog>=3.0.0 - File system monitoring (if watcher enabled)
- plyer>=2.1.0 - System notifications (if notifications enabled)

**Optional (for specific features):**
- httpx>=0.25.0 + beautifulsoup4>=4.12.0 - Web ingestion (ingest_doc tool)
- tree-sitter-language-pack>=0.13.0 - Code analysis (Phase 2 feature)

**Optional (for observability):**
- opentelemetry-api>=1.20.0 - Tracing API
- opentelemetry-sdk>=1.20.0 - Tracing implementation
- opentelemetry-exporter-otlp>=1.20.0 - OTLP exporter (when OTEL_EXPORTER_OTLP_ENDPOINT set)

## Configuration

**Environment:**
- Settings loaded from `DAEM0NMCP_*` prefixed environment variables
- Optional `.env` file support (utf-8 encoded)
- Configuration class: `daem0nmcp/config.py` → `Settings`
- All settings optional with sensible defaults

**Key Configurations:**
- `DAEM0NMCP_LOG_LEVEL` - Logging level (default: INFO)
- `DAEM0NMCP_PROJECT_ROOT` - Project root path (default: ".")
- `DAEM0NMCP_STORAGE_PATH` - Storage directory (auto-detects if not set)
- `DAEM0NMCP_QDRANT_PATH` - Local Qdrant storage (auto-detects if not set)
- `DAEM0NMCP_QDRANT_URL` - Remote Qdrant URL (overrides local path)
- `DAEM0NMCP_QDRANT_API_KEY` - API key for remote Qdrant cloud
- `DAEM0NMCP_EMBEDDING_MODEL` - Sentence-transformers model (default: all-MiniLM-L6-v2)
- `DAEM0NMCP_WATCHER_ENABLED` - Enable file watcher (default: false)
- `OTEL_EXPORTER_OTLP_ENDPOINT` - OpenTelemetry endpoint (auto-enables tracing)
- `OTEL_SERVICE_NAME` - Service name for tracing (default: daem0nmcp)

**Build:**
- `pyproject.toml` - Standard Python packaging configuration
- Entry point: `daem0nmcp.server:main` (CLI command: `daem0nmcp`)
- Build backend: setuptools with wheel support
- No build-time dependencies beyond setuptools>=61.0

## Database

**Primary Storage:**
- SQLite (async via aiosqlite)
  - Database file: `.daem0nmcp/storage/daem0nmcp.db`
  - WAL mode enabled for concurrent access
  - Performance pragmas: synchronous=NORMAL, cache_size=64MB
  - Foreign keys enabled
  - Temp tables in memory

**Models Location:** `daem0nmcp/models.py`
- Memory (core memory records)
- MemoryVersion (versioning)
- ActiveContextItem (working context)
- MemoryCommunity (entity clustering)
- ContextTrigger (pattern matching)
- SessionState (covenant enforcement)
- ExtractedEntity, MemoryEntityRef (entity linking)
- RuleNode (decision trees)

**Migrations:** `daem0nmcp/migrations/`
- Schema initialization via SQLAlchemy DeclarativeBase
- Auto-migration on startup
- Legacy data migration support (.devilmcp → .daem0nmcp)

## Vector Database

**Qdrant Configuration:**
- Local file-based storage at `.daem0nmcp/storage/qdrant` (default)
- Supports remote cloud instances via `DAEM0NMCP_QDRANT_URL` + `DAEM0NMCP_QDRANT_API_KEY`
- Collections:
  - `daem0n_memories` - Memory embeddings (384 dims, cosine distance)
  - `daem0n_code_entities` - Code entity embeddings (Phase 2, reserved)

**Embedding:**
- Model: all-MiniLM-L6-v2 (384 dimensions)
- Lazy loading on first use
- Shared across all project contexts
- Generated by `daem0nmcp/vectors.py` → `encode()` function

## Platform Requirements

**Development:**
- Python 3.10+
- pip, uv, or poetry for package management
- pytest for running tests
- Git (for git integration features)

**Production:**
- Python 3.10+
- SQLite support (built-in to Python)
- 100MB+ disk space for vector database and memories
- Async-capable runtime (Python native asyncio)

## Server Startup

**Entry Point:**
- `daem0nmcp/server.py` → `main()` function
- Or via command: `daem0nmcp` (setuptools script)
- Starts FastMCP server for MCP client connections

**Project-Specific Storage:**
- Each project gets isolated storage at `{project_root}/.daem0nmcp/storage/`
- Multiple projects can share same Daem0n server instance
- project_path parameter required for all tools (identifies which memories to access)

---

*Stack analysis: 2026-01-22*
