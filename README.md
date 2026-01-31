# Daem0nMCP

```
        ,     ,
       /(     )\
      |  \   /  |      "I am Daem0n, keeper of memories,
       \  \ /  /        guardian of decisions past..."
        \  Y  /
         \ | /
          \|/
           *
```

**AI Memory & Decision System** - Give AI agents persistent memory and consistent decision-making with *actual* semantic understanding.

## What's New in v6.0.0

### The Thinking Daemon
The daemon awakens to autonomous thought. v6.0 adds four major cognitive capabilities: **Auto-Zoom retrieval routing**, **JIT compression**, **background dreaming**, and three **cognitive tools** for temporal scrying, rule evolution, and adversarial debate — all grounded purely in memory evidence with no LLM dependency.

#### Server Decomposition
The monolithic `server.py` (6,467 lines) has been decomposed into a 149-line composition root plus 15 focused tool modules under `daem0nmcp/tools/`. Legacy individual tools are removed from MCP registration — all capabilities flow through 8 workflow tools plus 3 new cognitive tools.

#### Auto-Zoom Retrieval Router
Query-aware search dispatch routes queries to the optimal retrieval strategy:
- **SIMPLE queries** (e.g., "auth") → vector-only search via Qdrant (fast path)
- **MEDIUM queries** → hybrid BM25+vector with RRF fusion (baseline)
- **COMPLEX queries** (e.g., "trace auth flow through all components") → GraphRAG multi-hop + community summaries
- **Shadow mode** (default): logs classifications without changing behavior
- **Safety guarantees**: all strategies fall back to hybrid on any failure

#### JIT Compression
Automatic compression of retrieval results when token counts exceed tiered thresholds:
- **Soft (>4K tokens)**: ~2x compression
- **Hard (>8K tokens)**: ~3x compression
- **Emergency (>16K tokens)**: ~5x compression
- Code syntax and entity names preserved during compression
- Compression metadata returned for observability

#### Background Dreaming
The daemon thinks during idle periods:
- **Idle detection**: triggers after 60 seconds of inactivity
- **FailedDecisionReview**: re-evaluates `worked=False` decisions against current evidence
- **Cooperative yielding**: immediately suspends when user returns
- **Dream insights**: persisted as learning memories with full provenance
- **Configurable**: `DAEM0NMCP_DREAM_ENABLED`, `DAEM0NMCP_DREAM_IDLE_TIMEOUT`

#### Cognitive Tools (3 New MCP Tools)
Three standalone reasoning tools grounded entirely in memory evidence:

| Tool | Purpose |
|------|---------|
| `simulate_decision` | Temporal scrying — replay a past decision with current knowledge, revealing what is now known that wasn't known then |
| `evolve_rule` | Rule entropy analysis — detect rule drift by cross-referencing triggers against code index and outcome history |
| `debate_internal` | Adversarial council — structured advocate/challenger debate with convergence detection, consensus inscribed as memory |

#### Code-Augmented Reflexion
The Reflexion loop now includes code verification:
- Generates Python assertion code for verifiable claims
- Classifies failures (assertion, syntax, import, timeout, sandbox)
- Template fallback when LLM unavailable
- Failure types inform reflection strategy

### New Configuration Options (v6.0.0)
| Variable | Default | Description |
|----------|---------|-------------|
| `DAEM0NMCP_AUTO_ZOOM_ENABLED` | `false` | Enable active query-aware routing |
| `DAEM0NMCP_AUTO_ZOOM_SHADOW` | `true` | Log classifications without routing |
| `DAEM0NMCP_AUTO_ZOOM_CONFIDENCE_THRESHOLD` | `0.25` | Confidence floor for classification |
| `DAEM0NMCP_AUTO_ZOOM_GRAPH_EXPANSION_DEPTH` | `2` | Multi-hop depth for complex queries |
| `DAEM0NMCP_DREAM_ENABLED` | `true` | Enable background dreaming |
| `DAEM0NMCP_DREAM_IDLE_TIMEOUT` | `60.0` | Seconds before dreaming starts |
| `DAEM0NMCP_DREAM_MAX_DECISIONS_PER_SESSION` | `5` | Max decisions to review per idle session |
| `DAEM0NMCP_DREAM_MIN_DECISION_AGE_HOURS` | `1` | Min age before re-evaluation |
| `DAEM0NMCP_COGNITIVE_DEBATE_MAX_ROUNDS` | `5` | Max debate rounds |
| `DAEM0NMCP_COGNITIVE_DEBATE_CONVERGENCE_THRESHOLD` | `0.05` | Position stabilization threshold |
| `DAEM0NMCP_COGNITIVE_EVOLVE_MAX_RULES` | `10` | Max rules analyzed per session |

### Stats
- **11 MCP tools** (8 workflows + 3 cognitive)
- **63 total actions** across all tools
- **740+ tests** passing
- **Server decomposed** from 6,467 lines → 149-line root + 15 modules

---

## What's New in v5.1.0

### Workflow Consolidation
The daemon speaks fewer words but with greater power. v5.1 consolidates **67 individual MCP tools into 8 workflow-oriented tools**, dramatically reducing context overhead for AI agents while preserving all capabilities.

### Stats
- **8 workflow tools** (consolidating 67 individual tools)
- **60 total actions** across all workflows
- **500+ tests** passing

---

## What's New in v5.0.0

### Visions of the Void
The daemon gains sight. v5.0 brings daemon knowledge into the visual realm through **MCP Apps (SEP-1865)** — interactive HTML UIs for exploring memories, graphs, communities, and covenant status.

#### MCP Apps Integration
Six interactive visual portals accessible from MCP-Apps-enabled hosts:

| Portal | Description |
|--------|-------------|
| **Search Results UI** | Card-based recall results with filters, relevance bars, score breakdowns, Record Outcome buttons |
| **Briefing Dashboard** | Collapsible accordion with stats, recent decisions, warnings, focus areas, git changes |
| **Covenant Status Dashboard** | Visual state machine showing Sacred Covenant phases with token countdown timer |
| **Community Cluster Map** | D3 treemap visualization with click-to-drill-down hierarchy and breadcrumb navigation |
| **Memory Graph Viewer** | Canvas-based force-directed graph supporting 10,000+ nodes at 60fps, community hulls, path animation, temporal slider |
| **Real-Time Updates** | Notification badges when daemon knowledge changes via host-mediated polling |

