#!/usr/bin/env python3
"""
Daem0n Stop Hook - Automatic reminder to record outcomes

This hook runs when Claude finishes responding (Stop event).
It detects task completion signals and reminds Claude to record outcomes
with Daem0n if appropriate.

Exit codes:
- 0: Success, no action needed (or reminder via JSON block)
- 2: Block - feeds stderr back to Claude (not used here, we use JSON instead)

Output:
- JSON with {"decision": "block", "reason": "..."} to inject reminder as next turn
- Empty/no output to let conversation end normally
"""

import json
import os
import re
import sys
from pathlib import Path

# Environment variables provided by Claude Code
TRANSCRIPT_PATH = os.environ.get("CLAUDE_TRANSCRIPT_PATH", "")
SESSION_ID = os.environ.get("CLAUDE_SESSION_ID", "")
PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR", "")

# State file to prevent infinite loops
STATE_DIR = Path.home() / ".daem0n_hook_state"
STATE_DIR.mkdir(exist_ok=True)

# Completion signal patterns (case-insensitive)
COMPLETION_PATTERNS = [
    r"\ball\s+(?:tasks?|todos?|items?)\s+(?:are\s+)?(?:complete|done|finished)\b",
    r"\bcompleted?\s+all\s+(?:tasks?|todos?|items?)\b",
    r"\bmarking\s+.*\s+as\s+completed?\b",
    r"\btask\s+(?:is\s+)?(?:complete|done|finished)\b",
    r"\bimplementation\s+(?:is\s+)?(?:complete|done|finished)\b",
    r"\bsuccessfully\s+(?:implemented|completed|finished)\b",
    r"\bwork\s+(?:is\s+)?(?:complete|done|finished)\b",
    r"\bchanges?\s+(?:have\s+been\s+)?(?:committed|pushed)\b",
    r"\bpull\s+request\s+(?:created|opened)\b",
    r"\bfeature\s+(?:is\s+)?(?:complete|ready|done)\b",
    r"\bbug\s+(?:fix\s+)?(?:is\s+)?(?:complete|done|deployed)\b",
]

# Patterns that indicate Daem0n was already used appropriately
DAEM0N_OUTCOME_PATTERNS = [
    r"mcp__daem0nmcp__record_outcome",
    r"record_outcome",
    r"recorded?\s+(?:the\s+)?outcome",
    r"outcome\s+(?:has\s+been\s+)?recorded",
]

# Patterns that indicate this is just research/exploration (no outcome needed)
EXPLORATION_PATTERNS = [
    r"\bhere(?:'s|\s+is)\s+(?:the\s+)?(?:information|answer|explanation)\b",
    r"\bi\s+found\b",
    r"\blet\s+me\s+explain\b",
    r"\bthe\s+(?:code|file|function)\s+(?:is|does|works)\b",
    r"\bbased\s+on\s+my\s+(?:research|analysis|exploration)\b",
]


def get_state_file() -> Path:
    """Get the state file path for the current session."""
    safe_session = re.sub(r'[^\w\-]', '_', SESSION_ID or "default")
    return STATE_DIR / f"stop_hook_{safe_session}.json"


