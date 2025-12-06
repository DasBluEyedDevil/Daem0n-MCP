# DevilMCP

**AI Memory & Decision System** - Give AI agents persistent memory and consistent decision-making.

DevilMCP solves "AI amnesia" by providing:
- **Active Memory**: Store and retrieve decisions, patterns, warnings, and learnings
- **Decision Trees**: Rules that guide AI behavior consistently
- **Outcome Tracking**: Learn from what worked and what didn't

## Why DevilMCP?

AI agents start each session fresh. They don't remember:
- What decisions were made and why
- Patterns that should be followed
- Warnings from past mistakes

**Markdown files don't solve this** - the AI has to know to read them and might ignore them.

**DevilMCP provides ACTIVE memory** - it surfaces relevant context when the AI asks about a topic, enforces rules before actions, and learns from outcomes.

## Quick Start

```bash
# Install
pip install -e /path/to/DevilMCP

# Run the MCP server
python -m devilmcp.server
```

## Core Tools

### 1. `remember` - Store a memory
```python
remember(
    category="decision",  # decision, pattern, warning, or learning
    content="Use JWT tokens instead of sessions",
    rationale="Need stateless auth for horizontal scaling",
    tags=["auth", "architecture"]
)
```

### 2. `recall` - Retrieve relevant memories
```python
recall("authentication")
# Returns: decisions, patterns, warnings, learnings about auth
```

### 3. `add_rule` - Create decision tree nodes
```python
add_rule(
    trigger="adding new API endpoint",
    must_do=["Add rate limiting", "Write integration test"],
    must_not=["Use synchronous database calls"],
    ask_first=["Is this a breaking change?"]
)
```

### 4. `check_rules` - Validate actions against rules
```python
check_rules("I'm adding a new API endpoint")
# Returns: matching rules, combined guidance, warnings
```

### 5. `record_outcome` - Track what worked
```python
record_outcome(memory_id=42, outcome="JWT auth works great", worked=True)
```

### 6. `get_briefing` - Session start summary
```python
get_briefing()
# Returns: stats, recent decisions, active warnings, top rules
```

## MCP Configuration

### Claude Desktop / Claude Code
Add to your config file:

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**Mac**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "devilmcp": {
      "command": "python",
      "args": ["-m", "devilmcp.server"],
      "env": {
        "PYTHONPATH": "/path/to/DevilMCP",
        "DEVILMCP_PROJECT_ROOT": "/path/to/your/project"
      }
    }
  }
}
```

### Cursor IDE
Add to `~/.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "devilmcp": {
      "command": "python",
      "args": ["-m", "devilmcp.server"],
      "env": {
        "PYTHONPATH": "/path/to/DevilMCP",
        "DEVILMCP_PROJECT_ROOT": "/path/to/your/project"
      }
    }
  }
}
```

## AI Agent Protocol

### At Session Start
```
Call get_briefing() to load context
```

### Before Making Changes
```
1. Call recall(topic) to get relevant memories
2. Call check_rules(action) to get guidance
3. Follow must_do items, avoid must_not items
```

### When Making Decisions
```
Call remember(category="decision", content="...", rationale="...")
```

### After Implementing
```
Call record_outcome(memory_id, outcome, worked)
```

## Data Storage

Each project gets isolated storage at:
```
<project_root>/.devilmcp/storage/devilmcp.db
```

## Migration from v1

If you have an existing DevilMCP database:
```bash
python scripts/migrate_to_v2.py /path/to/.devilmcp/storage/devilmcp.db
```

This converts old decisions, thoughts, and cascade events to the new memory format.

## Configuration

Environment variables (prefix: `DEVILMCP_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVILMCP_PROJECT_ROOT` | `.` | Project root path |
| `DEVILMCP_STORAGE_PATH` | auto | Override storage location |
| `DEVILMCP_LOG_LEVEL` | `INFO` | Logging level |

## Architecture

```
devilmcp/
├── server.py      # MCP server with 9 tools
├── memory.py      # Memory storage & retrieval
├── rules.py       # Decision tree / rule engine
├── database.py    # SQLite async database
├── models.py      # 3 tables: memories, rules, project_state
└── config.py      # Pydantic settings
```

## Development

```bash
# Install in development mode
pip install -e .

# Run tests
pytest tests/ -v --asyncio-mode=auto

# Run server directly
python -m devilmcp.server
```

---

*DevilMCP: Because AI agents should remember what they learned.*
