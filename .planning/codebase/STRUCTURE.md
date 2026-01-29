# Codebase Structure

**Analysis Date:** 2026-01-22

## Directory Layout

```
daem0nmcp/
├── __init__.py                    # Package init, exports version
├── __main__.py                    # Entry point for `python -m daem0nmcp`
├── server.py                      # FastMCP server, 50+ MCP tools, project context mgmt
├── memory.py                      # Memory storage, semantic retrieval, decay
├── rules.py                       # Rule engine, decision tree matching
├── similarity.py                  # TF-IDF vectorization, decay calculation, conflict detection
├── config.py                      # Pydantic settings, env var loading
├── database.py                    # SQLAlchemy async database manager
├── models.py                      # 10+ SQLAlchemy ORM models
├── covenant.py                    # Sacred Covenant enforcement, decorators, tokens
├── cli.py                         # Command-line interface
├── vectors.py                     # sentence-transformers embeddings, Qdrant integration
├── bm25_index.py                  # Okapi BM25 keyword search index
├── fusion.py                      # Reciprocal Rank Fusion hybrid search
├── recall_planner.py              # TiMem complexity classification (simple/medium/complex)
├── surprise.py                    # Titans-inspired novelty detection scoring
├── prompt_templates.py            # AutoPDL-inspired modular prompt system
├── tool_search.py                 # Dynamic MCP tool discovery index
├── communities.py                 # GraphRAG community detection for hierarchical recall
├── active_context.py              # MemGPT-style always-hot memory layer
├── context_triggers.py            # Auto-recall pattern matching (file, tag, entity)
├── entity_manager.py              # Entity extraction and entity-based recall
├── entity_extractor.py            # Helper for entity extraction from content
├── code_indexer.py                # Tree-sitter AST parsing for code understanding
├── watcher.py                     # Proactive file watcher daemon
├── enforcement.py                 # Pre-commit hook enforcement
├── hooks.py                       # Git hook templates and installation
├── links.py                       # Multi-project linking
├── cache.py                       # Memory and rules caching
├── rwlock.py                      # Reader-writer lock for concurrent access
├── background.py                  # Background task management
├── logging_config.py              # Structured logging configuration
├── tracing.py                     # Optional OpenTelemetry integration
├── qdrant_store.py                # Qdrant vector database adapter
├──
├── channels/                      # Notification channels for file watcher
│   ├── __init__.py
│   ├── system_notify.py           # Desktop notifications via plyer
│   ├── log_notify.py              # JSON-lines file logging
│   └── editor_poll.py             # Editor polling endpoint for context injection
│
├── migrations/                    # Database schema migrations
│   ├── __init__.py
│   ├── schema.py                  # Schema definitions and migration helpers
│   └── migrate_vectors.py         # Vector embedding migration script
│
└── transforms/                    # FastMCP 3.0 middleware transforms
    ├── __init__.py
    └── covenant.py                # CovenantMiddleware for tool call interception

tests/                            # Test suite (559 tests)
├── conftest.py                    # Pytest configuration and fixtures
├── test_*.py                      # Test files organized by component
├── ...

docs/                             # Documentation
├── multi-repo-setup.md            # Linked projects guide
└── ...

.planning/
└── codebase/                     # GSD codebase analysis documents
    ├── ARCHITECTURE.md           # Architecture and layers
    ├── STRUCTURE.md              # This file
    ├── CONVENTIONS.md            # Coding conventions
    ├── TESTING.md                # Testing patterns
    ├── STACK.md                  # Technology stack
    ├── INTEGRATIONS.md           # External integrations
    └── CONCERNS.md               # Technical debt and issues

hooks/                            # Pre-commit hook scripts (deprecated, in code now)
.claude/
└── skills/
    └── daem0nmcp-protocol/
        └── SKILL.md               # Claude Superpowers skill for protocol enforcement

Summon_Daem0n.md                  # Installation guide (ritual theme)
Banish_Daem0n.md                  # Uninstallation guide
start_server.py                   # HTTP server launcher for Windows
pyproject.toml                    # Project metadata and dependencies
pytest.ini                        # Pytest configuration
README.md                         # Main documentation
```

