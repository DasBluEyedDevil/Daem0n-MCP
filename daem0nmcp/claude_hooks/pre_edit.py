"""Claude Code PreToolUse hook for v7 preflight guidance.

The hook never opens the legacy mutable manager stack. Because a standalone
hook process cannot validate an MCP capability token against the authenticated
invocation scope, it fails closed and directs the host to ``memory_preflight``.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from ..workspace import WorkspaceRegistry
from ._client import block, get_file_path_from_input, get_project_path, run_async


class PreEditResult:
    """Value object returned by ``async_main``."""

    __slots__ = ("allowed", "message")

    def __init__(self, allowed: bool, message: str):
        self.allowed = allowed
        self.message = message


def _workspace_id(project_path: str) -> str:
    return WorkspaceRegistry(default_root=project_path).default.workspace_id


def _relative_file_path(project_path: str, file_path: str) -> str | None:
    """Return a root-contained v7 relative path, or fail closed."""
    try:
        project_root = Path(project_path).resolve(strict=True)
        resolved_file = Path(file_path).resolve(strict=False)
        return resolved_file.relative_to(project_root).as_posix()
    except (OSError, RuntimeError, ValueError):
        return None


def _preflight_message(project_path: str, file_path: str) -> str:
    workspace_id = _workspace_id(project_path)
    relative_path = _relative_file_path(project_path, file_path)
    path_label = relative_path or "<workspace-relative-path>"
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
    encoded_arguments = json.dumps(
        target_arguments,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return (
        "[Daem0n blocks] This standalone hook cannot validate a scoped v7 "
        "preflight capability, so it fails closed. Ask the MCP host to call "
        f'mcp__daem0nmcp__memory_preflight(workspace_id="{workspace_id}", '
        'target_tool="memory_store", '
        f"target_arguments={encoded_arguments}, "
        f'description="Review the planned edit to {path_label}"). '
        "Use the returned guidance and pass its preflight_token only to the "
        "exact protected call it authorizes."
    )


async def async_main(project_path: str, file_path: str) -> PreEditResult:
    """Return a deterministic fail-closed v7 preflight instruction."""
    return PreEditResult(
        allowed=False,
        message=_preflight_message(project_path, file_path),
    )


def main() -> None:
    project_path = get_project_path()
    if project_path is None:
        sys.exit(0)

    file_path = get_file_path_from_input()
    if not file_path:
        sys.exit(0)

    result = run_async(async_main(project_path, file_path))
    if not result.allowed:
        block(result.message)
    sys.exit(0)


if __name__ == "__main__":
    import warnings

    warnings.filterwarnings("ignore")
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # A pre-edit hook must not silently permit work when its scoped v7
        # guidance cannot be constructed.
        block(
            "[Daem0n blocks] Unable to validate v7 preflight state. "
            "Call memory_preflight for the exact protected operation."
        )
