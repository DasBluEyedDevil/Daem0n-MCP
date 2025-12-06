# CLAUDE.md

Guidance for Claude Code when working with this repository.

## Project Overview

DevilMCP is a focused MCP server providing **AI memory and decision trees**. It gives AI agents:
- Persistent memory across sessions (decisions, patterns, warnings, learnings)
- Rule-based decision trees for consistent behavior
- Outcome tracking for learning

## Commands

```bash
# Install
pip install -e .

# Run the MCP server
python -m devilmcp.server

# Run tests
pytest tests/ -v --asyncio-mode=auto
```

## Architecture

```
devilmcp/
├── server.py      # MCP server, 9 tools (FastMCP)
├── memory.py      # MemoryManager - store/recall memories
├── rules.py       # RulesEngine - decision tree nodes
├── database.py    # DatabaseManager - async SQLite
├── models.py      # SQLAlchemy models (3 tables)
└── config.py      # Pydantic settings
```

**Data Storage:** `<project_root>/.devilmcp/storage/devilmcp.db`

## Database Schema (3 tables)

**memories**: Stores decisions, patterns, warnings, learnings
- category, content, rationale, context, tags, keywords
- outcome tracking (outcome, worked)

**rules**: Decision tree nodes
- trigger, trigger_keywords
- must_do, must_not, ask_first, warnings
- priority, enabled

**project_state**: Cached project info

## Key Patterns

- **Async-first**: All database operations use async/await
- **Keyword extraction**: Content is indexed for semantic-ish search
- **Rule matching**: Actions are matched against rules by keyword overlap
- **Outcome learning**: Failed decisions inform future recalls

## MCP Tools (9 total)

Core:
1. `remember` - Store a memory (decision/pattern/warning/learning)
2. `recall` - Retrieve relevant memories by topic
3. `add_rule` - Create decision tree node
4. `check_rules` - Validate action against rules
5. `record_outcome` - Track if decision worked
6. `get_briefing` - Session start summary

Utility:
7. `search_memories` - Full-text search
8. `list_rules` - Show all rules
9. `update_rule` - Modify existing rule

## Adding New Tools

```python
@mcp.tool()
async def my_tool(param: str) -> Dict[str, Any]:
    """Tool description shown to AI agents."""
    await db_manager.init_db()
    # ... implementation
    return {"result": "..."}
```

## AI Agent Protocol

1. **Session Start**: Call `get_briefing()`
2. **Before Changes**: Call `recall(topic)` and `check_rules(action)`
3. **Making Decisions**: Call `remember(category, content, rationale)`
4. **After Implementation**: Call `record_outcome(memory_id, outcome, worked)`

## Testing

```bash
pytest tests/ -v --asyncio-mode=auto
```
