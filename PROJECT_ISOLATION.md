# DevilMCP Project Isolation Guide

## Overview

DevilMCP automatically provides **per-project data isolation** while keeping the server code centralized. Each project you work on gets its own isolated storage for decisions, changes, context, and thoughts.

## How It Works

### Automatic Project Detection

When Claude Code starts DevilMCP, the server automatically detects which project is calling it by examining the current working directory. Based on this detection:

- **Project-Specific Storage**: Data is stored in `<project-root>/.devilmcp/storage/`
- **Isolated Data**: Each project's decisions, changes, and context are kept separate
- **No Manual Configuration**: Works automatically for all projects

### Storage Location Priority

The server determines storage location using this priority:

1. **`STORAGE_PATH` environment variable** - Explicit override (if set)
2. **`PROJECT_ROOT` environment variable** - Uses `$PROJECT_ROOT/.devilmcp/storage`
3. **Current working directory** - Uses `<cwd>/.devilmcp/storage` (default for Claude Code)
4. **Fallback** - Uses centralized storage if running from DevilMCP directory

## Project Directory Structure

When you use DevilMCP in a project, it creates:

```
YourProject/
├── .devilmcp/
│   └── storage/
│       ├── context.db        # Project structure and dependencies
│       ├── decisions.db      # Decision history
│       ├── changes.db        # Change tracking
│       ├── cascades.db       # Cascade events
│       └── thoughts.db       # Thought processes
├── src/
├── README.md
└── ... (your project files)
```

## Configuration

### Current Setup (Automatic Isolation)

Your Claude Code configuration at:
`C:\Users\dasbl\AppData\Roaming\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "devilmcp": {
      "command": "C:\\Users\\dasbl\\AndroidStudioProjects\\DevilMCP\\venv\\Scripts\\python.exe",
      "args": [
        "-u",
        "C:\\Users\\dasbl\\AndroidStudioProjects\\DevilMCP\\server.py"
      ],
      "env": {
        "PYTHONPATH": "C:\\Users\\dasbl\\AndroidStudioProjects\\DevilMCP"
      }
    }
  }
}
```

**Key Points:**
- ✅ No `cwd` specified = uses Claude Code's working directory (your project)
- ✅ Absolute path to `server.py` = server code stays centralized
- ✅ `PYTHONPATH` set = imports work correctly
- ✅ `-u` flag = unbuffered output for better logging

## Usage Examples

### Example 1: Working on Project A

```bash
cd C:\Projects\ProjectA
# Start Claude Code here
# DevilMCP stores data in: C:\Projects\ProjectA\.devilmcp\storage\
```

### Example 2: Working on Project B

```bash
cd C:\Projects\ProjectB
# Start Claude Code here
# DevilMCP stores data in: C:\Projects\ProjectB\.devilmcp\storage\
```

### Example 3: Multiple Projects

Projects A and B have completely isolated data:
- ProjectA decisions don't appear in ProjectB
- ProjectB changes don't affect ProjectA tracking
- Each maintains its own context and history

## Benefits of This Approach

✅ **Automatic Isolation** - No manual configuration per project
✅ **Centralized Server** - One codebase, easy to update
✅ **Clean Projects** - Data stored in hidden `.devilmcp` folder
✅ **Git-Friendly** - Add `.devilmcp/` to `.gitignore` if desired
✅ **Cross-Project Updates** - Update server once, all projects benefit

## Git Integration

You can choose to:

### Option 1: Ignore DevilMCP Data (Recommended for Personal Use)

Add to your `.gitignore`:
```
.devilmcp/
```

### Option 2: Commit DevilMCP Data (Team Collaboration)

Keep `.devilmcp/` in version control to share:
- Project decisions and rationale
- Change history and impact
- Architectural context

This can be valuable for team collaboration and project documentation.

## Troubleshooting

### Check Which Storage Is Being Used

When the server starts, it logs:
```
INFO - Project detected: YourProjectName
INFO - Using project-specific storage: C:\path\to\project\.devilmcp\storage
```

### Force Specific Storage Location

Set environment variable:
```bash
export STORAGE_PATH=/path/to/custom/storage
```

### Centralized Storage (Old Behavior)

If you prefer centralized storage for all projects:
```json
{
  "devilmcp": {
    "command": "...",
    "args": ["..."],
    "env": {
      "PYTHONPATH": "...",
      "STORAGE_PATH": "C:\\Users\\dasbl\\AndroidStudioProjects\\DevilMCP\\storage\\centralized"
    }
  }
}
```

## Advanced: Per-Project Configuration

If you want different settings per project, create a `.env` file in your project root:

```bash
# ProjectA/.env
LOG_LEVEL=DEBUG
MAX_CONTEXT_DEPTH=15
```

```bash
# ProjectB/.env
LOG_LEVEL=INFO
MAX_CONTEXT_DEPTH=10
```

DevilMCP will load the `.env` file from the project directory.

## Verification

To verify project isolation is working:

1. Start Claude Code in Project A
2. Use a DevilMCP tool (e.g., log a decision)
3. Check that `ProjectA/.devilmcp/storage/` was created
4. Switch to Project B
5. Use another DevilMCP tool
6. Check that `ProjectB/.devilmcp/storage/` was created separately

## Summary

🎯 **You're all set!** DevilMCP now provides automatic per-project isolation while keeping the server code centralized. Each project gets its own clean data storage, and you never have to think about it.
