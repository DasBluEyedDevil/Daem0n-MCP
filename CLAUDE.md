# CLAUDE.md

Guidance for Claude Code when working with this repository.

## Project Overview

Daem0nMCP is a focused MCP server providing **AI memory and decision trees** with **semantic understanding**. It gives AI agents:
- Persistent memory across sessions (decisions, patterns, warnings, learnings)
- TF-IDF based semantic search (not just keywords)
- Time-weighted recall (recent memories matter more)
- Permanent memories for patterns/warnings (project facts don't decay)
- Conflict detection (warns about contradicting decisions)
- Rule-based decision trees for consistent behavior
- File-level memory associations
- Git awareness (shows changes since last session)
- Outcome tracking for learning from success/failure

## Commands

```bash
# Install
pip install -e .

# Run the MCP server
python -m daem0nmcp.server

# Run tests
pytest tests/ -v --asyncio-mode=auto
```

## Architecture

```
daem0nmcp/
├── server.py      # MCP server, 15 tools (FastMCP)
├── memory.py      # MemoryManager - semantic store/recall with decay
├── rules.py       # RulesEngine - TF-IDF matched decision trees
├── similarity.py  # TF-IDF index, cosine similarity, conflict detection
├── vectors.py     # Optional vector embeddings (sentence-transformers)
├── database.py    # DatabaseManager - async SQLite
├── models.py      # SQLAlchemy models (2 tables)
├── cli.py         # Command-line interface for pre-commit hooks
└── config.py      # Pydantic settings

scripts/
└── pre-commit     # Git hook for memory-aware commits
```

**Data Storage:** `<project_root>/.daem0nmcp/storage/daem0nmcp.db`

## Database Schema (2 tables)

**memories**: Stores decisions, patterns, warnings, learnings
- category, content, rationale, context, tags, keywords
- file_path (link memory to specific files)
- is_permanent (patterns/warnings never decay)
- outcome tracking (outcome, worked)
- TF-IDF indexed for semantic search

**rules**: Decision tree nodes
- trigger, trigger_keywords (TF-IDF indexed)
- must_do, must_not, ask_first, warnings
- priority, enabled

## Key Patterns

- **Async-first**: All database operations use async/await
- **TF-IDF similarity**: Content is indexed for semantic matching (not just keywords)
- **Memory decay**: Decisions/learnings decay over time; patterns/warnings are permanent
- **Conflict detection**: New memories checked against existing for contradictions
- **Failed decision boosting**: Failed outcomes are highlighted in recalls (1.5x boost)
- **Git awareness**: Briefing shows changes since last memory

## MCP Tools (17 total)

Core:
1. `remember` - Store a memory with conflict detection and file association
2. `recall` - Semantic retrieval with decay weighting (TF-IDF + optional vectors)
3. `recall_for_file` - Get memories for a specific file
4. `add_rule` - Create decision tree node
5. `check_rules` - Semantic matching against rules
6. `record_outcome` - Track if decision worked (failures get boosted)
7. `get_briefing` - Smart session start with git changes

Utility:
8. `context_check` - Quick pre-flight check (recall + rules combined)
9. `search_memories` - Semantic search across all memories
10. `list_rules` - Show all rules
11. `update_rule` - Modify existing rule
12. `find_related` - Discover connected memories
13. `scan_todos` - Find TODO/FIXME/HACK comments in codebase
14. `ingest_doc` - Fetch and store external documentation as learnings
15. `propose_refactor` - Generate refactor context from memory + todos
16. `rebuild_index` - Force rebuild of TF-IDF index for rules
17. `health` - Get server health, version, and statistics

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

1. **Session Start**: Call `get_briefing(focus_areas=["topic1", "topic2"])`
2. **Before Changes**: Call `context_check(description)` for quick guidance
3. **File-Level**: Call `recall_for_file(path)` when touching a file
4. **Detailed Lookup**: Call `recall(topic)` and `check_rules(action)` separately
5. **Making Decisions**: Call `remember(category, content, rationale, file_path)`
6. **After Implementation**: Call `record_outcome(memory_id, outcome, worked)`

## Testing

```bash
pytest tests/ -v --asyncio-mode=auto
```

88 tests covering:
- Memory CRUD and semantic recall
- TF-IDF indexing and similarity
- Vector embeddings and hybrid search
- Code symbol extraction
- Memory decay calculations
- Conflict detection
- Rule matching and priority
- File-level associations
- TODO/FIXME scanner
- All edge cases
