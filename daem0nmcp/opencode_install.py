"""Installer for OpenCode integration.

Creates .opencode/ directory structure and ensures opencode.json exists
at project root for MCP server connectivity.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any


OPENCODE_JSON_TEMPLATE: dict[str, Any] = {
    "$schema": "https://opencode.ai/config.json",
    "mcp": {
        "daem0nmcp": {
            "type": "local",
            "command": ["python", "-m", "daem0nmcp"],
            "enabled": True,
            "environment": {
                "PYTHONUNBUFFERED": "1"
            }
        }
    }
}

# Subdirectories to scaffold inside .opencode/
_OPENCODE_SUBDIRS = ["commands", "plugins", "agents"]


def detect_clients(project_path: Path) -> dict[str, Any]:
    """Detect installed AI coding clients and their configuration status.

    Checks for Claude Code and OpenCode binaries and configuration files.
    Does NOT gate installation on binary detection -- reports status only.

    Returns nested dict with ``binary_found``, individual config checks,
    and a summary ``configured`` boolean for each client.
    """
    claude_binary = shutil.which("claude") is not None
    claude_mcp_json = (project_path / ".mcp.json").exists()
    claude_dir = (project_path / ".claude").is_dir()

    opencode_binary = shutil.which("opencode") is not None
    opencode_json = (project_path / "opencode.json").exists()
    opencode_dir = (project_path / ".opencode").is_dir()
    agents_md = (project_path / "AGENTS.md").exists()

    return {
        "claude_code": {
            "binary_found": claude_binary,
            "mcp_json": claude_mcp_json,
            "claude_dir": claude_dir,
            "configured": claude_mcp_json or claude_dir,
        },
        "opencode": {
            "binary_found": opencode_binary,
            "opencode_json": opencode_json,
            "opencode_dir": opencode_dir,
            "agents_md": agents_md,
            "configured": opencode_json or opencode_dir,
        },
    }


def _ensure_dir(path: Path, dry_run: bool) -> str:
    """Ensure a directory exists. Returns status string."""
    if path.is_dir():
        return "[exists]"
    if not dry_run:
        path.mkdir(parents=True, exist_ok=True)
    return "[create]"


def _ensure_file(path: Path, content: str, dry_run: bool, force: bool) -> str:
    """Ensure a file exists with given content. Returns status string."""
    if path.exists():
        if force:
            if not dry_run:
                path.write_text(content, encoding="utf-8")
            return "[overwrite]"
        return "[exists]"
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return "[create]"


def install_opencode(
    project_path: str,
    dry_run: bool = False,
    force: bool = False,
) -> tuple[bool, str]:
    """Install OpenCode integration for a project.

    Creates ``.opencode/`` directory structure and ensures ``opencode.json``
    exists at the project root.

    Returns ``(success, message)`` tuple.
    """
    root = Path(project_path).resolve()
    lines: list[str] = []

    if dry_run:
        lines.append("[dry-run] Showing planned changes (no files will be modified)\n")

    # -- Client detection ------------------------------------------------
    clients = detect_clients(root)

    lines.append("Client detection:")
    cc = clients["claude_code"]
    lines.append(f"  Claude Code binary: {'found' if cc['binary_found'] else 'not found'}")
    lines.append(f"  .mcp.json: {'found' if cc['mcp_json'] else 'not found'}")
    lines.append(f"  .claude/: {'found' if cc['claude_dir'] else 'not found'}")

    oc = clients["opencode"]
    lines.append(f"  OpenCode binary: {'found' if oc['binary_found'] else 'not found'}")
    lines.append(f"  opencode.json: {'found' if oc['opencode_json'] else 'not found'}")
    lines.append(f"  .opencode/: {'found' if oc['opencode_dir'] else 'not found'}")
    lines.append(f"  AGENTS.md: {'found' if oc['agents_md'] else 'not found'}")
    lines.append("")

    # -- Scaffold .opencode/ directories ---------------------------------
    try:
        lines.append("Directory scaffolding:")
        opencode_root = root / ".opencode"
        status = _ensure_dir(opencode_root, dry_run)
        lines.append(f"  {status} .opencode/")

        for subdir in _OPENCODE_SUBDIRS:
            status = _ensure_dir(opencode_root / subdir, dry_run)
            lines.append(f"  {status} .opencode/{subdir}/")
        lines.append("")

        # -- Ensure opencode.json at project root ------------------------
        lines.append("Configuration:")
        json_content = json.dumps(OPENCODE_JSON_TEMPLATE, indent=2) + "\n"
        json_path = root / "opencode.json"
        status = _ensure_file(json_path, json_content, dry_run, force)
        lines.append(f"  {status} opencode.json")

        # -- AGENTS.md status (do NOT create) ----------------------------
        if oc["agents_md"]:
            lines.append(f"  [exists] AGENTS.md")
        else:
            lines.append(f"  [skip]   AGENTS.md (create via Phase 18 or manually)")
        lines.append("")

    except OSError as exc:
        return False, f"Installation failed: {exc}"

    # -- Claude Code preservation report ---------------------------------
    if cc["configured"]:
        lines.append("Claude Code preservation:")
        if cc["mcp_json"]:
            lines.append("  .mcp.json -- preserved (not modified)")
        if cc["claude_dir"]:
            lines.append("  .claude/ -- preserved (not modified)")
        lines.append("")

    # -- Summary ---------------------------------------------------------
    if dry_run:
        lines.append("No changes were made. Remove --dry-run to apply.")
    else:
        lines.append("OpenCode integration installed successfully.")
        lines.append("Next: Launch OpenCode in this project directory.")

    return True, "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Install OpenCode integration for Daem0n-MCP"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be created without making changes"
    )
    parser.add_argument(
        "--force", "-f", action="store_true",
        help="Overwrite existing configuration files"
    )
    parser.add_argument(
        "--project-path", default=".",
        help="Project root path (default: current directory)"
    )
    args = parser.parse_args()

    ok, msg = install_opencode(
        args.project_path,
        dry_run=args.dry_run,
        force=args.force,
    )
    print(msg)
    sys.exit(0 if ok else 1)
