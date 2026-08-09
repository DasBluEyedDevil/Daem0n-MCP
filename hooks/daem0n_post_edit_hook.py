#!/usr/bin/env python3
"""Read-only Claude PostToolUse guidance for significant v7 changes."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path


SIGNIFICANT_EXTENSIONS = frozenset(
    {
        ".py",
        ".ts",
        ".js",
        ".go",
        ".rs",
        ".java",
        ".yaml",
        ".yml",
        ".json",
        ".toml",
        ".sql",
    }
)
SIGNIFICANT_TERMS = (
    "async def ",
    "class ",
    "auth",
    "config",
    "credential",
    "endpoint",
    "migration",
    "schema",
    "secret",
    "token",
)


def _configured_root() -> Path | None:
    raw_root = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not raw_root:
        return None
    root = Path(raw_root).resolve(strict=False)
    return root if (root / ".daem0nmcp").is_dir() else None


def _tool_input() -> dict[str, object]:
    try:
        value = json.loads(os.environ.get("TOOL_INPUT", "{}"))
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _relative_path(root: Path, value: str) -> str | None:
    try:
        return Path(value).resolve(strict=False).relative_to(root).as_posix()
    except (OSError, RuntimeError, ValueError):
        return None


def _is_significant(value: str, changed: str) -> bool:
    if Path(value).suffix.casefold() not in SIGNIFICANT_EXTENSIONS:
        return False
    lowered = changed.casefold()
    return len(changed) > 500 or any(term in lowered for term in SIGNIFICANT_TERMS)


def _suggestion(root: Path, value: str, changed: str) -> str:
    key = os.path.normcase(str(root))
    workspace_id = "ws_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    relative_path = _relative_path(root, value)
    path_label = relative_path or Path(value).name or "changed file"
    digest = hashlib.sha256(
        f"{workspace_id}\0{path_label}\0{changed}".encode("utf-8")
    ).hexdigest()[:24]
    target_arguments: dict[str, object] = {
        "record_type": "decision",
        "content": f"Summarize the significant change to {path_label}",
        "rationale": "Preserve the reason and constraints for future sessions",
        "idempotency_key": f"hook-postedit-{digest}",
    }
    if relative_path is not None:
        target_arguments["relative_file_path"] = relative_path
    encoded = json.dumps(target_arguments, ensure_ascii=True, separators=(",", ":"))
    store_fields = [
        f'workspace_id="{workspace_id}"',
        'record_type="decision"',
        f'content={json.dumps(target_arguments["content"])}',
        f'rationale={json.dumps(target_arguments["rationale"])}',
    ]
    if relative_path is not None:
        store_fields.append(f"relative_file_path={json.dumps(relative_path)}")
    store_fields.extend(
        (
            f'idempotency_key="{target_arguments["idempotency_key"]}"',
            'preflight_token="<token-from-memory_preflight>"',
        )
    )
    return (
        "[Daem0n suggests] This hook did not write memory. First call "
        f'mcp__daem0nmcp__memory_preflight(workspace_id="{workspace_id}", '
        f'target_tool="memory_store", target_arguments={encoded}, '
        f'description="Record the significant change to {path_label}"). Then '
        "call mcp__daem0nmcp__memory_store(" + ", ".join(store_fields) + ")."
    )


def main() -> None:
    root = _configured_root()
    if root is None:
        return
    data = _tool_input()
    value = data.get("file_path")
    if not isinstance(value, str) or not value:
        return
    changed = " ".join(
        item
        for item in (
            data.get("old_string"),
            data.get("new_string"),
            data.get("content"),
        )
        if isinstance(item, str)
    )
    if _is_significant(value, changed):
        print(_suggestion(root, value, changed))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(
            "[Daem0n v7 warning] No memory was written. Call memory_preflight "
            "before any memory_store retry, and use system_health for diagnostics."
        )
    sys.exit(0)
