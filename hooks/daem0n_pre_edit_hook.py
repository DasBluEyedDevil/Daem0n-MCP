#!/usr/bin/env python3
"""
Daem0n Pre-Edit Hook - Auto-recall memories for files being edited

This hook runs BEFORE Edit/Write/NotebookEdit tools.
It checks if Daem0n has memories for the file being modified and
injects them as context so Claude is aware of past decisions.

Output format: Text injected as context for Claude
Exit code 0: Success (output added to context)
"""

import json
import os
import sys
from pathlib import Path

# Environment variables from Claude Code
PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR", "")
TOOL_INPUT = os.environ.get("TOOL_INPUT", "{}")

# MCP server URL (for HTTP transport on Windows)
MCP_URL = os.environ.get("DAEM0NMCP_URL", "http://localhost:9876/mcp")


def get_file_path_from_tool_input() -> str | None:
    """Extract file_path from the tool input JSON."""
    try:
        input_data = json.loads(TOOL_INPUT)
        # Edit and Write tools use "file_path"
        # NotebookEdit uses "notebook_path"
        return input_data.get("file_path") or input_data.get("notebook_path")
    except (json.JSONDecodeError, TypeError):
        return None


def has_daem0n_setup() -> bool:
    """Check if Daem0n is set up in this project."""
    if not PROJECT_DIR:
        return False
    daem0n_dir = Path(PROJECT_DIR) / ".daem0nmcp"
    return daem0n_dir.exists()


def recall_for_file_sync(file_path: str) -> dict | None:
    """
    Call recall_for_file via the Daem0n CLI (synchronous).

    We use CLI instead of HTTP to avoid async complexity in hooks.
    The CLI check command returns warnings, must_do, must_not.
    """
    import subprocess

    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "daem0nmcp.cli",
                "check", file_path,
                "--project-path", PROJECT_DIR,
                "--json"
            ],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=PROJECT_DIR
        )

        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        pass

    return None


def format_memories_context(memories: dict) -> str:
    """Format memories as human-readable context.

    The CLI check command returns:
    - warnings: list of {type, content, outcome?}
    - must_do: list of strings
    - must_not: list of strings
    - blockers: list (usually empty for file checks)
    """
    parts = []
    file_name = Path(memories.get("file", "")).name

    # Warnings are most important
    warnings = memories.get("warnings", [])

    # Split warnings by type
    failed_approaches = [w for w in warnings if w.get("type") == "FAILED_APPROACH"]
    general_warnings = [w for w in warnings if w.get("type") == "WARNING"]
    rule_warnings = [w for w in warnings if w.get("type") == "RULE_WARNING"]

    if failed_approaches:
        parts.append("**Failed approaches (avoid repeating):**")
        for f in failed_approaches[:3]:  # Limit to 3
            content = f.get("content", "")[:150]
            parts.append(f"  - {content}")
            outcome = f.get("outcome")
            if outcome:
                parts.append(f"    Outcome: {outcome[:100]}")

    if general_warnings:
        parts.append("**Warnings for this file:**")
        for w in general_warnings[:3]:  # Limit to 3
            content = w.get("content", "")[:150]
            parts.append(f"  - {content}")

    if rule_warnings:
        parts.append("**Rule warnings:**")
        for w in rule_warnings[:2]:  # Limit to 2
            content = w.get("content", "")[:150]
            parts.append(f"  - {content}")

    # Must do / Must not from rules
    must_do = memories.get("must_do", [])
    if must_do:
        parts.append("**Must do:**")
        for item in must_do[:3]:
            parts.append(f"  - {item[:100]}")

    must_not = memories.get("must_not", [])
    if must_not:
        parts.append("**Must NOT do:**")
        for item in must_not[:3]:
            parts.append(f"  - {item[:100]}")

    return "\n".join(parts)


def main():
    """Main hook logic."""
    # Skip if Daem0n not set up
    if not has_daem0n_setup():
        sys.exit(0)

    # Get file path from tool input
    file_path = get_file_path_from_tool_input()
    if not file_path:
        sys.exit(0)

    # Recall memories for this file
    memories = recall_for_file_sync(file_path)
    if not memories:
        sys.exit(0)

    # Check if there are any relevant memories
    has_content = (
        memories.get("warnings") or
        memories.get("must_do") or
        memories.get("must_not") or
        memories.get("blockers")
    )

    if not has_content:
        sys.exit(0)

    # Format and output context
    context = format_memories_context(memories)
    if context:
        file_name = Path(file_path).name
        print(f"[Daem0n recalls for {file_name}]\n{context}")

    sys.exit(0)


if __name__ == "__main__":
    main()
