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
- Communion required: `remember`, `remember_batch`, `add_rule`, `update_rule`, `record_outcome`, `link_memories`, `pin_memory`, `archive_memory`, `prune_memories`, `cleanup_memories`, `compact_memories`
- Exempt (read-only): `recall`, `recall_for_file`, `search_memories`, `find_code`, `analyze_impact`, `check_rules`, `list_rules`

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

## Core Tools (53 Total)

### Memory Tools

| Tool | Purpose |
|------|---------|
| `remember` | Store a memory with conflict detection |
| `remember_batch` | Store multiple memories efficiently in one transaction |
| `recall` | Semantic memory retrieval by topic (supports `condensed=True` for token savings) |
| `recall_for_file` | Get memories linked to a specific file |
| `search_memories` | Search across all memories |
| `find_related` | Discover connected memories |
| `record_outcome` | Track if a decision worked or failed |
| `pin_memory` | Pin memories to prevent pruning and boost relevance |
| `archive_memory` | Hide memories from recall while preserving history |
| `compact_memories` | Consolidate old episodic memories into summaries |
| `get_memory_versions` | Get full version history for a memory |
| `get_memory_at_time` | Query historical state of a memory at a specific time |

### Rule Tools

| Tool | Purpose |
|------|---------|
| `add_rule` | Create decision tree nodes |
| `check_rules` | Semantic rule matching |
| `update_rule` | Modify existing rules |
| `list_rules` | Show all configured rules |

### Session & Context Tools

| Tool | Purpose |
|------|---------|
| `get_briefing` | Smart session start with git awareness |
| `context_check` | Combined recall + rules in one call |
| `set_active_context` | Pin memory to active working context |
| `get_active_context` | Get all hot memories for current focus |
| `remove_from_active_context` | Remove memory from active context |
| `clear_active_context` | Clear all hot memories |

### Graph Memory Tools

| Tool | Purpose |
|------|---------|
| `link_memories` | Create causal relationships between memories |
| `unlink_memories` | Remove relationships between memories |
| `trace_chain` | Traverse memory graph (forward/backward) |
| `get_graph` | Visualize memory relationships (JSON or Mermaid) |

### Hierarchical Summarization Tools

| Tool | Purpose |
|------|---------|
| `rebuild_communities` | Detect memory clusters by tag co-occurrence |
| `list_communities` | Get community summaries for high-level overview |
| `get_community_details` | Drill down to member memories in a community |
| `recall_hierarchical` | Layered retrieval: community summaries then details |

### Code Understanding Tools

| Tool | Purpose |
|------|---------|
| `index_project` | Index code entities (classes, functions, methods) |
| `find_code` | Semantic search across code entities |
| `analyze_impact` | Analyze what changing an entity would affect |

### Utility Tools

| Tool | Purpose |
|------|---------|
| `scan_todos` | Find TODO/FIXME/HACK comments |
| `propose_refactor` | Get refactoring context for a file |
| `ingest_doc` | Import external documentation |

### Maintenance Tools

| Tool | Purpose |
|------|---------|
| `rebuild_index` | Force rebuild TF-IDF and vector indexes |
| `export_data` | Export all memories and rules as JSON |
| `import_data` | Import memories and rules from JSON |
| `prune_memories` | Remove old, low-value memories (with protection) |
| `cleanup_memories` | Find and merge duplicate memories |
| `health` | Get server health, version, and statistics |

## Usage Examples

### Store a Memory
```python
remember(
    category="decision",  # decision, pattern, warning, or learning
    content="Use JWT tokens instead of sessions",
    rationale="Need stateless auth for horizontal scaling",
    tags=["auth", "architecture"],
    file_path="src/auth/jwt.py"  # optional file association
)
```

### Retrieve Memories
```python
recall("authentication")
# Returns: decisions, patterns, warnings, learnings about auth
# Sorted by: semantic relevance × recency × importance

recall_for_file("src/auth/jwt.py")
# Returns: all memories linked to this file
```

### Create Rules
```python
add_rule(
    trigger="adding new API endpoint",
    must_do=["Add rate limiting", "Write integration test"],
    must_not=["Use synchronous database calls"],
    ask_first=["Is this a breaking change?"]
)
```

### Track Outcomes
```python
record_outcome(memory_id=42, outcome="JWT auth works great", worked=True)
record_outcome(memory_id=43, outcome="Caching caused stale data", worked=False)
# Failed decisions get 1.5x boost in future recalls
```

### Session Start
```python
get_briefing(focus_areas=["authentication", "API"])
# First run: Creates 6-7 memories from project structure, README, manifests, etc.
# Returns: stats, recent decisions, warnings, failed approaches,
# git changes, bootstrap summary, plus pre-fetched context for focus areas
```

### Endless Mode (Token Compression)
```python
# Full recall (default) - ~40KB response
recall("authentication")

# Condensed recall - ~10KB response (75% smaller)
recall("authentication", condensed=True)
# Returns: truncated content, no rationale/context, minimal fields

# Briefings automatically use condensed mode for focus areas
get_briefing(focus_areas=["auth", "database", "api"])
# Focus area results are pre-compressed
```

### Import External Docs
```python
ingest_doc("https://stripe.com/docs/api/charges", "stripe")
# Later: recall("stripe") to retrieve
```

## AI Agent Protocol

The recommended workflow for AI agents:

```
SESSION START
    └─> get_briefing()

BEFORE CHANGES
    └─> context_check("what you're doing")
    └─> recall_for_file("path/to/file.py")

AFTER DECISIONS
    └─> remember(category, content, rationale, file_path)

AFTER IMPLEMENTATION
    └─> record_outcome(memory_id, outcome, worked)
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

## Architecture

```
daem0nmcp/
├── server.py       # MCP server with 42+ tools (FastMCP)
├── memory.py       # Memory storage & semantic retrieval
├── rules.py        # Rule engine with TF-IDF matching
├── similarity.py   # TF-IDF index, decay, conflict detection
├── vectors.py      # Vector embeddings (sentence-transformers)
├── covenant.py     # Sacred Covenant enforcement decorators & preflight tokens
├── transforms/     # FastMCP 3.0 transforms
│   └── covenant.py # CovenantMiddleware & CovenantTransform
├── tracing.py      # OpenTelemetry integration (optional)
├── code_indexer.py # Code understanding via tree-sitter (Phase 2)
├── watcher.py      # Proactive file watcher daemon (Phase 1)
├── database.py     # SQLite async database
├── models.py       # 10+ tables: memories, rules, memory_relationships,
│                   #             session_state, code_entities, memory_code_refs,
│                   #             communities, context_triggers, memory_versions, etc.
├── enforcement.py  # Pre-commit enforcement & session tracking
├── hooks.py        # Git hook templates & installation
├── cli.py          # Command-line interface
├── migrations/     # Database schema migrations
└── config.py       # Pydantic settings

.claude/
└── skills/
    └── daem0nmcp-protocol/
        └── SKILL.md   # Protocol enforcement skill

Summon_Daem0n.md   # Installation instructions (ritual theme)
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

# Run tests (559 tests)
pytest tests/ -v --asyncio-mode=auto

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

*Daem0nMCP v3.0.0: FastMCP 3.0 upgrade—CovenantMiddleware, component versioning, OpenTelemetry tracing, Sacred Covenant enforcement.*