#### Self-Contained Infrastructure
- **D3.js Bundle**: 105KB self-contained bundle via esbuild (no CDN dependencies)
- **CSP Security**: Restrictive Content Security Policy (`default-src 'none'`)
- **SecureMessenger**: Origin-validated iframe communication (O(1) exact matching)
- **Text Fallback**: All tools work on non-MCP-Apps hosts with formatted text output

#### New Visual Tools (v5.0)
| Tool | Purpose |
|------|---------|
| `recall_visual` | Search results with UI resource hint |
| `get_briefing_visual` | Briefing dashboard with UI resource hint |
| `get_covenant_status_visual` | Covenant status with UI resource hint |
| `list_communities_visual` | Community map with UI resource hint |
| `get_graph_visual` | Memory graph with UI resource hint |
| `check_for_updates` | Host-mediated polling for real-time notifications |

### Stats
- **66 MCP tools** (up from 60)
- **500+ tests** passing
- **51,929 lines** of Python
- **48 requirements** satisfied for v5.0

---

## What's New in v4.0.0

### Cognitive Architecture
The daemon awakens to full cognition. v4.0 transforms Daem0n-MCP from a reactive semantic engine into a complete **Cognitive Architecture** with five major capabilities:

#### GraphRAG & Leiden Communities
Knowledge graph construction with hierarchical community detection:
- **Entity extraction**: Automatically extracts entities and relationships during `remember` operations
- **NetworkX graph**: In-memory graph manipulation with directed edges
- **Leiden algorithm**: Hierarchical community detection (replaces basic tag clustering)
- **Multi-hop queries**: `trace_chain`, `trace_evolution`, `get_related_memories` MCP tools
- **Global search**: `recall_hierarchical` uses community summaries for high-level queries

#### Bi-Temporal Knowledge
Track what was true vs when you learned it:
- **Dual timestamps**: `valid_time` (when happened) and `transaction_time` (when learned)
- **`happened_at` parameter**: Backfill historical knowledge with accurate timestamps
- **Point-in-time queries**: `as_of_time` parameter for "what did we know then?" queries
- **Knowledge evolution**: `trace_evolution` shows how understanding changed over time
- **Contradiction detection**: Identifies when new facts invalidate existing beliefs

#### Metacognitive Architecture (Reflexion)
Self-correction before speaking:
- **Actor-Evaluator-Reflector loop**: LangGraph state machine for iterative refinement
- **`verify_facts` tool**: Validates claims against stored knowledge before output
- **Chain of Verification**: Intercepts factual claims for grounding verification
- **Reflection persistence**: Stores self-critiques as retrievable memories
- **Episodic-to-semantic consolidation**: Automatic memory summarization

#### Context Engineering
Intelligent context compression:
- **LLMLingua-2 integration**: 3x-6x compression while preserving meaning
- **Code entity preservation**: Protects function signatures, variable names, syntax
- **Adaptive compression**: Rates adjust based on content type (code vs narrative)
- **Hierarchical compression**: Leverages Leiden community summaries
- **`compress_context` tool**: On-demand context optimization

#### Dynamic Agency
Context-aware tool control:
- **Ritual phase tracking**: BRIEFING -> EXPLORATION -> ACTION -> REFLECTION
- **Tool masking**: Hides irrelevant tools based on current phase
- **`execute_python` tool**: Sandboxed code execution via E2B Firecracker microVMs
- **Capability scoping**: Least-privilege access enforcement
- **Security logging**: All sandbox activity logged for anomaly detection

### New Tools (v4.0)
| Tool | Purpose |
|------|---------|
| `verify_facts` | Validate claims against stored knowledge |
| `compress_context` | LLMLingua-2 context compression |
| `execute_python` | Sandboxed Python code execution |
| `trace_chain` | Multi-hop graph traversal |
| `trace_evolution` | Knowledge evolution tracking |
| `get_related_memories` | Entity relationship discovery |
| `get_graph_stats` | Knowledge graph metrics |

### Stats
- **60 MCP tools** (up from 53)
- **500+ tests** passing
- **48,554 lines** of Python
- **32 requirements** satisfied

---

## What's New in v3.1.0

### 2026 AI Memory Research Enhancements
Seven cutting-edge enhancements from 2026 AI memory research to improve retrieval precision, memory efficiency, and context utilization:

#### BM25 + RRF Hybrid Retrieval
Replaces TF-IDF with Okapi BM25 for better keyword matching, combined with Reciprocal Rank Fusion for hybrid search:
- **BM25 Index**: Better term frequency saturation (k1=1.5) and document length normalization (b=0.75)
- **RRF Fusion**: Combines BM25 and vector results with k=60 dampening constant
- **Configurable**: `DAEM0NMCP_BM25_K1`, `DAEM0NMCP_BM25_B`, `DAEM0NMCP_RRF_K`

#### TiMem-Style Recall Planner
Complexity-aware retrieval that adapts to query difficulty:
- **Simple queries** (e.g., "auth"): Returns community summaries only (~50% context reduction)
- **Medium queries**: Summaries + key raw memories
- **Complex queries** (e.g., "trace auth flow through all components"): Full raw memory access
- **Configurable limits**: `DAEM0NMCP_RECALL_SIMPLE_MAX_MEMORIES`, `DAEM0NMCP_RECALL_MEDIUM_MAX_MEMORIES`, `DAEM0NMCP_RECALL_COMPLEX_MAX_MEMORIES`

#### Titans-Inspired Surprise Scoring
Novelty detection for memory prioritization:
- **`surprise_score`** field on memories (0.0-1.0)
- High surprise = novel information to prioritize
- Low surprise = routine, can be deprioritized
- Uses k-nearest neighbor distance metric
- **Configurable**: `DAEM0NMCP_SURPRISE_K_NEAREST`, `DAEM0NMCP_SURPRISE_BOOST_THRESHOLD`

