#!/usr/bin/env python3
"""Read-only Claude UserPromptSubmit guidance for the v7 ritual."""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path


def _configured_root() -> Path | None:
    raw_root = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not raw_root:
        return None
    root = Path(raw_root).resolve(strict=False)
    return root if (root / ".daem0nmcp").is_dir() else None


def _workspace_id(root: Path) -> str:
    key = os.path.normcase(str(root))
    return "ws_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def main() -> None:
    """Tell the authenticated host which bounded read calls to make."""
    root = _configured_root()
    if root is None:
        return
    workspace_id = _workspace_id(root)
    print(
        "[Daem0n v7 reminder] At session start call "
        f'mcp__daem0nmcp__session_brief(workspace_id="{workspace_id}"). '
        "When history is relevant, call "
        f'mcp__daem0nmcp__memory_recall(workspace_id="{workspace_id}", '
        'query="<task topic>", limit=10). Use only the opaque workspace_id '
        "issued for this workspace."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(
            "[Daem0n v7 reminder] Call session_brief before protected work; "
            "use system_health if the scoped briefing cannot be obtained."
        )
    sys.exit(0)
