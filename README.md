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

## What's New in v6.6.6

### ModernBERT Deep Sight (BREAKING)
The daemon's vision has been fundamentally sharpened. The old `all-MiniLM-L6-v2` embedding model is replaced by **ModernBERT** with asymmetric query/document encoding and optional ONNX acceleration.

| Aspect | Old (v5.x) | New (v6.6.6) |
|--------|------------|--------------|
| **Model** | `all-MiniLM-L6-v2` | `nomic-ai/modernbert-embed-base` |
| **Dimensions** | 384 | 256 (Matryoshka truncation) |
| **Encoding** | Single `encode()` | Dual: `encode_query()` / `encode_document()` |
| **Backend** | PyTorch only | ONNX quantized (with torch fallback) |
| **Prefixes** | None | `search_query: ` / `search_document: ` |

**This is a BREAKING CHANGE** — existing embeddings must be re-encoded:
```bash
pip install -e ~/Daem0nMCP[onnx]  # Optional ONNX acceleration
python -m daem0nmcp.migrations.migrate_embedding_model --project-path /path/to/.daem0nmcp
```

### Background Dreaming
When the user goes idle, the daemon autonomously re-evaluates past failed decisions using current evidence:
- `IdleDreamScheduler` monitors tool call activity
- After configurable idle timeout (default 60s), `FailedDecisionReview` strategy runs
- Classifies decisions as **revised**, **confirmed_failure**, or **needs_more_data**
- Insights persisted as `learning` memories with `dream` tag and full provenance
- Yields immediately when user returns (cooperative scheduling)

### Cognitive Tools (3 new standalone MCP tools)
Meta-reasoning tools for daemon introspection:

| Tool | Purpose |
|------|---------|
| `simulate_decision` | **Temporal Scrying** — replay a past decision with current knowledge, revealing what changed |
| `evolve_rule` | **Rule Entropy Analysis** — examine rules for staleness, code drift, and outcome correlation |
| `debate_internal` | **Adversarial Council** — structured evidence-grounded debate with convergence detection |

### Auto-Zoom Retrieval Routing
Query-aware search dispatch that routes to the optimal retrieval strategy:
- **SIMPLE** queries → Vector-only search (fast path)
- **MEDIUM** queries → Hybrid BM25+vector with RRF fusion
- **COMPLEX** queries → GraphRAG multi-hop traversal + community summaries
- Shadow mode (default) logs classifications without changing behavior
- All strategies fall back to hybrid on failure

### Claude Code Native Hooks
New `daem0nmcp/claude_hooks/` module with 5 lifecycle hooks and automated installation:
```bash
python -m daem0nmcp.cli install-claude-hooks      # Install to ~/.claude/settings.json
python -m daem0nmcp.cli uninstall-claude-hooks     # Remove
```

| Hook | Purpose |
|------|---------|
| `session_start` | Auto-briefing at session dawn |
| `pre_edit` | Preflight enforcement + file memory recall before edits |
| `pre_bash` | Rule enforcement on bash commands |
| `post_edit` | Suggest remembrance for significant changes |
| `stop` | Auto-capture decisions from conversation |

### Stats
- **8 workflow tools** + **3 cognitive tools** (11 MCP tools total, plus legacy)
- **59 workflow actions** across 8 workflows
- **500+ tests** passing

---

## What's New in v5.1.0

### Workflow Consolidation
v5.1 consolidates **67 individual MCP tools into 8 workflow-oriented tools**, dramatically reducing context overhead for AI agents while preserving all capabilities.

#### 8 Workflow Tools