#### Importance-Weighted Learning
EWC-inspired protection for valuable memories:
- **`importance_score`** field on memories (0.0-1.0)
- High importance = protected from decay/pruning
- Based on: recall frequency, positive outcomes, user interactions

#### Fact Model (Static Memory Separation)
Engram-inspired separation of verified facts from dynamic memories:
- **`Fact`** model for immutable, verified knowledge
- Content hash for O(1) lookup instead of semantic search
- Verification count and promotion threshold
- **Configurable**: `DAEM0NMCP_FACT_PROMOTION_THRESHOLD`

#### Tool Search Index
Dynamic tool discovery to reduce context bloat:
- Register tools with metadata (name, description, category, tags)
- Search by natural language query
- Only load relevant tools into context
- Expected context savings: 85% for large tool libraries

#### Prompt Template System
AutoPDL-inspired modular prompts:
- Structured templates with sections (role, context, task, constraints)
- Variable substitution with `{placeholder}` syntax
- Optional sections and importance weights
- A/B testing support via `PromptVariant`

### New Configuration Options (v3.1.0)
| Variable | Default | Description |
|----------|---------|-------------|
| `DAEM0NMCP_BM25_K1` | `1.5` | BM25 term frequency saturation |
| `DAEM0NMCP_BM25_B` | `0.75` | BM25 document length normalization |
| `DAEM0NMCP_RRF_K` | `60` | RRF fusion dampening constant |
| `DAEM0NMCP_SURPRISE_K_NEAREST` | `5` | Neighbors for surprise calculation |
| `DAEM0NMCP_SURPRISE_BOOST_THRESHOLD` | `0.7` | Boost memories above this surprise |
| `DAEM0NMCP_RECALL_SIMPLE_MAX_MEMORIES` | `5` | Max memories for simple queries |
| `DAEM0NMCP_RECALL_MEDIUM_MAX_MEMORIES` | `10` | Max memories for medium queries |
| `DAEM0NMCP_RECALL_COMPLEX_MAX_MEMORIES` | `20` | Max memories for complex queries |
| `DAEM0NMCP_FACT_PROMOTION_THRESHOLD` | `3` | Successful outcomes to promote to fact |

---

## What's New in v3.0.0

### FastMCP 3.0 Upgrade
Daem0n-MCP now runs on FastMCP 3.0, bringing modern middleware architecture:

- **CovenantMiddleware**: Sacred Covenant enforcement via FastMCP 3.0 middleware pattern
  - Intercepts tool calls at the MCP protocol layer
  - Works alongside existing decorators (belt and suspenders)
  - Automatic enforcement without per-tool decoration

- **Component Versioning**: All 53 MCP tools now include version metadata
  - Enables safe API evolution and deprecation tracking
  - Tools report `version="3.0.0"` in their metadata

- **OpenTelemetry Tracing** (Optional): Built-in observability support
  - Install with: `pip install daem0nmcp[tracing]`
  - Enable with: `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317`

### Breaking Changes
- **Import path changed**: FastMCP 3.0 uses `from fastmcp import FastMCP` (was `from mcp.server.fastmcp`)
- **Decorators deprecated**: `@requires_communion` and `@requires_counsel` now emit deprecation warnings
  - CovenantMiddleware handles enforcement automatically
  - Decorators still work but will be removed in a future version

### Migration
Upgrading from v2.x is straightforward:
```bash
cd ~/Daem0nMCP && git pull && pip install -e .
```
Database migrations run automatically. No manual steps required.

## What's New in v2.16.0

### Sacred Covenant Enforcement
The Sacred Covenant is now **enforced**, not just advisory:

- **`requires_communion`**: Tools block with `COMMUNION_REQUIRED` until `get_briefing()` is called
- **`requires_counsel`**: Mutating tools block with `COUNSEL_REQUIRED` until `context_check()` is called
- **Preflight tokens**: `context_check()` returns a cryptographic token valid for 5 minutes
- **Remedies**: Each block includes the exact tool call needed to fix it

**Affected tools:**
- Communion required: `remember`, `remember_batch`, `add_rule`, `update_rule`, `record_outcome`, `link_memories`, `pin_memory`, `archive_memory`, `prune_memories`, `cleanup_memories`, `compact_memories`, `recall`, `recall_for_file`, `search_memories`, `find_code`, `analyze_impact`
- Counsel required (in addition to communion): `remember`, `remember_batch`, `add_rule`, `update_rule`
- Exempt (entry points only): `get_briefing`, `context_check`, `health`

### MCP Resources (Dynamic Context Injection)
Resources that Claude Desktop/Code can subscribe to for automatic context:

| Resource URI | Content |
|-------------|---------|
| `daem0n://warnings/{project_path}` | All active warnings |
| `daem0n://failed/{project_path}` | Failed approaches to avoid |
| `daem0n://rules/{project_path}` | All configured rules |
| `daem0n://context/{project_path}` | Combined context (warnings + failed + rules) |
| `daem0n://triggered/{file_path}` | Auto-recalled context for a file |

### Claude Code 2.1.3 Compatibility
- Fixed `daem0n_pre_edit_hook.py` to use MCP HTTP instead of removed `check-triggers` CLI command
- Hooks now communicate directly with MCP server for context triggers

## What's New in v2.15.0

### Iteration 1: Search Quality
- **Configurable hybrid weight**: `DAEM0NMCP_HYBRID_VECTOR_WEIGHT` (0.0-1.0)
- **Result diversity**: `DAEM0NMCP_SEARCH_DIVERSITY_MAX_PER_FILE` limits same-file results
- **Tag inference**: Auto-adds `bugfix`, `tech-debt`, `perf`, `warning` tags

### Iteration 2: Code Entity Fidelity
- **Qualified names**: Entities have `module.Class.method` identifiers
- **Stable IDs**: Line changes don't invalidate entity IDs
- **Import extraction**: Files track their imports for dependency analysis