## Directory Purposes

**daem0nmcp/:**
- Purpose: Main package containing all server, memory, and management code
- Contains: 30+ Python modules for memory management, search, enforcement, and CLI
- Key files: `server.py` (entry point), `memory.py` (core logic), `models.py` (data schema)

**daem0nmcp/channels/:**
- Purpose: Notification channels for proactive file watcher
- Contains: Multiple backends for sending memory change alerts
- Key files:
  - `system_notify.py`: Desktop notifications via plyer (Win/Mac/Linux)
  - `log_notify.py`: JSON-lines logging for external monitoring
  - `editor_poll.py`: Polling endpoint for IDE/editor integration

**daem0nmcp/migrations/:**
- Purpose: Database schema versioning and migrations
- Contains: Auto-running migration helpers and vector backfill scripts
- Key files:
  - `schema.py`: Schema definition helpers
  - `migrate_vectors.py`: Backfill vector embeddings for existing memories

**daem0nmcp/transforms/:**
- Purpose: FastMCP 3.0 middleware transforms
- Contains: Covenant enforcement middleware for tool call interception
- Key files:
  - `covenant.py`: CovenantMiddleware implementing Sacred Covenant at transport layer

**tests/:**
- Purpose: Test suite (559 tests covering all major functionality)
- Contains: Unit tests, integration tests, async tests
- Key files:
  - `conftest.py`: Pytest fixtures (temp databases, async event loops)
  - `test_memory.py`: Memory CRUD and semantic search tests
  - `test_rules.py`: Rule engine tests
  - `test_covenant.py`: Covenant enforcement tests
  - `test_server.py`: MCP tool integration tests

**docs/:**
- Purpose: Supplementary documentation
- Contains: Multi-repo setup guides, troubleshooting, advanced features
- Key files:
  - `multi-repo-setup.md`: Linked projects configuration guide

**.planning/codebase/:**
- Purpose: GSD codebase mapping documents for AI assistant guidance
- Contains: Architecture, structure, conventions, testing, tech stack, integrations, concerns
- Key files: This directory (read by `/gsd:plan-phase` and `/gsd:execute-phase`)

## Key File Locations

**Entry Points:**
- `daem0nmcp/__main__.py`: Python module entry point (`python -m daem0nmcp`)
- `daem0nmcp/server.py` (lines 2800+): `main()` function, MCP server initialization
- `daem0nmcp/cli.py` (lines 400+): `main()` function, CLI argument parsing
- `start_server.py`: HTTP server launcher for Windows (circumvents stdio bugs)

**Configuration:**
- `daem0nmcp/config.py`: Pydantic BaseSettings with DAEM0NMCP_ env var prefix
- `pyproject.toml`: Project metadata, dependencies, optional extras
- `pytest.ini`: Pytest config (asyncio_mode, testpaths)
- `.env`: Optional env file (git-ignored, not committed)

**Core Logic:**
- `daem0nmcp/memory.py`: Memory CRUD, outcome tracking, time decay
- `daem0nmcp/rules.py`: Rule engine with TF-IDF trigger matching
- `daem0nmcp/similarity.py`: TF-IDF vectorization, keyword extraction, decay calculation
- `daem0nmcp/server.py`: 50+ MCP tool definitions, project context management

**Search & Retrieval:**
- `daem0nmcp/bm25_index.py`: Okapi BM25 keyword search
- `daem0nmcp/vectors.py`: sentence-transformers embeddings + Qdrant integration
- `daem0nmcp/fusion.py`: Reciprocal Rank Fusion combining BM25 + vector results
- `daem0nmcp/recall_planner.py`: Complexity-aware retrieval planning