| Workflow | Purpose | Actions |
|----------|---------|---------|
| **`commune`** | Session start & status | `briefing`, `active_context`, `triggers`, `health`, `covenant`, `updates` |
| **`consult`** | Pre-action intelligence | `preflight`, `recall`, `recall_file`, `recall_entity`, `recall_hierarchical`, `search`, `check_rules`, `compress` |
| **`inscribe`** | Memory writing & linking | `remember`, `remember_batch`, `link`, `unlink`, `pin`, `activate`, `deactivate`, `clear_active`, `ingest` |
| **`reflect`** | Outcomes & verification | `outcome`, `verify`, `execute` |
| **`understand`** | Code comprehension | `index`, `find`, `impact`, `todos`, `refactor` |
| **`govern`** | Rules & triggers | `add_rule`, `update_rule`, `list_rules`, `add_trigger`, `list_triggers`, `remove_trigger` |
| **`explore`** | Graph & discovery | `related`, `chain`, `graph`, `stats`, `communities`, `community_detail`, `rebuild_communities`, `entities`, `backfill_entities`, `evolution`, `versions`, `at_time` |
| **`maintain`** | Housekeeping & federation | `prune`, `archive`, `cleanup`, `compact`, `rebuild_index`, `export`, `import_data`, `link_project`, `unlink_project`, `list_projects`, `consolidate` |

#### How It Works
Each workflow tool accepts an `action` parameter that selects the operation:
```python
# Old way (67 separate tools)
mcp__daem0nmcp__get_briefing(project_path="...")
mcp__daem0nmcp__recall(topic="auth", project_path="...")
mcp__daem0nmcp__remember(category="decision", content="...", project_path="...")
mcp__daem0nmcp__record_outcome(memory_id=42, outcome="...", worked=True, project_path="...")

# New way (8 workflow tools)
mcp__daem0nmcp__commune(action="briefing", project_path="...")
mcp__daem0nmcp__consult(action="recall", topic="auth", project_path="...")
mcp__daem0nmcp__inscribe(action="remember", category="decision", content="...", project_path="...")
mcp__daem0nmcp__reflect(action="outcome", memory_id=42, outcome_text="...", worked=True, project_path="...")
```

#### Why Consolidate?
- **88% fewer tool definitions** in context (8 vs 67)
- **Lower token overhead** — AI agents load fewer tool schemas
- **Logical grouping** — related operations live in one tool
- **Backward compatible** — legacy individual tools still registered alongside workflows

---

## What's New in v5.0.0

### Visions of the Void (MCP Apps)
Interactive HTML interfaces via MCP Apps (SEP-1865). Visual mode is now accessed via the `visual=true` parameter on workflow tools:

```python
commune(action="briefing", visual=true, project_path="...")      # Briefing Dashboard
consult(action="recall", topic="auth", visual=true, project_path="...")  # Search Results UI
commune(action="covenant", visual=true, project_path="...")      # Covenant Status
explore(action="communities", visual=true, project_path="...")   # Community Map
explore(action="graph", topic="auth", visual=true, project_path="...")  # Memory Graph Viewer
```

Features: D3.js v7 bundled (105KB, no CDN), restrictive CSP, canvas-based graph (10,000+ nodes at 60fps), graceful text fallback for non-visual hosts.

---

## What's New in v4.0.0

### Cognitive Architecture
Five major capabilities:

- **GraphRAG & Leiden Communities**: Knowledge graph construction with hierarchical community detection, multi-hop queries, global search via community summaries
- **Bi-Temporal Knowledge**: Dual timestamps (`valid_time` vs `transaction_time`), `happened_at` backfilling, `as_of_time` point-in-time queries, contradiction detection
- **Metacognitive Reflexion**: Actor-Evaluator-Reflector loop, `verify` action validates claims against stored knowledge, reflection persistence
- **Context Engineering**: LLMLingua-2 for 3x-6x compression, code entity preservation, adaptive rates, `compress` action for on-demand optimization
- **Dynamic Agency**: `execute` action for sandboxed Python execution via E2B Firecracker microVMs

---

## What's New in v3.1.0

### 2026 AI Memory Research Enhancements
- **BM25 + RRF Hybrid Retrieval**: Okapi BM25 replaces TF-IDF, Reciprocal Rank Fusion combines keyword and vector search
- **TiMem-Style Recall Planner**: Complexity-aware retrieval adapting to query difficulty (simple/medium/complex)
- **Titans-Inspired Surprise Scoring**: Novelty detection with `surprise_score` (0.0-1.0)
- **Importance-Weighted Learning**: EWC-inspired protection for valuable memories via `importance_score`
- **Fact Model**: Verified facts promote to immutable O(1) lookup after threshold successful outcomes