### Iteration 3: Incremental Indexing
- **File hash tracking**: Only re-parses changed files
- **`index_file_if_changed()`**: Efficient single-file re-indexing
- **FileHash model**: Persists content hashes

### Iteration 4: Performance & UX
- **Parse tree caching**: Avoids re-parsing unchanged files
- **Extended config**: `embedding_model`, `parse_tree_cache_maxsize`
- **Enhanced health**: Code index stats, staleness detection

## What's New in v2.14.0

### Active Working Context (MemGPT-style)
Always-hot memory layer that keeps critical information front and center:
- `set_active_context(memory_id)` - Pin critical memories to active context
- `get_active_context()` - Get all hot memories for current focus
- `remove_from_active_context(memory_id)` - Remove from hot context
- `clear_active_context()` - Clear all hot memories
- Auto-included in `get_briefing()` responses
- Failed decisions auto-activate with high priority
- Max 10 items to prevent context bloat

### Temporal Versioning
Track how memories evolve over time:
- Auto-creates versions on memory creation, outcome recording, relationship changes
- `get_memory_versions(memory_id)` - Get full version history
- `get_memory_at_time(memory_id, timestamp)` - Query historical state
- Enables questions like "What did we believe about X last month?"

### Hierarchical Summarization
GraphRAG-style community detection and layered recall:
- `rebuild_communities()` - Detect clusters by tag co-occurrence
- `list_communities()` - Get summaries for high-level overview
- `get_community_details(id)` - Drill down to member memories
- `recall_hierarchical(topic)` - Layered retrieval: summaries then details
- Auto-generated community names from dominant tags

### Auto Entity Extraction (Cognee-style)
Auto-extract and link code entities from memory content:
- Auto-extracts functions, classes, files, concepts from memories on `remember()`
- `recall_by_entity(name)` - Get all memories mentioning an entity
- `list_entities()` - Most frequently mentioned entities
- `backfill_entities()` - Extract entities from existing memories
- Enables queries like "show everything about UserService"

### Contextual Recall Triggers (Knowledge Graph MCP-style)
Auto-recall memories without explicit calls based on context patterns:
- `add_context_trigger(pattern, topic)` - Define auto-recall rules
- `check_context_triggers(file_path)` - Get triggered context
- `list_context_triggers()` / `remove_context_trigger(id)`
- Supports file patterns, tag matching, entity matching
- Integrated with pre-edit hooks for automatic injection
- MCP Resource: `daem0n://triggered/{file_path}`

## What's New in v2.13.0

- **Passive Capture (Auto-Remember)**: Memories without manual calls
  - Pre-edit hook: Auto-recalls memories for files being modified
  - Post-edit hook: Suggests remember() for significant changes
  - Stop hook: Auto-extracts decisions from Claude's responses
  - CLI `remember` command for hook integration
  - See `hooks/settings.json.example` for configuration

## What's New in v2.12.0

- **Endless Mode (Context Compression)**: Reduce token usage by 50-75%
  - `recall(topic, condensed=True)` - Returns compressed memories
  - Strips rationale, context fields; truncates content to 150 chars
  - Focus areas in briefings use condensed mode automatically
  - Inspired by memvid-mind's token efficiency approach

## What's New in v2.11.0

- **Linked Projects (Multi-Repo Support)**: Work across related repositories
  - Link client/server or other related repos for cross-awareness
  - `link_projects()` / `unlink_projects()` / `list_linked_projects()`
  - `recall(include_linked=True)` - Search across linked repos
  - `consolidate_linked_databases()` - Merge child DBs into unified parent
  - `get_briefing()` now shows linked project warnings/stats
  - See `docs/multi-repo-setup.md` for full guide
  - New skill: `summon_daem0n` for project setup guidance

### Previous Features (v2.10.0)

- **Code Understanding Layer (Phase 2)**: The Daem0n now understands your code structure
  - Multi-language AST parsing via `tree-sitter-language-pack`
  - Supports: Python, TypeScript, JavaScript, Go, Rust, Java, C, C++, C#, Ruby, PHP
  - Extracts: classes, functions, methods, signatures, docstrings
  - New MCP tools:
    - `index_project` - Index code entities for understanding
    - `find_code` - Semantic search across code entities
    - `analyze_impact` - Analyze what changing an entity would affect
  - CLI: `python -m daem0nmcp.cli index`
  - New models: `CodeEntity`, `MemoryCodeRef`

### Previous Features (v2.9.0)

- **Qdrant Vector Backend (Phase 0)**: Persistent vector storage replaces SQLite blob storage
  - Qdrant local mode (file-based, no server required)
  - Hybrid search: TF-IDF + vector similarity (0.3 weight)
  - Migration script: `python -m daem0nmcp.migrations.migrate_vectors`

- **Proactive File Watcher (Phase 1)**: The Daem0n now watches your files proactively
  - Monitors file changes and notifies when files with associated memories are modified
  - Multi-channel notifications:
    - **System notifications**: Desktop alerts via `plyer`
    - **Log file**: JSON-lines at `.daem0nmcp/storage/watcher.log`
    - **Editor poll**: JSON at `.daem0nmcp/storage/editor-poll.json` for IDE plugins
  - Start with: `python -m daem0nmcp.cli watch`
  - Configurable debouncing, skip patterns, extension filters

### Previous Features (v2.8.0)

- **Automatic Tool Reminders (Stop Hook)**: Claude Code hooks that detect task completion and remind to record outcomes
- **Enhanced SessionStart Hook**: Now reminds to commune with `get_briefing()` at session start
- **Hook Scripts**: New `hooks/` directory with reusable Python scripts for Claude Code integration

### Previous Features (v2.7.0)

- **Pre-Commit Enforcement**: Git hooks that actually block commits when memory discipline is broken
  - Blocks commits with decisions >24h old that lack recorded outcomes
  - Blocks commits modifying files with known failed approaches
  - Warns on recent pending decisions and file warnings
- **CLI Resolution Tools**: New commands to resolve blocking issues
  - `status` - Show pending decisions and what's blocking
  - `record-outcome` - Record outcomes directly from CLI
  - `install-hooks` / `uninstall-hooks` - Manage git hooks