**Advanced Features:**
- `daem0nmcp/communities.py`: GraphRAG-style community detection and hierarchical recall
- `daem0nmcp/active_context.py`: MemGPT-style always-hot memory layer (max 10 items)
- `daem0nmcp/context_triggers.py`: Auto-recall pattern rules
- `daem0nmcp/code_indexer.py`: Tree-sitter AST parsing for code understanding

**Enforcement & Compliance:**
- `daem0nmcp/covenant.py`: Sacred Covenant decorators and token validation
- `daem0nmcp/transforms/covenant.py`: CovenantMiddleware for FastMCP 3.0
- `daem0nmcp/enforcement.py`: Pre-commit hook integration
- `daem0nmcp/hooks.py`: Git hook template installation

**Data Layer:**
- `daem0nmcp/database.py`: SQLAlchemy async connection manager, PRAGMA tuning
- `daem0nmcp/models.py`: ORM models (Memory, Rule, MemoryRelationship, MemoryVersion, Fact, CodeEntity, etc.)
- `daem0nmcp/qdrant_store.py`: Qdrant vector store adapter

**Testing:**
- `tests/conftest.py`: Pytest fixtures (async loops, temp databases)
- `tests/test_memory.py`: Memory storage and retrieval tests
- `tests/test_server.py`: MCP tool integration tests
- `tests/test_covenant.py`: Covenant enforcement tests

## Naming Conventions

**Files:**
- Module files: `snake_case.py` (e.g., `similarity.py`, `bm25_index.py`)
- Entry points: `__main__.py`, `server.py`, `cli.py`
- Tests: `test_*.py` (e.g., `test_memory.py`, `test_covenant.py`)
- Migrations: `migrate_*.py` (e.g., `migrate_vectors.py`)

**Directories:**
- Package directories: `snake_case` (e.g., `daem0nmcp`, `migrations`, `channels`)
- Feature directories: `snake_case` (e.g., `transforms`, `migrations`)

**Classes:**
- Pattern: PascalCase (e.g., `DatabaseManager`, `MemoryManager`, `RulesEngine`, `ProjectContext`)
- Model classes: PascalCase (e.g., `Memory`, `Rule`, `CodeEntity`)
- Engine/Manager classes: `*Manager`, `*Engine` (e.g., `MemoryManager`, `RulesEngine`)
- Transform classes: `*Middleware`, `*Transform` (e.g., `CovenantMiddleware`)
- Index classes: `*Index` (e.g., `TFIDFIndex`, `BM25Index`, `VectorIndex`)

**Functions:**
- Pattern: snake_case (e.g., `extract_keywords`, `calculate_memory_decay`, `reciprocal_rank_fusion`)
- Private functions: Leading underscore `_function_name()`
- Async functions: `async def` keyword (e.g., `async def remember()`, `async def recall()`)
- Callback functions: `_*_callback()` pattern (e.g., `_get_context_callback`, `_context_state_callback`)

**Variables:**
- Module-level constants: SCREAMING_SNAKE_CASE (e.g., `FAILED_DECISION_BOOST`, `COUNSEL_TTL_SECONDS`)
- Module-level state: `_leading_underscore` (e.g., `_project_contexts`, `_model`, `_index_loaded`)
- Local variables: snake_case (e.g., `normalized_path`, `memory_decay_weight`)

**Database/ORM:**
- Table names: plural snake_case (e.g., `memories`, `rules`, `memory_relationships`)
- Column names: snake_case (e.g., `created_at`, `file_path_relative`, `surprise_score`)
- Model class = table name pluralized (Memory → memories, Rule → rules)

## Where to Add New Code

**New Memory Management Feature:**
- Primary code: `daem0nmcp/memory.py` (add methods to MemoryManager class)
- Database model: `daem0nmcp/models.py` (add ORM model if new table needed)
- Tests: `tests/test_memory.py`
- Example: Adding a new outcome type would add a method to MemoryManager and update Memory model