---

## What's New in v3.0.0

### FastMCP 3.0 Upgrade
- **CovenantMiddleware**: Sacred Covenant enforcement via FastMCP 3.0 middleware pattern
- **Component Versioning**: All tools include version metadata
- **OpenTelemetry Tracing** (Optional): `pip install daem0nmcp[tracing]`

---

## Previous Versions

<details>
<summary>v2.16.0 — Sacred Covenant Enforcement</summary>

- Tools block with `COMMUNION_REQUIRED`/`COUNSEL_REQUIRED` until proper rituals observed
- Preflight tokens with 5-minute validity
- MCP Resources for dynamic context injection (`daem0n://warnings/`, `daem0n://failed/`, etc.)
</details>

<details>
<summary>v2.14.0–v2.15.0 — Active Context, Temporal Versioning, Entities</summary>

- Active Working Context (MemGPT-style always-hot memories, max 10)
- Temporal versioning with `versions` and `at_time` queries
- Hierarchical summarization via Leiden communities
- Auto entity extraction from memory content
- Contextual recall triggers (auto-recall on file/tag/entity patterns)
- Configurable hybrid search weight, result diversity, tag inference
- Qualified entity names (`module.Class.method`), incremental indexing
</details>

<details>
<summary>v2.11.0–v2.13.0 — Passive Capture, Linked Projects</summary>

- Passive Capture hooks (auto-remember decisions from conversation)
- Endless Mode (condensed recall with 50-75% token reduction)
- Linked Projects for cross-repo memory awareness
</details>

<details>
<summary>v2.7.0–v2.10.0 — Code Understanding, Enforcement, File Watcher</summary>

