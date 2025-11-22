# DevilMCP

DevilMCP is an advanced **Context Management System** for AI agents (like Claude, Cursor, or Windsurf) that acts as a long-term memory and project manager. It solves the problem of AI "amnesia" by tracking decisions, analyzing codebase impact, and detecting potential cascade failures.

## 🚀 Key Benefits

*   **Memory:** Remembers architectural decisions so you don't have to repeat yourself.
*   **Safety:** Predicts "blast radius" of code changes before they happen.
*   **Task Management:** Tracks what needs to be done directly within the chat.
*   **Project Isolation:** Automatically maintains separate contexts for each project you work on.

---

## 📦 Installation

DevilMCP is designed for **autonomous setup by your AI assistant**.

1.  **Download the repository:**
    ```bash
    git clone https://github.com/yourusername/DevilMCP.git
    ```
    or simply download and unzip the archive to a convenient location (e.g., `C:/Tools/DevilMCP`).

2.  **Point your AI to `AI_INSTRUCTIONS.md`:**
    Once the files are on your system, open your AI assistant (Claude, Cursor, etc.) and provide it with the full path to the `AI_INSTRUCTIONS.md` file located in the root of the DevilMCP directory.

    *Example Prompt:*
    ```
    Please read and execute the instructions in "C:/Path/To/DevilMCP/AI_INSTRUCTIONS.md"
    ```
    Your AI will then autonomously install DevilMCP and configure its connection.

---

## ⚙️ Configuration

Your AI assistant will handle the configuration automatically once you point it to `AI_INSTRUCTIONS.md`. It will locate its own configuration file and integrate DevilMCP as an MCP server.

**Note on Automatic Project Isolation:** `STORAGE_PATH` is typically left empty in the configuration. This allows DevilMCP to create a hidden `.devilmcp/` folder (containing `devilmcp.db`) in whichever project directory you are currently working in. This ensures each project has its own isolated data.

---

## 🖥️ Usage

DevilMCP is primarily designed to be used by your AI agent.

### AI Agent Mode (Server)
When connected to Claude or an IDE, the agent will automatically use these tools:

*   **`get_project_context`**: Analyzes your file structure.
*   **`log_decision`**: Records architectural choices.
*   **`create_task`**: Manages your todo list.
*   **`analyze_change_impact`**: Checks for breaking changes.

---

## 🧠 AI Integration Guide

To get the best results, provide the contents of `AI_INSTRUCTIONS.md` (found in this repo) to your AI assistant as a "System Prompt" or "Custom Instruction".

**Core Rules for the AI:**
1.  **Always Check Context First:** Run `get_project_context()`.
2.  **Log Every Decision:** Use `log_decision()` for architectural choices.
3.  **Predict Before Changing:** Run `analyze_change_impact()` before writing code.

---

## 🏗️ Architecture

DevilMCP uses a modular architecture backed by **SQLite** for robust data persistence.

*   **Core Logic:** Located in `devilmcp/` package.
*   **Data Storage:** `.devilmcp/storage/devilmcp.db` (SQLite) inside your project root.
*   **Entry Points:** `devilmcp` command (installed via pip) or `devilmcp/server.py`.

### Custom Tools
You can register your own local CLI tools for the agent to use by creating a `tools.toml` file in your project root. See `tools.toml.example` for details.

---

## 🔄 Database Migration
If you are upgrading from v1 (JSON storage), run:
```bash
python scripts/migrate_json_to_sqlite.py "/path/to/your/project"
```

---

*DevilMCP: Because AI agents should know what they're doing, why they're doing it, and what might break when they do it.*