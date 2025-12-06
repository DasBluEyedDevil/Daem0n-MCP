# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DevilMCP is an MCP (Model Context Protocol) server that provides long-term memory and context management for AI agents. It solves "AI amnesia" by persisting architectural decisions, tracking code change impacts, detecting cascade failures, and managing tasks across sessions.

## Commands

```bash
# Install (editable mode)
pip install -e .

# Run the MCP server
python -m devilmcp.server
# Or via console script:
devilmcp

# Run tests
pytest devilmcp/
pytest -v --asyncio-mode=auto  # For async tests
```

## Architecture

```
┌─────────────────────────────────────┐
│  FastMCP Server (server.py)         │  ← Entry point, exposes MCP tools
├─────────────────────────────────────┤
│  Feature Modules                    │
│  • context_manager.py   → Project structure & dependency analysis
│  • decision_tracker.py  → Architectural decision logging
│  • change_analyzer.py   → Code change impact prediction
│  • cascade_detector.py  → Cascade failure detection (auto-hydrates from DB)
│  • task_manager.py      → Task/todo management
│  • thought_processor.py → AI reasoning chain tracking
│  • tool_registry.py     → CLI tool management (with security whitelist)
│  • subprocess_executor.py → Stateless subprocess execution
├─────────────────────────────────────┤
│  parsers/                           │
│  • python_parser.py     → Python AST parsing (stdlib ast)
│  • javascript_parser.py → JS parsing (tree-sitter + regex fallback)
├─────────────────────────────────────┤
│  database.py + models.py            │  ← SQLAlchemy ORM, async SQLite
└─────────────────────────────────────┘
```

**Data Storage:** Each project gets isolated storage at `<project_root>/.devilmcp/storage/devilmcp.db`

## Key Patterns

- **Async-first:** All database operations and managers use `async`/`await`
- **SQLAlchemy ORM:** Models in `models.py` (Decision, Change, Task, Tool, etc.)
- **FastMCP framework:** Tools defined as decorated async functions in `server.py`
- **Git-aware:** Context manager respects `.gitignore` for project scanning
- **AST parsing:** Python uses stdlib `ast`, JS uses tree-sitter (no fallback)
- **Auto-hydration:** CascadeDetector loads dependency graph from DB automatically

## Security

Tool execution is **disabled by default**. To enable:

```bash
# Enable tool execution
export DEVILMCP_TOOL_EXECUTION_ENABLED=true

# Whitelist allowed commands (minimal safe default)
export DEVILMCP_ALLOWED_COMMANDS="git,pytest"
```

**WARNING:** The command whitelist is NOT a sandbox. If you allow `python` or `node`, the AI agent can write and execute arbitrary code. This effectively grants shell access. For true isolation:
- Run DevilMCP inside a Docker container
- Or only allow read-only commands like `git status`

## Adding New MCP Tools

1. Define the tool in `server.py` using `@mcp.tool()` decorator
2. Tools are async functions that can access module-level managers
3. Example pattern from existing tools:
```python
@mcp.tool()
async def my_new_tool(param: str) -> str:
    """Description shown to AI agents."""
    result = await some_manager.do_work(param)
    return json.dumps(result)
```

## Custom CLI Tools

Register external tools in `tools.toml` (see `tools.toml.example`):
```toml
[tools.my-tool]
display_name = "My Tool"
command = "python"
args = ["-c", "print('hello')"]
capabilities = ["testing", "utilities"]
enabled = true
```

## AI Agent Integration

When AI agents connect via MCP, they should follow protocols from `AI_INSTRUCTIONS.md`:
- **First Contact:** Call `get_project_context(summary_only=True)` then `list_tasks(status="todo")`
- **Before Edits:** Call `get_focused_context(file_path)` and `analyze_change_impact()`
- **Log Decisions:** Call `log_decision()` immediately for architectural choices