- **Automatic Session Tracking**: `remember()` now auto-tracks decisions as pending

### Previous Features (v2.6.0)

- **Enhanced Bootstrap**: First-run context collection extracts 7 memory categories automatically
- **Smarter Session Start**: `get_briefing()` reports exactly what was ingested

### Previous Features (v2.5.0)
- **Windows HTTP Transport**: Full Windows support via streamable-http (bypasses stdio bugs)
- **Ritual-Themed Installation**: `Summon_Daem0n.md` and `Banish_Daem0n.md` for fun
- **Claude Code Hooks**: Auto-reminders to use memory tools
- **Protocol Skill**: `daem0nmcp-protocol` skill for Superpowers users

### Core Features (v2.1+)
- **TF-IDF Semantic Search**: Real similarity matching, not just keyword overlap
- **Memory Decay**: Recent memories weighted higher than old ones
- **Conflict Detection**: Warns when new decisions contradict past failures
- **Failed Decision Boosting**: Past mistakes surface prominently in recalls
- **File-Level Memories**: Associate memories with specific files
- **Vector Embeddings**: sentence-transformers for enhanced semantic matching

## Why Daem0nMCP?

AI agents start each session fresh. They don't remember:
- What decisions were made and why
- Patterns that should be followed
- Warnings from past mistakes

**Markdown files don't solve this** - the AI has to know to read them and might ignore them.

**Daem0nMCP provides ACTIVE memory** - it surfaces relevant context when the AI asks about a topic, enforces rules before actions, and learns from outcomes.

### What Makes This Different

Unlike keyword-based systems:
- **Semantic matching**: "creating REST endpoint" matches rules about "adding API route"
- **Time decay**: A decision from yesterday matters more than one from 6 months ago
- **Conflict warnings**: "You tried this approach before and it failed"
- **Learning loops**: Record outcomes, and failures get boosted in future recalls

## Quick Start

### The Easy Way (Recommended)

1. Copy `Summon_Daem0n.md` to your project
2. Start a Claude Code session in that project
3. Claude will read the file and perform the summoning ritual automatically

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/DasBluEyedDevil/Daem0n-MCP.git ~/Daem0nMCP

# Install
pip install -e ~/Daem0nMCP

# Run the MCP server (Linux/macOS)
python -m daem0nmcp.server

# Run the MCP server (Windows - use HTTP transport)
python ~/Daem0nMCP/start_server.py --port 9876
```

## Installation by Platform

### Linux / macOS (stdio transport)

```bash
# Find your Python path
python3 -c "import sys; print(sys.executable)"

# Register with Claude Code (replace <PYTHON_PATH>)
claude mcp add daem0nmcp --scope user -- <PYTHON_PATH> -m daem0nmcp.server

# Restart Claude Code
```

### Windows (HTTP transport required)

Windows has a known bug where Python MCP servers using stdio transport hang indefinitely. Use HTTP transport instead:

1. **Start the server** (keep this terminal open):
```bash
python ~/Daem0nMCP/start_server.py --port 9876
```
Or use `start_daem0nmcp_server.bat`

2. **Add to `~/.claude.json`**:
```json
{
  "mcpServers": {
    "daem0nmcp": {
      "type": "http",
      "url": "http://localhost:9876/mcp"
    }
  }
}
```

3. **Start Claude Code** (after server is running)

## MCP Tools (11 Tools, 63 Actions)

As of v6.0, all capabilities are accessed through 8 workflow tools plus 3 cognitive tools. Each workflow tool accepts an `action` parameter to select the operation. Legacy individual tools have been removed from MCP registration.

### `commune` — Session Start & Status

| Action | Purpose |
|--------|---------|
| `briefing` | Smart session start with git awareness (replaces `get_briefing`) |
| `active_context` | Get all hot memories for current focus |
| `triggers` | Check context triggers for auto-recalled memories |
| `health` | Server health, version, and statistics |
| `covenant` | Sacred Covenant status and phase |
| `updates` | Poll for knowledge changes (real-time notifications) |

### `consult` — Pre-Action Intelligence

| Action | Purpose |
|--------|---------|
| `preflight` | Combined recall + rules check (replaces `context_check`) |
| `recall` | Semantic memory retrieval by topic (supports `condensed`, `visual`) |
| `recall_file` | Get memories linked to a specific file |
| `recall_entity` | Get memories mentioning a code entity |
| `recall_hierarchical` | GraphRAG-style layered retrieval |
| `search` | Full-text search across all memories |
| `check_rules` | Validate action against decision rules |
| `compress` | LLMLingua-2 context compression |

### `inscribe` — Memory Writing & Linking

| Action | Purpose |
|--------|---------|
| `remember` | Store a memory with conflict detection |
| `remember_batch` | Store multiple memories in one transaction |
| `link` | Create causal relationships between memories |
| `unlink` | Remove relationships between memories |
| `pin` | Pin/unpin memories to prevent pruning |
| `activate` | Add memory to always-hot working context |
| `deactivate` | Remove memory from active context |
| `clear_active` | Clear all active context |
| `ingest` | Import external documentation from URL |

### `reflect` — Outcomes & Verification

| Action | Purpose |
|--------|---------|
| `outcome` | Record whether a decision worked or failed |
| `verify` | Validate factual claims against stored knowledge |
| `execute` | Sandboxed Python execution (E2B) |

### `understand` — Code Comprehension

| Action | Purpose |
|--------|---------|
| `index` | Index code entities via tree-sitter |
| `find` | Semantic search across code entities |
| `impact` | Analyze blast radius of code changes |
| `todos` | Scan for TODO/FIXME/HACK comments |
| `refactor` | Generate refactor suggestions with causal history |

### `govern` — Rules & Triggers

| Action | Purpose |
|--------|---------|
| `add_rule` | Create decision tree rules |
| `update_rule` | Modify existing rules |
| `list_rules` | Show all configured rules |
| `add_trigger` | Create auto-recall context triggers |
| `list_triggers` | List all context triggers |
| `remove_trigger` | Remove a context trigger |

### `explore` — Graph & Discovery

| Action | Purpose |
|--------|---------|
| `related` | Find related memories via graph traversal |
| `chain` | Find causal paths between memories |
| `graph` | Visualize memory relationships (JSON/Mermaid, supports `visual`) |
| `stats` | Knowledge graph metrics |
| `communities` | List Leiden community clusters (supports `visual`) |
| `community_detail` | Drill down into a community |
| `rebuild_communities` | Detect communities via Leiden algorithm |
| `entities` | List most frequently mentioned entities |
| `backfill_entities` | Extract entities from existing memories |
| `evolution` | Trace knowledge evolution over time |
| `versions` | Get version history for a memory |
| `at_time` | Query memory state at a point in time |

### `maintain` — Housekeeping & Federation

| Action | Purpose |
|--------|---------|
| `prune` | Remove old, low-value memories (with protection) |
| `archive` | Archive/restore memories |
| `cleanup` | Find and merge duplicate memories |
| `compact` | Consolidate episodic memories into summaries |
| `rebuild_index` | Force rebuild TF-IDF and vector indexes |
| `export` | Export all memories and rules as JSON |
| `import_data` | Import memories and rules from JSON |
| `link_project` | Link to another project for cross-repo awareness |
| `unlink_project` | Remove a project link |
| `list_projects` | List all linked projects |
| `consolidate` | Merge memories from linked projects |

### Cognitive Tools (3 Standalone MCP Tools)

| Tool | Purpose |
|------|---------|
| `simulate_decision` | Temporal scrying — reconstruct past decision context vs current knowledge |
| `evolve_rule` | Rule entropy analysis — detect staleness, code drift, and suggest evolution |
| `debate_internal` | Adversarial council — evidence-grounded debate with convergence detection |

### Visual Tools (MCP Apps — accessed via workflow tools)

As of v5.1, these are no longer standalone MCP tools. Visual mode is accessed by passing `visual=True` to the `commune`, `consult`, or `explore` workflow tools. The table below lists the visual capabilities and which workflow action enables them:

| Visual Capability | Access Via |
|-------------------|------------|
| Search results with card-based display | `consult(action="recall", visual=True)` |
| Briefing dashboard with collapsible accordion | `commune(action="briefing", visual=True)` |
| Covenant status with visual state machine | `commune(action="covenant", visual=True)` |
| Community clusters with treemap visualization | `explore(action="communities", visual=True)` |
| Memory graph with force-directed viewer | `explore(action="graph", visual=True)` |
| Real-time update notifications | `commune(action="updates")` |

## Usage Examples

### Store a Memory
```python
inscribe(
    action="remember",
    category="decision",  # decision, pattern, warning, or learning
    content="Use JWT tokens instead of sessions",
    rationale="Need stateless auth for horizontal scaling",
    tags=["auth", "architecture"],
    file_path="src/auth/jwt.py"  # optional file association
)
```

### Retrieve Memories
```python
consult(action="recall", topic="authentication")
# Returns: decisions, patterns, warnings, learnings about auth
# Sorted by: semantic relevance × recency × importance