**New Retrieval Algorithm:**
- Implementation: `daem0nmcp/custom_search.py` (new file for custom algorithm)
- Integration: `daem0nmcp/memory.py` (update recall() to use new algorithm)
- Tests: `tests/test_custom_search.py`
- Example: Adding a new ranking algorithm would create an Index class and integrate via fusion.py

**New MCP Tool:**
- Definition: `daem0nmcp/server.py` (add @mcp.tool() decorated async function)
- Helper functions: Extract to separate module if >50 lines
- Covenant enforcement: Add to COMMUNION_REQUIRED_TOOLS or COUNSEL_REQUIRED_TOOLS sets in covenant.py
- Tests: `tests/test_server.py` (add test for new tool)
- Example: `remember_batch()` at line 694 in server.py

**New Similarity/Ranking Engine:**
- Core algorithm: `daem0nmcp/new_ranking.py` (create Index class)
- Fusion integration: Update `daem0nmcp/fusion.py` to accept new ranker
- Memory integration: `daem0nmcp/memory.py` (update recall() to optionally use new ranker)
- Tests: `tests/test_new_ranking.py`

**New Specialized Component:**
- Location: `daem0nmcp/new_feature.py` (e.g., `communities.py`, `active_context.py`)
- Memory integration: Add helper methods in MemoryManager if needed
- Server integration: Add MCP tools in server.py if client-facing
- Tests: `tests/test_new_feature.py`

**New CLI Command:**
- Definition: `daem0nmcp/cli.py` (add async function, register in argument parser)
- Database/manager initialization: Use async context managers
- Async handling: Use `asyncio.run()` for CLI invocation
- Tests: `tests/test_cli.py`
- Example: `scan_todos()` function in cli.py handles --auto-remember flag

**New Notification Channel:**
- Implementation: `daem0nmcp/channels/new_channel.py` (create channel class)
- Watcher integration: `daem0nmcp/watcher.py` (add channel to notifier)
- Configuration: Add settings in config.py (e.g., watcher_new_channel_enabled)
- Tests: `tests/test_channels.py`

**New Test Suite:**
- File: `tests/test_new_component.py`
- Fixtures: Use conftest.py fixtures (temp_db_path, async_session_factory)
- Async tests: Use @pytest.mark.asyncio or auto-asyncio mode
- Coverage: Aim for 80%+ coverage on new code

**Schema Extensions:**
- Model definition: Add to `daem0nmcp/models.py` (new Base class)
- Migration: Auto-applies on next database init
- Backfill: Add script in `daem0nmcp/migrations/migrate_*.py` if needed
- Tests: Update schema tests in `tests/test_models.py`

## Special Directories

**daem0nmcp/.daem0nmcp/storage/:**
- Purpose: Project-level storage directory (created per project)
- Generated: Yes (auto-created on first use)
- Committed: No (git-ignored, project-specific)
- Contents:
  - `daem0nmcp.db`: SQLite database with memories, rules, entities
  - `qdrant/`: Local Qdrant vector store (if using local vectors)
  - `watcher.log`: JSON-lines file with file change events
  - `editor-poll.json`: Current file watch status for IDE polling

**tests/.test_tmp/:**
- Purpose: Temporary directory for test databases and artifacts
- Generated: Yes (created by pytest)
- Committed: No (git-ignored)
- Contents: Per-test SQLite databases, temp files, log output

**daem0nmcp/__pycache__/:**
- Purpose: Python bytecode cache
- Generated: Yes (auto-generated by Python interpreter)
- Committed: No (git-ignored)

**hooks/ (deprecated, now in daem0nmcp/):**
- Purpose: Legacy pre-commit hook scripts (no longer used)
- Generated: No
- Committed: Yes (for reference, but functionality moved to daem0nmcp/enforcement.py)

---

*Structure analysis: 2026-01-22*