- Multi-language AST parsing via tree-sitter (Python, TypeScript, JavaScript, Go, Rust, Java, C, C++, C#, Ruby, PHP)
- Qdrant vector backend for persistent vector storage
- Proactive file watcher with desktop/log/editor-poll notifications
- Pre-commit enforcement hooks blocking commits with stale decisions
- CLI tools for status, record-outcome, install-hooks
</details>

<details>
<summary>Core Features (v2.1+)</summary>

- TF-IDF semantic search with real similarity matching
- Memory decay (30-day half-life for decisions/learnings, eternal patterns/warnings)
- Conflict detection and failed decision boosting (1.5x relevance)
- File-level memory associations
- Vector embeddings for enhanced semantic matching
</details>

## Why Daem0nMCP?

AI agents start each session fresh. They don't remember:
- What decisions were made and why
- Patterns that should be followed
- Warnings from past mistakes

**Markdown files don't solve this** - the AI has to know to read them and might ignore them.

**Daem0nMCP provides ACTIVE memory** - it surfaces relevant context when the AI asks about a topic, enforces rules before actions, and learns from outcomes.

### What Makes This Different

- **Semantic matching**: "creating REST endpoint" matches rules about "adding API route"
- **Time decay**: A decision from yesterday matters more than one from 6 months ago
- **Conflict warnings**: "You tried this approach before and it failed"
- **Learning loops**: Record outcomes, and failures get boosted in future recalls
- **Surprise scoring**: Novel information surfaces above routine knowledge
- **Graph reasoning**: Multi-hop traversal across linked memories and communities
- **Background dreaming**: Idle-time re-evaluation of past failed decisions

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

# Optional: ONNX acceleration for embeddings
pip install -e ~/Daem0nMCP[onnx]

# Run the MCP server (Linux/macOS — stdio transport)
python -m daem0nmcp.server

# Run the MCP server (Windows — HTTP transport required)
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

### Transport Modes

| Method | Transport | Default Port | Use Case |
|--------|-----------|-------------|----------|
| `python -m daem0nmcp.server` | `stdio` (default) or `sse` | 8765 (sse) | Unix/macOS direct channel |
| `python start_server.py` | `streamable-http` | 9876 | Windows HTTP, remote access |

## Workflow Tools (8 Tools, 59 Actions)

All capabilities are accessed through 8 workflow tools. Each tool accepts an `action` parameter to select the operation. Legacy individual tools remain registered for backward compatibility.

### `commune` — Session Start & Status

| Action | Purpose |
|--------|---------|
| `briefing` | Smart session start with git awareness |
| `active_context` | Get all hot memories for current focus |
| `triggers` | Check context triggers for auto-recalled memories |
| `health` | Server health, version, and statistics |
| `covenant` | Sacred Covenant status and phase |
| `updates` | Poll for knowledge changes (real-time notifications) |

### `consult` — Pre-Action Intelligence

| Action | Purpose |
|--------|---------|
| `preflight` | Combined recall + rules check before changes |
| `recall` | Semantic memory retrieval by topic (supports `condensed`, `visual`) |
| `recall_file` | Get memories linked to a specific file |
| `recall_entity` | Get memories mentioning a code entity |
| `recall_hierarchical` | GraphRAG-style layered retrieval with community summaries |
| `search` | Full-text search across all memories (supports `highlight`, `visual`) |
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
| `todos` | Scan for TODO/FIXME/HACK/XXX/BUG comments |
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

### Cognitive Tools (Standalone)

| Tool | Purpose |
|------|---------|
| `simulate_decision` | Temporal Scrying — replay a past decision with current knowledge |
| `evolve_rule` | Rule Entropy — examine rules for staleness and drift |
| `debate_internal` | Adversarial Council — evidence-grounded debate with convergence detection |

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
# Sorted by: semantic relevance x recency x importance

consult(action="recall_file", file_path="src/auth/jwt.py")
# Returns: all memories linked to this file

consult(action="recall_entity", entity_name="UserService")
# Returns: all memories mentioning the entity

consult(action="recall", topic="auth", condensed=True)
# Condensed: 50-75% fewer tokens, content truncated to 150 chars
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
# Returns: stats, recent decisions, warnings, failed approaches,
# git changes, plus pre-fetched context for focus areas
```

### Active Context (Working Memory)
```python
inscribe(action="activate", memory_id=42, reason="Working on auth refactor",
         priority=10, expires_in_hours=8)
# Memory stays in always-hot context, auto-injected into briefings
# Max 10 items, auto-expires, duplicate prevention

commune(action="active_context")  # View all hot memories
inscribe(action="deactivate", memory_id=42)  # Remove
inscribe(action="clear_active")  # Clear all
```

### Cognitive Tools
```python
# Temporal Scrying: What would I decide differently today?
simulate_decision(decision_id=42)

# Rule Entropy: Which rules have grown stale?
evolve_rule(rule_id=5)       # Single rule
evolve_rule()                 # Batch: all enabled rules

# Adversarial Council: Evidence-grounded debate
debate_internal(
    topic="Database choice for sessions",
    advocate_position="Use Redis",
    challenger_position="Use PostgreSQL"
)
```

### Import External Docs
```python
inscribe(action="ingest", url="https://stripe.com/docs/api/charges", topic="stripe")
# Later: consult(action="recall", topic="stripe") to retrieve
```

## AI Agent Protocol

The recommended workflow for AI agents:

```
SESSION START
    +-> commune(action="briefing")

BEFORE CHANGES
    +-> consult(action="preflight", description="what you're doing")
    +-> consult(action="recall_file", file_path="path/to/file.py")

AFTER DECISIONS
    +-> inscribe(action="remember", category=..., content=..., rationale=..., file_path=...)

AFTER IMPLEMENTATION
    +-> reflect(action="outcome", memory_id=..., outcome_text=..., worked=...)
```

See `Summon_Daem0n.md` for the complete protocol (with ritual theme for fun).

## Claude Code Integration

### Automated Hook Installation (Recommended)

```bash
python -m daem0nmcp.cli install-claude-hooks
```

This registers 5 hook modules in `~/.claude/settings.json`:

| Event | Hook | Purpose |
|-------|------|---------|
| `SessionStart` | `session_start` | Auto-briefing summary |
| `PreToolUse` (Edit/Write/NotebookEdit) | `pre_edit` | Preflight enforcement + file memory recall |
| `PreToolUse` (Bash) | `pre_bash` | Rule enforcement on commands |
| `PostToolUse` (Edit/Write) | `post_edit` | Suggest remembrance for significant changes |
| `Stop`/`SubagentStop` | `stop` | Auto-capture decisions from conversation |

To remove: `python -m daem0nmcp.cli uninstall-claude-hooks`

### Manual Hooks (Legacy)

Add to `.claude/settings.json`:
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

### Protocol Skill

A Claude Code skill is included at `.claude/skills/daem0nmcp-protocol/SKILL.md` that enforces the memory protocol automatically.

## How It Works

### Hybrid Search (BM25 + Vector + RRF)
- **BM25** for keyword matching with term saturation and length normalization
- **ModernBERT** vector embeddings (256-dim, asymmetric encoding) for deep semantic understanding
- **Reciprocal Rank Fusion** combines both with configurable weights
- "blocking database calls" matches memories about "synchronous queries"

### Auto-Zoom Retrieval Routing
Query-aware dispatch classifies complexity and routes to the optimal strategy:
- Simple queries → vector-only (fast path)
- Medium queries → hybrid BM25+vector
- Complex queries → GraphRAG multi-hop with community summaries

### Memory Decay
```
weight = e^(-lambda*t) where lambda = ln(2)/half_life_days
```
Default half-life is 30 days. Patterns and warnings are permanent (no decay).

### Conflict Detection
When storing a new memory, it's compared against recent memories:
- If similar content failed before → warning about the failure
- If it matches an existing warning → warning surfaced
- If highly similar content exists → potential duplicate flagged

### Failed Decision Boosting
Memories with `worked=False` get a 1.5x relevance boost in recalls.
Warnings get a 1.2x boost. Past mistakes surface prominently.

### Background Dreaming
During idle periods, the daemon re-evaluates failed decisions against current evidence. `FailedDecisionReview` strategy finds `worked=False` decisions, recalls current evidence, and persists actionable insights as `learning` memories. Yields cooperatively when the user returns.

## Data Storage

Each project gets isolated storage at:
```
<project_root>/.daem0nmcp/storage/daem0nmcp.db
```

## Configuration

All settings are configurable via environment variables with `DAEM0NMCP_` prefix.

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DAEM0NMCP_PROJECT_ROOT` | `.` | Project root path |
| `DAEM0NMCP_STORAGE_PATH` | auto | Override storage location |
| `DAEM0NMCP_LOG_LEVEL` | `INFO` | Logging level |
| `DAEM0NMCP_QDRANT_URL` | `None` | Remote Qdrant URL (overrides local) |

### Embedding Model (v6.6.6+)

| Variable | Default | Description |
|----------|---------|-------------|
| `DAEM0NMCP_EMBEDDING_MODEL` | `nomic-ai/modernbert-embed-base` | Model name |
| `DAEM0NMCP_EMBEDDING_DIMENSION` | `256` | Matryoshka truncation dimension |
| `DAEM0NMCP_EMBEDDING_BACKEND` | auto-detected | `onnx` or `torch` |
| `DAEM0NMCP_EMBEDDING_QUERY_PREFIX` | `search_query: ` | Prefix for query encoding |
| `DAEM0NMCP_EMBEDDING_DOCUMENT_PREFIX` | `search_document: ` | Prefix for document encoding |

### Search Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `DAEM0NMCP_HYBRID_VECTOR_WEIGHT` | `0.3` | Vector weight in hybrid search (0.0-1.0) |
| `DAEM0NMCP_BM25_K1` | `1.5` | BM25 term frequency saturation |
| `DAEM0NMCP_BM25_B` | `0.75` | BM25 document length normalization |
| `DAEM0NMCP_RRF_K` | `60` | RRF fusion dampening constant |
| `DAEM0NMCP_SEARCH_DIVERSITY_MAX_PER_FILE` | `3` | Max results from same file |

### Auto-Zoom Routing

| Variable | Default | Description |
|----------|---------|-------------|
| `DAEM0NMCP_AUTO_ZOOM_ENABLED` | `false` | Master switch for query-aware routing |
| `DAEM0NMCP_AUTO_ZOOM_SHADOW` | `true` | Log classifications without routing |
| `DAEM0NMCP_AUTO_ZOOM_CONFIDENCE_THRESHOLD` | `0.25` | Below this → hybrid fallback |
| `DAEM0NMCP_AUTO_ZOOM_GRAPH_EXPANSION_DEPTH` | `2` | Multi-hop depth for complex queries |

### Background Dreaming

| Variable | Default | Description |
|----------|---------|-------------|
| `DAEM0NMCP_DREAM_ENABLED` | `true` | Master switch for dreaming |
| `DAEM0NMCP_DREAM_IDLE_TIMEOUT` | `60.0` | Seconds of idle before dreaming starts |
| `DAEM0NMCP_DREAM_MAX_DECISIONS_PER_SESSION` | `5` | Max failed decisions to re-evaluate |
| `DAEM0NMCP_DREAM_MIN_DECISION_AGE_HOURS` | `1` | Min age before re-evaluation eligible |

### Cognitive Tools

| Variable | Default | Description |
|----------|---------|-------------|
| `DAEM0NMCP_COGNITIVE_DEBATE_MAX_ROUNDS` | `5` | Max rounds for adversarial council |
| `DAEM0NMCP_COGNITIVE_EVOLVE_MAX_RULES` | `10` | Max rules to analyze for staleness |
| `DAEM0NMCP_COGNITIVE_STALENESS_AGE_WEIGHT` | `0.3` | Time-based decay weight |

### Recall Planner

| Variable | Default | Description |
|----------|---------|-------------|
| `DAEM0NMCP_SURPRISE_K_NEAREST` | `5` | Neighbors for surprise calculation |
| `DAEM0NMCP_SURPRISE_BOOST_THRESHOLD` | `0.7` | Boost threshold (0.0-1.0) |
| `DAEM0NMCP_RECALL_SIMPLE_MAX_MEMORIES` | `5` | Max memories for simple queries |
| `DAEM0NMCP_RECALL_MEDIUM_MAX_MEMORIES` | `10` | Max memories for medium queries |
| `DAEM0NMCP_RECALL_COMPLEX_MAX_MEMORIES` | `20` | Max memories for complex queries |
| `DAEM0NMCP_FACT_PROMOTION_THRESHOLD` | `3` | Outcomes to promote to fact |

See `Summon_Daem0n.md` for the complete configuration reference (~50 settings).

## Architecture

```
daem0nmcp/
├── server.py            # MCP server with 8 workflow + 3 cognitive tools (FastMCP)
├── mcp_instance.py      # FastMCP instance creation
├── config.py            # Pydantic settings (~50 configurable options)
├── memory.py            # Memory storage & semantic retrieval
├── rules.py             # Rule engine with BM25 matching
├── similarity.py        # TF-IDF index, decay, conflict detection
├── vectors.py           # ModernBERT embeddings (ONNX/torch, asymmetric encoding)
├── bm25_index.py        # BM25 Okapi keyword retrieval
├── fusion.py            # Reciprocal Rank Fusion for hybrid search
├── surprise.py          # Titans-inspired novelty detection
├── recall_planner.py    # TiMem-style complexity classification
├── retrieval_router.py  # Auto-Zoom query-aware search dispatch
├── query_classifier.py  # Exemplar-based query complexity classification
├── qdrant_store.py      # Qdrant vector database backend
├── active_context.py    # MemGPT-style always-hot working memory
├── entity_extractor.py  # Entity extraction from memory content
├── entity_manager.py    # Entity lifecycle management
├── communities.py       # Leiden community detection & summaries
├── context_triggers.py  # Auto-recall trigger system
├── context_manager.py   # Multi-project context management
├── covenant.py          # Sacred Covenant enforcement & preflight tokens
├── database.py          # SQLite async database
├── models.py            # 10+ tables: memories, rules, relationships, etc.
├── enforcement.py       # Pre-commit enforcement & session tracking
├── hooks.py             # Git hook templates & installation
├── cli.py               # Command-line interface
├── workflows/           # 8 consolidated workflow tools
│   ├── commune.py       # Session start & status
│   ├── consult.py       # Pre-action intelligence
│   ├── inscribe.py      # Memory writing & linking
│   ├── reflect.py       # Outcomes & verification
│   ├── understand.py    # Code comprehension
│   ├── govern.py        # Rules & triggers
│   ├── explore.py       # Graph & discovery
│   └── maintain.py      # Housekeeping & federation
├── tools/               # MCP tool registrations
│   ├── workflows.py     # 8 workflow tool definitions
│   ├── cognitive_tools.py # simulate_decision, evolve_rule, debate_internal
│   ├── memory.py        # Legacy memory tools (deprecated)
│   ├── briefing.py      # Legacy briefing tools (deprecated)
│   ├── code_tools.py    # Legacy code tools (deprecated)
│   ├── context_tools.py # Legacy context tools (deprecated)
│   ├── entity_tools.py  # Legacy entity tools (deprecated)
│   ├── graph_tools.py   # Legacy graph tools (deprecated)
│   ├── rules.py         # Legacy rule tools (deprecated)
│   ├── temporal.py      # Legacy temporal tools (deprecated)
│   ├── verification.py  # Legacy verification tools (deprecated)
│   ├── federation.py    # Legacy federation tools (deprecated)
│   ├── maintenance.py   # Legacy maintenance tools (deprecated)
│   └── agency_tools.py  # Legacy agency tools (deprecated)
├── cognitive/           # Cognitive tool implementations
│   ├── simulate.py      # Temporal scrying (decision replay)
│   ├── evolve.py        # Rule entropy analysis
│   └── debate.py        # Adversarial council
├── dreaming/            # Background dreaming system
│   ├── scheduler.py     # IdleDreamScheduler (idle detection + dispatch)
│   ├── strategies.py    # FailedDecisionReview strategy
│   └── persistence.py   # Dream session/result models & persistence
├── claude_hooks/        # Claude Code native hooks
│   ├── install.py       # install/uninstall-claude-hooks CLI
│   ├── session_start.py # Auto-briefing at session dawn
│   ├── pre_edit.py      # Preflight enforcement + file recall
│   ├── pre_bash.py      # Rule enforcement on commands
│   ├── post_edit.py     # Significance detection
│   ├── stop.py          # Auto-capture decisions
│   └── _client.py       # Hook helper utilities
├── compression/         # LLMLingua-2 context compression
├── graph/               # Knowledge graph (NetworkX + Leiden)
├── reflexion/           # Metacognitive architecture (LangGraph)
├── agency/              # Dynamic agency (E2B sandboxing)
├── transforms/          # FastMCP 3.0 middleware
│   └── covenant.py      # CovenantMiddleware & CovenantTransform
├── ui/                  # MCP Apps visual interfaces (D3.js)
├── channels/            # Notification channels (desktop, log, editor-poll)
├── migrations/          # Database schema & embedding migrations
├── code_indexer.py      # Code understanding via tree-sitter
├── watcher.py           # Proactive file watcher daemon
├── tracing.py           # OpenTelemetry integration (optional)
├── prompt_templates.py  # AutoPDL-inspired modular prompts
└── tool_search.py       # Dynamic tool discovery index

.claude/
└── skills/
    └── daem0nmcp-protocol/
        └── SKILL.md       # Protocol enforcement skill

Summon_Daem0n.md     # Installation instructions (ritual theme)
Banish_Daem0n.md     # Uninstallation instructions
start_server.py      # HTTP server launcher (streamable-http transport)
```

## CLI Commands

```bash
# Session briefing/statistics
python -m daem0nmcp.cli briefing

# Index code entities
python -m daem0nmcp.cli index [--path PATH] [--patterns **/*.py **/*.ts ...]

# Scan for TODO/FIXME/HACK comments
python -m daem0nmcp.cli scan-todos [--auto-remember] [--path PATH]

# Check a file against memories and rules
python -m daem0nmcp.cli check <filepath>

# Run database migrations (usually automatic)
python -m daem0nmcp.cli migrate [--backfill-vectors]
```

### Hook & Enforcement Commands

```bash
# Install Claude Code hooks (user-level, all projects)
python -m daem0nmcp.cli install-claude-hooks [--dry-run]

# Remove Claude Code hooks
python -m daem0nmcp.cli uninstall-claude-hooks [--dry-run]

# Install git pre-commit hooks
python -m daem0nmcp.cli install-hooks [--force]

# Remove git pre-commit hooks
python -m daem0nmcp.cli uninstall-hooks

# Show pending decisions and blocking issues
python -m daem0nmcp.cli status

# Record outcome for a decision
python -m daem0nmcp.cli record-outcome <id> "<outcome>" --worked|--failed
```

All commands support `--json` for machine-readable output and `--project-path` to specify the project root.

## Upgrading

### 1. Update the Code

```bash
# If installed from source (recommended)
cd ~/Daem0nMCP && git pull && pip install -e .

# Optional: ONNX acceleration
pip install -e ~/Daem0nMCP[onnx]
```

### 2. Re-encode Embeddings (v6.6.6+ — REQUIRED for existing data)

The embedding model changed from `all-MiniLM-L6-v2` (384-dim) to `nomic-ai/modernbert-embed-base` (256-dim). Existing embeddings must be re-encoded:

```bash
python -m daem0nmcp.migrations.migrate_embedding_model --project-path /path/to/.daem0nmcp
```

Qdrant collections are auto-recreated with the correct dimension on first startup.

### 3. Install Claude Code Hooks

```bash
python -m daem0nmcp.cli install-claude-hooks
```

### 4. Restart Claude Code

After updating, restart Claude Code to load the new MCP tools.

### 5. Migrations Run Automatically

Database schema migrations are applied automatically when any MCP tool runs. No manual migration step required.

### 6. Index Your Codebase

```bash
python -m daem0nmcp.cli index
```

Supports Python, TypeScript, JavaScript, Go, Rust, Java, C, C++, C#, Ruby, PHP via tree-sitter.

## Troubleshooting

### MCP Tools Not Available in Claude Session

**Symptom:** `claude mcp list` shows daem0nmcp connected, but Claude can't use `mcp__daem0nmcp__*` tools.

**Fixes:**

1. **Start server before Claude Code (Windows):**
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

### Hooks Not Firing

1. MCP server running: `curl http://localhost:9876/mcp` should respond
2. Hooks configured: check `~/.claude/settings.json` or `.claude/settings.json`
3. Project has `.daem0nmcp/` directory

### Communion/Counsel Errors

- `COMMUNION_REQUIRED` → Call `commune(action="briefing", project_path="...")` first
- `COUNSEL_REQUIRED` → Call `consult(action="preflight", description="...", project_path="...")` first

## Development

```bash
# Install in development mode
pip install -e .[dev]

# Run tests (500+ tests)
pytest tests/ -v --asyncio-mode=auto

# Run server directly (stdio)
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
# Remove Claude Code hooks
python -m daem0nmcp.cli uninstall-claude-hooks

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

*Daem0nMCP v6.6.6: ModernBERT Deep Sight (256-dim Matryoshka, ONNX quantized, asymmetric encoding). 8 workflow tools with 59 actions + 3 cognitive tools (simulate_decision, evolve_rule, debate_internal). Background Dreaming, Auto-Zoom Retrieval Routing, Active Context, Visual Portals (MCP Apps), GraphRAG, bi-temporal knowledge, LLMLingua-2 compression, Claude Code native hooks. 500+ tests. The daemon sees deeper and speaks with greater precision.*
