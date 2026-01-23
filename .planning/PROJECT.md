# Daem0n-MCP v4.0: Cognitive Architecture

## What This Is

Daem0n-MCP is an AI memory system that grants Claude persistent memory, decision tracking, and covenant-enforced workflows via MCP tools. Currently at v3.1.0 as a "Reactive Semantic Engine," this milestone evolves it into a full **Cognitive Architecture** capable of structural reasoning, temporal understanding, and self-correction.

## Core Value

**Claude can remember, learn from outcomes, and maintain coherent understanding across sessions and projects.**

Everything else can fail; this must work. The enhancements expand *how* Claude remembers and reasons, but the core promise remains: persistent, intelligent memory.

## Requirements

### Validated

Existing v3.1.0 capabilities (shipped and working):

- ✓ Memory CRUD with semantic search — existing
- ✓ Hybrid retrieval (BM25 + vector) — existing
- ✓ Sacred Covenant enforcement (communion, counsel) — existing
- ✓ Decision/outcome tracking with time decay — existing
- ✓ Rule engine with TF-IDF trigger matching — existing
- ✓ File watcher with notification channels — existing
- ✓ Basic community clustering (tag co-occurrence) — existing
- ✓ Memory versioning and relationships — existing
- ✓ Active context (always-hot memories) — existing
- ✓ Context triggers (auto-recall patterns) — existing
- ✓ Code indexing via tree-sitter — existing
- ✓ Pre-commit hook enforcement — existing
- ✓ Multi-project linking — existing

### Active

New capabilities for v4.0 (Cognitive Architecture):

**Phase 1: GraphRAG & Leiden**
- [ ] LLM-based entity/relationship extraction during `remember`
- [ ] NetworkX graph construction for in-memory manipulation
- [ ] Leiden algorithm for hierarchical community detection
- [ ] Global search via recursive community summarization
- [ ] "How has X evolved?" style queries

**Phase 2: Bi-Temporal Knowledge**
- [ ] Dual timestamps: `valid_time` (when happened) vs `transaction_time` (when learned)
- [ ] `happened_at` parameter for backfilling historical knowledge
- [ ] Episodic subgraph (immutable raw interactions)
- [ ] Semantic subgraph (mutable crystallized facts)
- [ ] Temporal query support ("what did we know at time T?")

**Phase 3: Metacognitive Architecture (Reflexion)**
- [ ] Actor-Evaluator-Reflector loop via LangGraph state machine
- [ ] Verbal gradient generation for self-correction
- [ ] `verify_facts` tool for claim validation
- [ ] Chain of Verification (CoVe) intercept on factual claims
- [ ] Mistake internalization before user sees output

**Phase 4: Context Engineering**
- [ ] LLMLingua-2 integration for intelligent compression
- [ ] Token classification by information entropy
- [ ] 3x-6x compression while preserving code syntax/entities
- [ ] Attention sinks (StreamingLLM) for KV cache management
- [ ] Rolling window with preserved system prompt

**Phase 5: Dynamic Agency**
- [ ] Context-aware tool masking via Dynamic FastMCP
- [ ] Automatic tool hiding based on user's current focus
- [ ] Sandboxed `execute_python` tool
- [ ] Rootless container or Wasm isolation (Pyodide/Wasmtime)
- [ ] Universal solver capability

### Out of Scope

- Multi-user/multi-tenant architecture — personal tool, not a platform
- Cloud-hosted vector database migration — Qdrant local works well
- Web UI dashboard — CLI/MCP-first, not a visual product
- Real-time collaboration features — single-user focus
- Mobile/embedded deployment — desktop Python environment assumed

## Context

**Current State:**
- v3.1.0 released with 2026 AI Memory Research enhancements
- ~50 MCP tools exposed via FastMCP 3.0
- Python 3.10+ with SQLite + Qdrant (local) storage
- Active GitHub community with stars and external users

**Theming:**
- Daemon/ritual aesthetic throughout ("Sacred Covenant", "Summon_Daem0n", etc.)
- All documentation and messaging maintains this character
- Theming is part of the project's identity, not just decoration

**Technical Foundation:**
- FastMCP 3.0 for MCP server with middleware support
- SQLAlchemy 2.0 async with SQLite + aiosqlite
- sentence-transformers (all-MiniLM-L6-v2) for embeddings
- Qdrant for vector storage
- rank-bm25 for keyword search
- pytest with 600+ tests

## Constraints

- **Theming**: All new features must maintain daemon/ritual character
- **Backwards Compatibility**: Existing `remember`, `recall`, `check_rules` APIs must not break
- **Python Ecosystem**: Must work with Python 3.10+ on Windows, macOS, Linux
- **Local-First**: No mandatory cloud dependencies; remote options remain optional
- **Test Coverage**: New features require tests; maintain existing test quality

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Phase order: GraphRAG → Bi-Temporal → Reflexion → Context → Agency | Structural reasoning foundation enables later phases | — Pending |
| Leiden over Louvain for community detection | Guarantees well-connected communities, better performance | — Pending |
| LangGraph for Reflexion loop | State machine approach matches Actor-Evaluator-Reflector pattern | — Pending |
| LLMLingua-2 over simple truncation | Information-entropy token classification preserves meaning | — Pending |
| Wasm/Rootless for sandboxing | Security isolation without heavy containerization | — Pending |

---
*Last updated: 2026-01-22 after initialization*
