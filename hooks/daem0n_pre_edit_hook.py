#!/usr/bin/env python3
"""Fail-closed Claude PreToolUse guidance for v7-scoped edits."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path


def _configured_root() -> Path | None:
    raw_root = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not raw_root:
        return None
    root = Path(raw_root).resolve(strict=False)
    return root if (root / ".daem0nmcp").is_dir() else None


def _tool_path() -> str | None:
    try:
        data = json.loads(os.environ.get("TOOL_INPUT", "{}"))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    value = data.get("file_path") or data.get("notebook_path")
    return value if isinstance(value, str) and value else None


def _relative_path(root: Path, value: str) -> str | None:
    try:
        return Path(value).resolve(strict=False).relative_to(root).as_posix()
    except (OSError, RuntimeError, ValueError):
        return None


def _workspace_id(root: Path) -> str:
    key = os.path.normcase(str(root))
    return "ws_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def _guidance(root: Path, value: str) -> str:
    workspace_id = _workspace_id(root)
    relative_path = _relative_path(root, value)
    path_label = relative_path or "<workspace-relative-file>"
    digest = hashlib.sha256(
        f"{workspace_id}\0{path_label}".encode("utf-8")
    ).hexdigest()[:24]
    target_arguments = {
        "record_type": "decision",
        "content": f"Describe the planned change to {path_label}",
        "idempotency_key": f"hook-preedit-{digest}",
    }
    if relative_path is not None:
        target_arguments["relative_file_path"] = relative_path
    encoded = json.dumps(target_arguments, ensure_ascii=True, separators=(",", ":"))
    return (
        "[Daem0n blocks] This standalone hook cannot access the authenticated "
        "v7 invocation, so it fails closed. Ask the MCP host to call "
        f'mcp__daem0nmcp__memory_recall(workspace_id="{workspace_id}", '
        f'query="planned edit to {path_label}", limit=10). If the plan is '
        "durable, call "
        f'mcp__daem0nmcp__memory_preflight(workspace_id="{workspace_id}", '
        f'target_tool="memory_store", target_arguments={encoded}, '
        f'description="Review the planned edit to {path_label}"). Review the '
        "returned warnings and use its preflight_token only with that exact "
        "memory_store request."
    )


def main() -> int:
    root = _configured_root()
    if root is None:
        return 0
    value = _tool_path()
    if value is None:
        print(
            "[Daem0n blocks] Unable to identify the edit target; this hook "
            "fails closed. Call memory_recall and memory_preflight through the "
            "authenticated MCP host.",
            file=sys.stderr,
        )
        return 2
    try:
        message = _guidance(root, value)
    except Exception:
        message = (
            "[Daem0n blocks] Unable to construct scoped v7 guidance; this "
            "hook fails closed. Call session_brief, memory_recall, and "
            "memory_preflight through the authenticated MCP host."
        )
    print(message, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