def load_state() -> dict:
    """Load the hook state for this session."""
    state_file = get_state_file()
    if state_file.exists():
        try:
            return json.loads(state_file.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {"reminder_count": 0, "last_reminder_turn": -1}


def save_state(state: dict) -> None:
    """Save the hook state for this session."""
    state_file = get_state_file()
    try:
        state_file.write_text(json.dumps(state))
    except IOError:
        pass


def clear_state() -> None:
    """Clear the state file (for new sessions)."""
    state_file = get_state_file()
    try:
        state_file.unlink(missing_ok=True)
    except IOError:
        pass


def read_transcript() -> list[dict]:
    """Read and parse the conversation transcript."""
    if not TRANSCRIPT_PATH or not Path(TRANSCRIPT_PATH).exists():
        return []

    messages = []
    try:
        with open(TRANSCRIPT_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        messages.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except IOError:
        pass

    return messages


def get_recent_assistant_content(messages: list[dict], lookback: int = 5) -> str:
    """Extract recent assistant message content."""
    content_parts = []

    for msg in reversed(messages[-lookback:]):
        if msg.get("role") == "assistant":
            # Handle different content formats
            content = msg.get("content", "")
            if isinstance(content, str):
                content_parts.append(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            content_parts.append(part.get("text", ""))
                        elif part.get("type") == "tool_use":
                            content_parts.append(part.get("name", ""))
                    elif isinstance(part, str):
                        content_parts.append(part)

    return " ".join(content_parts)


def get_recent_tool_calls(messages: list[dict], lookback: int = 10) -> list[str]:
    """Extract recent tool call names from transcript."""
    tool_calls = []

    for msg in messages[-lookback:]:
        content = msg.get("content", [])
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "tool_use":
                    tool_calls.append(part.get("name", ""))

    return tool_calls


def has_completion_signal(text: str) -> bool:
    """Check if text contains completion signals."""
    text_lower = text.lower()
    for pattern in COMPLETION_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False


def has_daem0n_outcome(text: str, tool_calls: list[str]) -> bool:
    """Check if Daem0n record_outcome was called recently."""
    text_lower = text.lower()

    # Check tool calls
    for tool in tool_calls:
        if "record_outcome" in tool.lower():
            return True

    # Check text mentions
    for pattern in DAEM0N_OUTCOME_PATTERNS:
        if re.search(pattern, text_lower):
            return True

    return False


def is_exploration_only(text: str) -> bool:
    """Check if this appears to be exploration/research without implementation."""
    text_lower = text.lower()
    for pattern in EXPLORATION_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False


def has_pending_decisions(text: str, tool_calls: list[str]) -> bool:
    """Check if there were decisions/remembers that need outcomes."""
    text_lower = text.lower()

    # Check for remember calls
    for tool in tool_calls:
        if "remember" in tool.lower() and "record_outcome" not in tool.lower():
            return True

    # Check for decision mentions
    if re.search(r"mcp__daem0nmcp__remember", text_lower):
        return True

    return False


def main():
    """Main hook logic."""
    # Load state
    state = load_state()

    # Read transcript
    messages = read_transcript()
    if not messages:
        # No transcript, nothing to do
        sys.exit(0)

    current_turn = len(messages)

    # Prevent infinite loops - don't remind twice in a row
    if state.get("last_reminder_turn", -1) >= current_turn - 2:
        # Already reminded recently, don't spam
        if state.get("reminder_count", 0) >= 2:
            # Too many reminders, give up for this session
            sys.exit(0)

    # Get recent content and tool calls
    recent_content = get_recent_assistant_content(messages)
    recent_tools = get_recent_tool_calls(messages)

    # Skip if this is just exploration/research
    if is_exploration_only(recent_content) and not has_pending_decisions(recent_content, recent_tools):
        sys.exit(0)

    # Check for completion signals
    if not has_completion_signal(recent_content):
        # No completion detected, nothing to do
        sys.exit(0)

    # Check if Daem0n outcome was already recorded
    if has_daem0n_outcome(recent_content, recent_tools):
        # Already recorded, clear state and exit
        clear_state()
        sys.exit(0)

    # Completion detected but no outcome recorded - send reminder
    state["reminder_count"] = state.get("reminder_count", 0) + 1
    state["last_reminder_turn"] = current_turn
    save_state(state)

    # Build reminder message
    reminder = {
        "decision": "block",
        "reason": (
            "[Daem0n whispers] Task completion detected. "
            "Remember to record the outcome of your work:\n\n"
            "```\n"
            "mcp__daem0nmcp__record_outcome(\n"
            "    memory_id=<id from remember>,\n"
            "    outcome=\"What actually happened\",\n"
            "    worked=True  # or False if it failed\n"
            ")\n"
            "```\n\n"
            "If you haven't recorded any decisions yet, you can skip this. "
            "Otherwise, recording outcomes helps the Daem0n learn from your work."
        )
    }

    # Output JSON to trigger the reminder
    print(json.dumps(reminder))
    sys.exit(0)


if __name__ == "__main__":
    main()
