#!/usr/bin/env python3
"""
Daem0n UserPromptSubmit Hook - Injects context reminder into every prompt

This hook runs when the user submits a prompt.
For UserPromptSubmit hooks, stdout is added as context to Claude's input.

This provides a subtle, persistent reminder about the Daem0n protocol.
"""

import json
import os
import sys
from pathlib import Path

PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR", "")


def has_daem0n_tools() -> bool:
    """Check if this project likely has Daem0n set up."""
    if not PROJECT_DIR:
        return False

    # Check for .daem0nmcp directory or skill
    daem0n_dir = Path(PROJECT_DIR) / ".daem0nmcp"
    skill_dir = Path(PROJECT_DIR) / ".claude" / "skills" / "daem0nmcp-protocol"

    return daem0n_dir.exists() or skill_dir.exists()


def main():
    """Output context reminder if Daem0n is set up."""
    if not has_daem0n_tools():
        # No Daem0n setup detected, don't add reminder
        sys.exit(0)

    # This output gets added as context to Claude's input
    reminder = (
        "[Daem0n Protocol Reminder] "
        "When completing tasks: (1) record decisions with remember(), "
        "(2) record outcomes with record_outcome() when done. "
        "Failures are valuable - always record them."
    )

    print(reminder)
    sys.exit(0)


if __name__ == "__main__":
    main()
