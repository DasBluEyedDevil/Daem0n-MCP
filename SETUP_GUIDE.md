# DevilMCP Setup Guide for Claude Code

## Quick Start (Windows)

### Option 1: Automated Setup (Recommended)

1. **Run the setup script:**
   ```cmd
   setup_and_run.bat
   ```

   This script will:
   - Create a Python virtual environment
   - Install all dependencies
   - Create the storage directory
   - Start the DevilMCP server

2. **Keep the server running** in that terminal window

3. **Configure Claude Code** (see Configuration section below)

### Option 2: Manual Setup

1. **Create virtual environment:**
   ```cmd
   python -m venv venv
   venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```cmd
   pip install -r requirements.txt
   ```

3. **Create storage directory:**
   ```cmd
   mkdir storage
   ```

4. **Configure environment (optional):**
   ```cmd
   copy .env.example .env
   REM Edit .env if you want to customize settings
   ```

5. **Run the server:**
   ```cmd
   python server.py
   ```

## Configuring Claude Code

### Method 1: Using MCP Configuration File

1. **Locate your Claude Code config directory:**
   - Windows: `%APPDATA%\Claude\`
   - Mac: `~/Library/Application Support/Claude/`
   - Linux: `~/.config/Claude/`

2. **Edit `claude_desktop_config.json`** (create if it doesn't exist):

   ```json
   {
     "mcpServers": {
       "devilmcp": {
         "command": "python",
         "args": [
           "C:\\Users\\dasbl\\AndroidStudioProjects\\DevilMCP\\server.py"
         ],
         "env": {
           "PORT": "8080",
           "LOG_LEVEL": "INFO",
           "STORAGE_PATH": "./storage",
           "MAX_CONTEXT_DEPTH": "10"
         }
       }
     }
   }
   ```

   **IMPORTANT:** Update the path in `args` to match your actual installation directory!

3. **Restart Claude Code** completely (quit and relaunch)

### Method 2: Using Virtual Environment (If Method 1 doesn't work)

If Claude Code has trouble finding Python, use the venv's Python directly:

```json
{
  "mcpServers": {
    "devilmcp": {
      "command": "C:\\Users\\dasbl\\AndroidStudioProjects\\DevilMCP\\venv\\Scripts\\python.exe",
      "args": [
        "C:\\Users\\dasbl\\AndroidStudioProjects\\DevilMCP\\server.py"
      ],
      "env": {
        "STORAGE_PATH": "C:\\Users\\dasbl\\AndroidStudioProjects\\DevilMCP\\storage"
      }
    }
  }
}
```

## Verifying the Setup

### 1. Test the server directly:

```cmd
python test_server.py
```

### 2. Check if Claude Code sees the server:

In Claude Code, you should see DevilMCP's tools available, including:
- `analyze_project_structure`
- `track_file_dependencies`
- `log_decision`
- `analyze_change_impact`
- `analyze_cascade_risk`
- And 25+ more tools!

### 3. Try a test command in Claude Code:

Ask Claude Code:
> "Use the analyze_project_structure tool to analyze this project"

## Troubleshooting

### Server won't start

**Error: Module not found**
```cmd
# Ensure you're in the virtual environment
venv\Scripts\activate
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

**Error: Port already in use**
```cmd
# Change port in .env file
echo PORT=8081 > .env
```

### Claude Code can't connect

**Check the server is running:**
- The terminal running `python server.py` should show "Starting DevilMCP server"
- No errors should be displayed

**Check the config path:**
- Make sure the path in `claude_desktop_config.json` uses `\\` (double backslashes) on Windows
- Use absolute paths, not relative paths

**Check Python path:**
- Try using the full path to the venv's Python: `C:\Users\dasbl\AndroidStudioProjects\DevilMCP\venv\Scripts\python.exe`

**Restart Claude Code:**
- Completely quit Claude Code (not just close the window)
- Relaunch it

### Permission errors

**Storage directory:**
```cmd
# Ensure storage directory exists and is writable
mkdir storage
```

**Python packages:**
```cmd
# Try installing with user flag
pip install -r requirements.txt --user
```

## Using DevilMCP with Claude Code

Once configured, Claude Code will automatically have access to all DevilMCP tools. Here are some example prompts:

### Starting a Session
> "Start a thought session for implementing the authentication feature"

### Analyzing Before Changes
> "Analyze the cascade risk of changing the auth module"

### Tracking Decisions
> "Log a decision to use JWT authentication with the rationale being better scalability"

### Getting Context
> "Get the full project context for this codebase"

### Checking Your Thinking
> "Analyze my reasoning gaps to see if I'm missing anything"

## Next Steps

1. ✅ Run `setup_and_run.bat` to start the server
2. ✅ Configure Claude Code's `claude_desktop_config.json`
3. ✅ Restart Claude Code
4. ✅ Test with: "Use analyze_project_structure on this project"
5. ✅ Start using DevilMCP's powerful context management!

## Need Help?

- Check server logs in the terminal running `python server.py`
- Review the main README.md for tool documentation
- Ensure all dependencies are installed: `pip list`
