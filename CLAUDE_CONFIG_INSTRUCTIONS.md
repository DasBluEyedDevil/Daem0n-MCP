# Configure Claude Code to Use DevilMCP

## ✅ DevilMCP Server Status
**Status:** Running on http://127.0.0.1:8000
**Shell ID:** 00e3f4

## Step 1: Locate Claude Code Config

Find your Claude Code configuration directory:
- **Windows:** `%APPDATA%\Claude\`
  (Usually: `C:\Users\YourUsername\AppData\Roaming\Claude\`)
- **Mac:** `~/Library/Application Support/Claude/`
- **Linux:** `~/.config/Claude/`

## Step 2: Edit claude_desktop_config.json

Create or edit the file `claude_desktop_config.json` in that directory.

### Configuration for DevilMCP

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "devilmcp": {
      "command": "python",
      "args": [
        "C:\\Users\\dasbl\\AndroidStudioProjects\\DevilMCP\\server.py"
      ],
      "cwd": "C:\\Users\\dasbl\\AndroidStudioProjects\\DevilMCP"
    }
  }
}
```

**IMPORTANT:** Update the paths if you've installed DevilMCP in a different location!

### Alternative: Using Virtual Environment Python

If Claude Code has issues finding Python, use the venv's Python directly:

```json
{
  "mcpServers": {
    "devilmcp": {
      "command": "C:\\Users\\dasbl\\AndroidStudioProjects\\DevilMCP\\venv\\Scripts\\python.exe",
      "args": [
        "server.py"
      ],
      "cwd": "C:\\Users\\dasbl\\AndroidStudioProjects\\DevilMCP"
    }
  }
}
```

## Step 3: Restart Claude Code

1. **Completely quit Claude Code** (not just close the window - use File → Quit or Alt+F4)
2. **Wait 2-3 seconds**
3. **Relaunch Claude Code**

## Step 4: Verify It's Working

In Claude Code, try these test commands:

### Test 1: Check Server Statistics
```
Use the get_mcp_statistics tool from DevilMCP
```

### Test 2: Analyze Project
```
Use analyze_project_structure to analyze this project
```

### Test 3: List Available Tools
```
What DevilMCP tools are available?
```

You should see 30+ tools available including:
- analyze_project_structure
- track_file_dependencies
- log_decision
- analyze_change_impact
- analyze_cascade_risk
- start_thought_session
- And many more!

## Troubleshooting

### Issue: Claude Code doesn't see DevilMCP

**Solution 1:** Check the server is running
```cmd
# In PowerShell or Command Prompt
curl http://127.0.0.1:8000
```

If nothing responds, restart the server:
```cmd
cd C:\Users\dasbl\AndroidStudioProjects\DevilMCP
python server.py
```

**Solution 2:** Check config file path
- Ensure you edited the correct `claude_desktop_config.json` file
- On Windows, check both:
  - `%APPDATA%\Claude\claude_desktop_config.json`
  - `%LOCALAPPDATA%\Claude\claude_desktop_config.json`

**Solution 3:** Check JSON syntax
- Use a JSON validator (https://jsonlint.com/) to verify your config
- Common mistakes: missing commas, wrong quotes, backslash issues

**Solution 4:** Check logs
- Windows: `%APPDATA%\Claude\logs\`
- Look for MCP-related errors

### Issue: Server won't start

**Check if port is in use:**
```cmd
netstat -ano | findstr :8000
```

If port 8000 is busy, edit `.env` to use a different port:
```
PORT=8001
```

### Issue: Import errors when starting server

**Reinstall dependencies:**
```cmd
cd C:\Users\dasbl\AndroidStudioProjects\DevilMCP
python -m pip install -r requirements.txt --force-reinstall
```

## Running the Server Automatically

### Option 1: Startup Script
Create a shortcut to `setup_and_run.bat` in your Startup folder:
1. Press `Win+R`, type `shell:startup`, press Enter
2. Right-click → New → Shortcut
3. Point to: `C:\Users\dasbl\AndroidStudioProjects\DevilMCP\setup_and_run.bat`

### Option 2: Windows Service (Advanced)
Use NSSM (Non-Sucking Service Manager) to run DevilMCP as a Windows service.

## Using DevilMCP with Claude Code

Once configured, Claude Code will have access to all DevilMCP capabilities:

### Example Prompts

**Starting a work session:**
> "Start a thought session for refactoring the authentication system"

**Before making changes:**
> "Analyze the cascade risk of modifying the user authentication module"

**Tracking decisions:**
> "Log a decision to migrate to PostgreSQL with the rationale being better performance and JSONB support"

**Getting project context:**
> "Get the complete project context for this codebase"

**Checking reasoning:**
> "Analyze my reasoning gaps to identify any blind spots"

## Next Steps

1. ✅ Server is running (http://127.0.0.1:8000)
2. ⬜ Configure Claude Code (edit claude_desktop_config.json)
3. ⬜ Restart Claude Code
4. ⬜ Test with: "Use get_mcp_statistics from DevilMCP"
5. ⬜ Start using DevilMCP's powerful features!

## Need Help?

- Server logs: Check terminal where `python server.py` is running
- Storage path: `C:\Users\dasbl\AndroidStudioProjects\DevilMCP\storage`
- README: See main `README.md` for tool documentation
- Issues: Review `SETUP_GUIDE.md` for detailed troubleshooting

---

**Remember:** The server must be running for Claude Code to access it. Keep the terminal window open where you ran `python server.py`!
