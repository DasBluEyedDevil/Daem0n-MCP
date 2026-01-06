#!/usr/bin/env python3
"""
Daem0n Post-Edit Hook - Suggest remembering significant changes

This hook runs AFTER Edit/Write tools complete.
It analyzes the change and suggests calling remember() for significant modifications.

Output: Suggestion text (added to Claude's context)
Exit code 0: Success
"""

import json
import os
import sys
from pathlib import Path

PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR", "")
TOOL_INPUT = os.environ.get("TOOL_INPUT", "{}")
TOOL_OUTPUT = os.environ.get("TOOL_OUTPUT", "")

# Patterns indicating significant changes
SIGNIFICANT_PATTERNS = [
    # Architecture changes
    "class ", "def __init__", "async def ", "@dataclass", "@mcp.tool",
    # Configuration
    "config", "settings", "environment", "env",
    # Security
    "auth", "password", "token", "secret", "credential",
    # Database
    "migration", "schema", "model", "table", "column",
    # API
    "endpoint", "route", "api", "request", "response",
]

# File types that are usually significant
SIGNIFICANT_EXTENSIONS = [
    ".py", ".ts", ".js", ".go", ".rs", ".java",
    ".yaml", ".yml", ".json", ".toml",
    ".sql", ".prisma",
]


def get_tool_info() -> tuple[str | None, str | None]:
    """Extract file_path and change info from tool input/output."""
    try:
        input_data = json.loads(TOOL_INPUT)
        file_path = input_data.get("file_path")
        old_string = input_data.get("old_string", "")
        new_string = input_data.get("new_string", "")
        return file_path, f"{old_string} -> {new_string}"
    except (json.JSONDecodeError, TypeError):
        return None, None


def has_daem0n_setup() -> bool:
    """Check if Daem0n is set up."""
    if not PROJECT_DIR:
        return False
    return (Path(PROJECT_DIR) / ".daem0nmcp").exists()


def is_significant_change(file_path: str, change_content: str) -> bool:
    """Determine if this change is significant enough to remember."""
    if not file_path:
        return False

    # Check file extension
    ext = Path(file_path).suffix.lower()
    if ext not in SIGNIFICANT_EXTENSIONS:
        return False

    # Check for significant patterns in the change
    change_lower = change_content.lower()
    for pattern in SIGNIFICANT_PATTERNS:
        if pattern.lower() in change_lower:
            return True

    # Check change size (large changes are often significant)
    if len(change_content) > 500:
        return True

    return False


def main():
    """Main hook logic."""
    if not has_daem0n_setup():
        sys.exit(0)

    file_path, change_content = get_tool_info()
    if not file_path or not change_content:
        sys.exit(0)

    # Only suggest for significant changes
    if not is_significant_change(file_path, change_content):
        sys.exit(0)

    # Output suggestion
    filename = Path(file_path).name
    print(
        f"[Daem0n suggests] Significant change to {filename}. "
        f"Consider: remember(category='decision', content='...', file_path='{file_path}')"
    )

    sys.exit(0)


if __name__ == "__main__":
    main()
