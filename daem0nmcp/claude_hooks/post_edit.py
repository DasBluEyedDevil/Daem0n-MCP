"""Claude Code PostToolUse hook for replay-safe v7 memory suggestions.

The hook never writes domain data itself. Significant edits receive exact
``memory_preflight`` and ``memory_store`` calls with an opaque workspace ID and
a deterministic idempotency key.
"""

import hashlib
import json
import sys
from pathlib import Path

from ..workspace import WorkspaceRegistry
from ._client import get_file_path_from_input, get_project_path, get_tool_input, succeed

# Patterns indicating architecturally or operationally significant changes
SIGNIFICANT_PATTERNS = [
    "class ",
    "def __init__",
    "async def ",
    "@dataclass",
    "@mcp.tool",
    "config",
    "settings",
    "environment",
    "auth",
    "password",
    "token",
    "secret",
    "credential",
    "migration",
    "schema",
    "model",
    "table",
    "column",
    "endpoint",
    "route",
    "api",
    "request",
    "response",
]

# File types that are usually significant
SIGNIFICANT_EXTENSIONS = {
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
    ".prisma",
}


def _is_significant(file_path: str, change_content: str) -> bool:
    """Determine if a change is significant enough to suggest remembering."""
    ext = Path(file_path).suffix.lower()
    if ext not in SIGNIFICANT_EXTENSIONS:
        return False

    change_lower = change_content.lower()
    for pattern in SIGNIFICANT_PATTERNS:
        if pattern.lower() in change_lower:
            return True

    return len(change_content) > 500


def _workspace_id(project_path: str) -> str:
    return WorkspaceRegistry(default_root=project_path).default.workspace_id


def _relative_file_path(project_path: str, file_path: str) -> str | None:
    try:
        root = Path(project_path).resolve(strict=True)
        return Path(file_path).resolve(strict=False).relative_to(root).as_posix()
    except (OSError, RuntimeError, ValueError):
        return None


def _v7_suggestion(
    project_path: str,
    file_path: str,
    change_content: str,
) -> str:
    workspace_id = _workspace_id(project_path)
    relative_path = _relative_file_path(project_path, file_path)
    path_label = relative_path or Path(file_path).name
    digest = hashlib.sha256(
        f"{workspace_id}\0{path_label}\0{change_content}".encode("utf-8")
    ).hexdigest()[:24]
    target_arguments = {
        "record_type": "decision",
        "content": f"Summarize the significant change to {path_label}",
        "rationale": "Preserve the reason and constraints for future sessions",
        "idempotency_key": f"hook-postedit-{digest}",
    }
    if relative_path is not None:
        target_arguments["relative_file_path"] = relative_path
    encoded = json.dumps(target_arguments, ensure_ascii=True, separators=(",", ":"))
    return (
        f"[Daem0n suggests] Significant change to {Path(file_path).name}. "
        "First call "
        f'daem0nmcp_memory_preflight(workspace_id="{workspace_id}", '
        f'target_tool="memory_store", target_arguments={encoded}); then call '
        f'daem0nmcp_memory_store(workspace_id="{workspace_id}", '
        f'record_type="decision", content={json.dumps(target_arguments["content"])}, '
        f'rationale={json.dumps(target_arguments["rationale"])}, '
        + (
            f'relative_file_path={json.dumps(relative_path)}, '
            if relative_path is not None
            else ""
        )
        + f'idempotency_key="{target_arguments["idempotency_key"]}", '
        'preflight_token="<token-from-memory_preflight>").'
    )


def main() -> None:
    project_path = get_project_path()
    if project_path is None:
        sys.exit(0)

    file_path = get_file_path_from_input()
    if not file_path:
        sys.exit(0)

    # Extract change content from tool input
    data = get_tool_input()
    old_string = data.get("old_string", "")
    new_string = data.get("new_string", "")
    content = data.get("content", "")  # Write tool uses 'content'
    change_content = f"{old_string} {new_string} {content}"

    if not _is_significant(file_path, change_content):
        sys.exit(0)

    succeed(_v7_suggestion(project_path, file_path, change_content))


if __name__ == "__main__":
    import warnings

    warnings.filterwarnings("ignore")

    from daem0nmcp.claude_hooks._client import run_hook_safely

    run_hook_safely(main)
