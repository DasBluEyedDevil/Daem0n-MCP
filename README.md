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

## What's New in v2.5.0

- **Windows HTTP Transport**: Full Windows support via streamable-http (bypasses stdio bugs)
- **Ritual-Themed Installation**: `Summon_Daem0n.md` and `Banish_Daem0n.md` for fun
- **15 MCP Tools**: Including `scan_todos`, `propose_refactor`, `ingest_doc`, `recall_for_file`
- **Claude Code Hooks**: Auto-reminders to use memory tools
- **Protocol Skill**: `daem0nmcp-protocol` skill for Superpowers users
- **Project Rule Generation**: Auto-analyze projects and propose rules
- **CLAUDE.md Integration**: Auto-update project instructions

### Previous Features (v2.1+)
- **TF-IDF Semantic Search**: Real similarity matching, not just keyword overlap
- **Memory Decay**: Recent memories weighted higher than old ones
- **Conflict Detection**: Warns when new decisions contradict past failures
- **Failed Decision Boosting**: Past mistakes surface prominently in recalls
- **File-Level Memories**: Associate memories with specific files
- **Vector Embeddings**: sentence-transformers for enhanced semantic matching (included by default)

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

## Core Tools (15 Total)

### Memory Tools

| Tool | Purpose |
|------|---------|
| `remember` | Store a memory with conflict detection |
| `recall` | Semantic memory retrieval by topic |
| `recall_for_file` | Get memories linked to a specific file |
| `search_memories` | Search across all memories |
| `find_related` | Discover connected memories |
| `record_outcome` | Track if a decision worked or failed |

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

### Utility Tools

| Tool | Purpose |
|------|---------|
| `scan_todos` | Find TODO/FIXME/HACK comments |
| `propose_refactor` | Get refactoring context for a file |
| `ingest_doc` | Import external documentation |

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
# Returns: stats, recent decisions, warnings, failed approaches,
# git changes, plus pre-fetched context for focus areas
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
├── server.py      # MCP server with 15 tools (FastMCP)
├── memory.py      # Memory storage & semantic retrieval
├── rules.py       # Rule engine with TF-IDF matching
├── similarity.py  # TF-IDF index, decay, conflict detection
├── vectors.py     # Vector embeddings (sentence-transformers)
├── database.py    # SQLite async database
├── models.py      # 2 tables: memories, rules
├── cli.py         # Command-line interface
└── config.py      # Pydantic settings

.claude/
└── skills/
    └── daem0nmcp-protocol/
        └── SKILL.md   # Protocol enforcement skill

Summon_Daem0n.md   # Installation instructions (ritual theme)
Banish_Daem0n.md   # Uninstallation instructions
start_server.py    # HTTP server launcher (Windows)
```

## Development

```bash
# Install in development mode
pip install -e .

# Run tests (88 tests)
pytest tests/ -v --asyncio-mode=auto

# Run server directly
python -m daem0nmcp.server

# Run HTTP server (Windows)
python start_server.py --port 9876
```

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

*Daem0nMCP v2.5.0: Persistent memory with semantic understanding, because AI agents should remember what they learned—and what went wrong.*