consult(action="recall_file", file_path="src/auth/jwt.py")
# Returns: all memories linked to this file
```

### Create Rules
```python
govern(
    action="add_rule",
    trigger="adding new API endpoint",
    must_do=["Add rate limiting", "Write integration test"],
    must_not=["Use synchronous database calls"],
    ask_first=["Is this a breaking change?"]
)
```

### Track Outcomes
```python
reflect(action="outcome", memory_id=42, outcome_text="JWT auth works great", worked=True)
reflect(action="outcome", memory_id=43, outcome_text="Caching caused stale data", worked=False)
# Failed decisions get 1.5x boost in future recalls
```

### Session Start
```python
commune(action="briefing", focus_areas=["authentication", "API"])
# First run: Creates 6-7 memories from project structure, README, manifests, etc.
# Returns: stats, recent decisions, warnings, failed approaches,
# git changes, bootstrap summary, plus pre-fetched context for focus areas
```

### Endless Mode (Token Compression)
```python
# Full recall (default) - ~40KB response
consult(action="recall", topic="authentication")

# Condensed recall - ~10KB response (75% smaller)
consult(action="recall", topic="authentication", condensed=True)
# Returns: truncated content, no rationale/context, minimal fields

# Briefings automatically use condensed mode for focus areas
commune(action="briefing", focus_areas=["auth", "database", "api"])
# Focus area results are pre-compressed
```

### Import External Docs
```python
inscribe(action="ingest", url="https://stripe.com/docs/api/charges", topic="stripe")
# Later: consult(action="recall", topic="stripe") to retrieve
```

## AI Agent Protocol

The recommended workflow for AI agents using the 8 workflow tools:

```
SESSION START
    └─> commune(action="briefing")

BEFORE CHANGES
    └─> consult(action="preflight", description="what you're doing")
    └─> consult(action="recall_file", file_path="path/to/file.py")

AFTER DECISIONS
    └─> inscribe(action="remember", category=..., content=..., rationale=..., file_path=...)

AFTER IMPLEMENTATION
    └─> reflect(action="outcome", memory_id=..., outcome_text=..., worked=...)
