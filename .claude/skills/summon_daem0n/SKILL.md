---
name: summon-daem0n
description: Guide for initializing and consolidating Daem0n-MCP across project structures
---

# Summoning the Daem0n

This skill guides Claude through setting up Daem0n-MCP for various project structures.

## Single Repo Setup

For a single repository:

```bash
# Daem0n auto-initializes on first get_briefing()
# Just ensure you're in the project root
```

## Multi-Repo Setup (Client/Server Split)

When you have related repos that should share context:

### Option A: Consolidated Parent (Recommended)

Best when repos are siblings under a common parent:

```
/repos/
├── backend/
└── client/
```

**Steps:**

1. **Navigate to parent directory**
   ```bash
   cd /repos
   ```

2. **Initialize Daem0n in parent**
   ```
   Call get_briefing(project_path="/repos")
   ```

3. **If child repos already have .daem0nmcp data, consolidate:**
   ```
   # Link the children first
   Call link_projects(linked_path="/repos/backend", relationship="same-project")
   Call link_projects(linked_path="/repos/client", relationship="same-project")

   # Merge their databases into parent
   Call consolidate_linked_databases(archive_sources=True)
   ```

4. **Verify consolidation**
   ```
   Call get_briefing(project_path="/repos")
   # Should show combined memory count
   ```

### Option B: Linked but Separate

Best when repos need their own isolated histories but cross-awareness:

```
# In each repo, link to siblings
cd /repos/backend
Call link_projects(linked_path="/repos/client", relationship="same-project")

cd /repos/client
Call link_projects(linked_path="/repos/backend", relationship="same-project")
```

Then use `include_linked=True` on recall to span both.

## Migrating Existing Setup

If you've been launching Claude from parent directory and have a "messy" .daem0nmcp:

1. **Backup existing data**
   ```bash
   cp -r /repos/.daem0nmcp /repos/.daem0nmcp.backup
   ```

2. **Review what's there**
   ```
   Call get_briefing(project_path="/repos")
   # Check statistics and recent decisions
   ```

3. **If data is salvageable, keep it**
   - Link child repos for future cross-awareness
   - Use consolidated parent approach going forward

4. **If data is too messy, start fresh**
   ```bash
   rm -rf /repos/.daem0nmcp
   # Re-initialize with get_briefing()
   ```

## Key Commands Reference

| Command | Purpose |
|---------|---------|
| `get_briefing()` | Initialize session, creates .daem0nmcp if needed |
| `link_projects()` | Create cross-repo awareness link |
| `list_linked_projects()` | See all linked repos |
| `consolidate_linked_databases()` | Merge child DBs into parent |
| `recall(include_linked=True)` | Search across linked repos |

## Endless Mode (v2.12.0)

Reduce token usage by 50-75% in recalls and briefings using condensed mode:

```python
# Use condensed mode for token-efficient recall
recall(query="authentication", condensed=True)

# Returns memories without rationale/context, truncated to 150 chars
# Perfect for: focus areas, prefetching, large context windows
```

**When to use condensed mode:**
- Large codebases with many memories
- Prefetching context before tasks
- Focus area summaries
- When you need breadth over depth

**When to use full mode (default):**
- Investigating specific decisions
- Understanding why something was done
- Learning from past failures

## Passive Capture (v2.13.0)

Automatically capture decisions and surface memories without explicit calls.

### Setting Up Passive Hooks

Copy the hook configuration to your Claude Code settings:

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

### What Each Hook Does

| Hook | Event | Behavior |
|------|-------|----------|
| **Pre-Edit** | Before Edit/Write | Auto-recalls warnings, patterns, failed approaches for the file |
| **Post-Edit** | After Edit/Write | Suggests `remember()` for significant changes (architecture, security, API) |
| **Stop** | End of response | Auto-extracts decisions from Claude's text and creates memories |

### Passive Capture Flow

```
1. User starts editing file
   ↓ PreToolUse hook
2. Daem0n recalls memories for that file
   ↓ Context injected
3. User sees warnings/patterns/decisions
   ↓
4. User completes edit
   ↓ PostToolUse hook
5. If significant: suggest remember()
   ↓
6. Claude completes response
   ↓ Stop hook
7. Auto-extract decisions from text
   ↓
8. Create memories automatically
```

### CLI Remember Command

Hooks use the CLI to create memories:

```bash
# Create a memory from CLI (used by hooks)
python -m daem0nmcp.cli remember \
  --category decision \
  --content "Use JWT for authentication" \
  --rationale "Stateless, scalable" \
  --file-path src/auth.py \
  --json
```

## Best Practices

1. **One project_path per logical project** - Even if split across repos
2. **Use parent directory for shared context** - `/repos/` not `/repos/backend/`
3. **Link before consolidating** - Links define what to merge
4. **Archive, don't delete** - `archive_sources=True` preserves originals
5. **Verify after consolidation** - Check memory counts match expectations
6. **Enable passive hooks** - Let Daem0n capture decisions automatically
7. **Use condensed mode** - For large projects, use `condensed=True` to save tokens
