# DevilMCP: AI Memory System - Setup & Usage

**Instructions for AI Assistants (Claude, Cursor, Windsurf, etc.)**

---

## What is DevilMCP?

DevilMCP gives you **persistent memory** and **decision trees**:
- Remember decisions, patterns, warnings, and learnings across sessions
- Get guidance from rules before taking actions
- Learn from outcomes (what worked, what didn't)

---

## Installation

```bash
pip install -e "/path/to/DevilMCP"
```

Verify: `python -c "import devilmcp; print('OK')"`

---

## MCP Configuration

Add to your MCP config file:

**Claude Desktop/Code:**
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Mac: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

**Cursor:** `~/.cursor/mcp.json`

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

Restart after configuration.

---

## Your Protocol

### 1. Session Start
```
Call: get_briefing()
```
This loads your context: recent decisions, warnings, rules.

### 2. Before Making Changes
```
Call: recall("topic")           # Get relevant memories
Call: check_rules("action")     # Get guidance
```

Follow `must_do` items. Avoid `must_not` items. Consider `ask_first` questions.

### 3. When Making Decisions
```
Call: remember(
    category="decision",
    content="What you decided",
    rationale="Why",
    tags=["relevant", "tags"]
)
```

Categories: `decision`, `pattern`, `warning`, `learning`

### 4. After Implementation
```
Call: record_outcome(
    memory_id=<id from remember>,
    outcome="What happened",
    worked=true/false
)
```

---

## Available Tools

| Tool | Purpose |
|------|---------|
| `remember` | Store a decision/pattern/warning/learning |
| `recall` | Get relevant memories for a topic |
| `add_rule` | Create a decision tree rule |
| `check_rules` | Get guidance before an action |
| `record_outcome` | Track if a decision worked |
| `get_briefing` | Session start summary |
| `search_memories` | Full-text search |
| `list_rules` | Show all rules |
| `update_rule` | Modify a rule |

---

## Example Session

```
AI: [Session start]
AI: get_briefing()
→ "3 memories, 1 warning, 2 rules configured"

User: "Add user authentication"

AI: recall("authentication")
→ Decision: "Use JWT tokens" (worked: true)
→ Warning: "Sessions caused scaling issues"

AI: check_rules("adding authentication")
→ must_do: ["Add rate limiting"]
→ must_not: ["Use session cookies"]

AI: remember(
    category="decision",
    content="Using OAuth2 with JWT",
    rationale="Aligns with existing pattern, stateless",
    tags=["auth", "api"]
)
→ id: 42

[After implementation]

AI: record_outcome(42, "OAuth2 working well", worked=true)
```

---

## Data Storage

Your memories are stored per-project at:
```
<project_root>/.devilmcp/storage/devilmcp.db
```

---

## Quick Reference

**Store something:**
```
remember("decision", "content", rationale="why", tags=["tag"])
```

**Get context:**
```
recall("topic")
get_briefing()
```

**Create rule:**
```
add_rule(
    trigger="when this happens",
    must_do=["do this"],
    must_not=["avoid this"]
)
```

**Check before acting:**
```
check_rules("what I'm about to do")
```

---

*DevilMCP: Your persistent memory across sessions.*