```

See `Summon_Daem0n.md` for the complete protocol (with ritual theme for fun).

## Claude Code Integration

### Hooks (Auto-Reminders)

Add to `.claude/settings.json`:
```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Edit|Write",
      "hooks": [{
        "type": "command",
        "command": "echo '[Daem0n] Check memories before modifying'"
      }]
    }],
    "PostToolUse": [{
      "matcher": "Edit|Write",
      "hooks": [{
        "type": "command",
        "command": "echo '[Daem0n] Consider calling remember()'"
      }]
    }]
  }
}
```

### Passive Capture Hooks

For fully automatic memory capture, enable all hooks in `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Edit|Write|NotebookEdit",
      "hooks": [{
        "type": "command",
        "command": "python3 \"$HOME/Daem0nMCP/hooks/daem0n_pre_edit_hook.py\""
      }]
    }],
    "PostToolUse": [{
      "matcher": "Edit|Write",
      "hooks": [{
        "type": "command",
        "command": "python3 \"$HOME/Daem0nMCP/hooks/daem0n_post_edit_hook.py\""
      }]
    }],
    "Stop": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python3 \"$HOME/Daem0nMCP/hooks/daem0n_stop_hook.py\""
      }]
    }]
  }
}
```

**What each hook does:**
- **Pre-edit**: Shows warnings, patterns, and past decisions for files before you modify them
- **Post-edit**: Suggests calling `remember()` when you make significant changes
- **Stop**: Auto-extracts decisions from Claude's responses and creates memories

### Protocol Skill

For Superpowers users, a skill is included at `.claude/skills/daem0nmcp-protocol/SKILL.md` that enforces the memory protocol.

## How It Works

### TF-IDF Similarity
Instead of simple keyword matching, Daem0nMCP builds TF-IDF vectors for all stored memories and queries. This means:
- "authentication" matches memories about "auth", "login", "OAuth"
- Rare terms (like project-specific names) get higher weight
- Common words are automatically de-emphasized

### Memory Decay
```
weight = e^(-λt) where λ = ln(2)/half_life_days
```
Default half-life is 30 days. A 60-day-old memory has ~25% weight.
Patterns and warnings are permanent (no decay).

### Conflict Detection
When storing a new memory, it's compared against recent memories:
- If similar content failed before → warning about the failure
- If it matches an existing warning → warning surfaced
- If highly similar content exists → potential duplicate flagged

### Failed Decision Boosting
Memories with `worked=False` get a 1.5x relevance boost in recalls.
Warnings get a 1.2x boost. This ensures past mistakes surface prominently.

## Data Storage

Each project gets isolated storage at:
```
<project_root>/.daem0nmcp/storage/daem0nmcp.db
```

### Legacy Migration
If upgrading from DevilMCP, data is automatically migrated from `.devilmcp/` to `.daem0nmcp/`.

## Configuration

Environment variables (prefix: `DAEM0NMCP_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DAEM0NMCP_PROJECT_ROOT` | `.` | Project root path |
| `DAEM0NMCP_STORAGE_PATH` | auto | Override storage location |
| `DAEM0NMCP_LOG_LEVEL` | `INFO` | Logging level |
| `DAEM0NMCP_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformer model for embeddings |
| `DAEM0NMCP_HYBRID_VECTOR_WEIGHT` | `0.3` | Vector vs BM25 weight (0.0–1.0) |
| `DAEM0NMCP_QDRANT_PATH` | auto | Path for local Qdrant storage |
| `DAEM0NMCP_QDRANT_URL` | — | Remote Qdrant URL (overrides local path) |
| `DAEM0NMCP_WATCHER_ENABLED` | `false` | Enable file watcher daemon |

Version-specific configuration options are listed in the [v6.0.0](#new-configuration-options-v600) and [v3.1.0](#new-configuration-options-v310) sections above. See `daem0nmcp/config.py` for the full list of settings.

## Architecture

```
daem0nmcp/
├── server.py           # Composition root (149 lines) — imports & wires 15 tool modules
├── mcp_instance.py     # Shared FastMCP instance
├── context_manager.py  # Multi-project context management
├── memory.py           # Memory storage & semantic retrieval (with Auto-Zoom integration)
├── tools/              # 15 decomposed tool modules (v6.0)
│   ├── briefing.py     # Session start, health, covenant, active context
│   ├── memory.py       # Remember, recall, search, link, pin, archive
│   ├── context_tools.py # Preflight, recall_file, recall_entity, triggers
│   ├── code_tools.py   # Index, find, impact, todos, refactor
│   ├── graph_tools.py  # Related, chain, graph, communities, evolution
│   ├── entity_tools.py # Entity listing, backfill
│   ├── rules.py        # Rule CRUD, context triggers
│   ├── verification.py # Outcome recording, fact verification
│   ├── agency_tools.py # Sandboxed code execution
│   ├── maintenance.py  # Prune, cleanup, compact, export/import
│   ├── federation.py   # Link/unlink projects, consolidate
│   ├── temporal.py     # Memory versions, point-in-time queries
│   ├── workflows.py    # 8 workflow tool registrations
│   ├── cognitive_tools.py # 3 cognitive tools (simulate, evolve, debate)
│   └── resources.py    # MCP resource providers
├── cognitive/          # Cognitive reasoning (v6.0 Phase 17)
│   ├── simulate.py     # Temporal scrying — decision replay
│   ├── evolve.py       # Rule entropy analysis
│   └── debate.py       # Adversarial council
├── retrieval_router.py # Auto-Zoom query-aware dispatch (v6.0 Phase 15)
├── query_classifier.py # ExemplarQueryClassifier (SentenceTransformer-based)
├── compression/        # Context compression
│   ├── jit.py          # JIT compression with tiered thresholds (v6.0 Phase 15)
│   └── hierarchical.py # Hierarchical context management
├── dreaming/           # Background dreaming (v6.0 Phase 16)
│   ├── scheduler.py    # IdleDreamScheduler (idle detection + cooperative yielding)
│   ├── strategies.py   # FailedDecisionReview strategy
│   └── persistence.py  # DreamResult/DreamSession provenance
├── reflexion/          # Metacognitive architecture
│   ├── nodes.py        # Actor, Evaluator, Reflector (LangGraph)
│   ├── code_gen.py     # Verification code generation (v6.0 Phase 14)
│   ├── code_exec.py    # Sandboxed execution with failure classification (v6.0 Phase 14)
│   ├── claims.py       # Claim extraction and classification
│   └── graph.py        # Reflexion graph construction
├── rules.py            # Rule engine with BM25 matching
├── similarity.py       # TF-IDF index, decay, conflict detection
├── vectors.py          # Vector embeddings (sentence-transformers)
├── bm25_index.py       # BM25 Okapi keyword retrieval
├── fusion.py           # Reciprocal Rank Fusion for hybrid search
├── surprise.py         # Titans-inspired novelty detection
├── recall_planner.py   # TiMem-style complexity classification
├── covenant.py         # Sacred Covenant enforcement
├── transforms/         # FastMCP 3.0 transforms
│   └── covenant.py     # CovenantMiddleware
├── channels/           # Notification channels (file watcher)
│   ├── system_notify.py  # Desktop notifications via plyer
│   ├── log_notify.py     # JSON-lines log file channel
│   └── editor_poll.py    # JSON poll file for IDE plugins
├── code_indexer.py     # Code understanding via tree-sitter
├── database.py         # SQLite async database
├── models.py           # 10+ tables
├── config.py           # Pydantic settings (all v6.0 config options)
└── ui/                 # MCP Apps visual interfaces
    ├── build/          # D3.js bundle (105KB, no CDN)
    ├── static/         # SecureMessenger, shared JS
    └── templates/      # 6 HTML portals

Summon_Daem0n.md   # Installation & upgrade instructions (ritual theme)
Banish_Daem0n.md   # Uninstallation instructions
start_server.py    # HTTP server launcher (Windows)
```

## CLI Commands

```bash
# Check a file against memories and rules
python -m daem0nmcp.cli check <filepath>

# Get session briefing/statistics
python -m daem0nmcp.cli briefing

# Scan for TODO/FIXME/HACK comments
python -m daem0nmcp.cli scan-todos [--auto-remember] [--path PATH]

# Index code entities (Phase 2)
python -m daem0nmcp.cli index [--path PATH] [--patterns **/*.py **/*.ts ...]

# Run database migrations (usually automatic)
python -m daem0nmcp.cli migrate [--backfill-vectors]
```

### Enforcement Commands

```bash
# Check staged files (used by pre-commit hook)
python -m daem0nmcp.cli pre-commit [--interactive]

# Show pending decisions and blocking issues
python -m daem0nmcp.cli status

# Record outcome for a decision
python -m daem0nmcp.cli record-outcome <id> "<outcome>" --worked|--failed

# Install git hooks
python -m daem0nmcp.cli install-hooks [--force]

# Remove git hooks
python -m daem0nmcp.cli uninstall-hooks
```

All commands support `--json` for machine-readable output and `--project-path` to specify the project root.

## Upgrading

Upgrading Daem0n-MCP is straightforward:

### 1. Update the Code

```bash
# If installed from source (recommended)
cd ~/Daem0nMCP && git pull && pip install -e .

# If installed via pip
pip install --upgrade daem0nmcp
```

**Important:** The `pip install -e .` step is required to install all dependencies:
- `qdrant-client` - Vector database for semantic search
- `watchdog` - File watching for proactive notifications
- `plyer` - Desktop notifications
- `tree-sitter-language-pack` - Multi-language code parsing (Python 3.14 compatible)

All dependencies are required for full functionality.

### 2. Restart Claude Code

After updating, restart Claude Code to load the new MCP tools.

### 3. Migrations Run Automatically

Database migrations are applied automatically when any MCP tool runs. The first time you use `get_briefing()`, `remember()`, or any other tool after upgrading, the database schema is updated.

No manual migration step required.

### 4. Install Enforcement Hooks

Pre-commit hooks block commits when decisions lack outcomes:

```bash
python -m daem0nmcp.cli install-hooks
```

### 5. Index Your Codebase

Enable code understanding by indexing your project:

```bash
python -m daem0nmcp.cli index
```

This parses your code with tree-sitter (supports Python, TypeScript, JavaScript, Go, Rust, Java, C, C++, C#, Ruby, PHP) and enables semantic code search via `find_code()` and impact analysis via `analyze_impact()`.

## Troubleshooting

### MCP Tools Not Available in Claude Session

**Symptom:** `claude mcp list` shows daem0nmcp connected, but Claude can't use `mcp__daem0nmcp__*` tools.

**Cause:** Known Claude Code bug ([#2682](https://github.com/anthropics/claude-code/issues/2682)) where MCP tools are discovered but not injected into Claude's toolbox.

**Fixes:**

1. **Start server before Claude Code:**
   ```bash
   # Terminal 1: Start Daem0n server first
   python ~/Daem0nMCP/start_server.py --port 9876

   # Wait for "Uvicorn running on http://localhost:9876"

   # Terminal 2: Then start Claude Code
   claude
   ```

2. **Re-register the server:**
   ```bash
   claude mcp remove daem0nmcp -s user
   claude mcp add daem0nmcp http://localhost:9876/mcp -s user
   ```

3. **Verify tools are available:**
   - Claude should show `mcp__daem0nmcp__*` tools in its toolbox
   - If Claude tries `claude mcp call` bash commands instead, the tools aren't injected

### Hooks Not Firing

**Symptom:** Pre-edit hooks don't show Daem0n context.

**Check:**
1. MCP server running: `curl http://localhost:9876/mcp` should respond
2. Hooks configured in `.claude/settings.json`
3. Project has `.daem0nmcp/` directory

## Development

```bash
# Install in development mode
pip install -e .

# Run tests (740+ tests)
pytest tests/ -v --asyncio-mode=auto

# Lint
ruff check daem0nmcp/ tests/

# Run server directly
python -m daem0nmcp.server

# Run HTTP server (Windows)
python start_server.py --port 9876
```

## Support

If Daem0nMCP has been useful to you, consider supporting its development:

[![Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/vitruvianredux)

## Uninstallation

See `Banish_Daem0n.md` for complete removal instructions, or quick version:

```bash
# Remove MCP registration
claude mcp remove daem0nmcp --scope user

# Uninstall package
pip uninstall daem0nmcp

# Remove repository
rm -rf ~/Daem0nMCP

# Remove project data (optional)
rm -rf .daem0nmcp/
```

---

```
    "The system learns from YOUR outcomes.
     Record them faithfully..."
                              ~ Daem0n
```

*Daem0nMCP v6.0.0: The Thinking Daemon — Auto-Zoom retrieval routing, JIT compression, background dreaming, and 3 cognitive tools (temporal scrying, rule evolution, adversarial debate). Server decomposed from 6,467 lines to 149-line composition root + 15 modules. 11 MCP tools (8 workflows + 3 cognitive), 63 actions. 740+ tests. The daemon now thinks while you rest.*
