"""
Claude Code SessionStart hook - auto-communion with Daem0n.

Runs at session start to output a briefing summary and mark the
session as briefed. Never blocks.
"""

import sys

from ._client import get_project_path, get_managers, run_async, succeed


async def async_main(project_path: str) -> str:
    """
    Core async logic.  Returns the briefing text (empty string if nothing).

    Separated from ``main()`` so tests can call it inside an existing
    event loop without needing a subprocess.
    """
    db, memory, _rules = get_managers(project_path)
    await db.init_db()

    stats = await memory.get_statistics()

    from ..enforcement import SessionManager
    session_mgr = SessionManager(db)
    await session_mgr.mark_briefed(project_path)

    total = stats.get("total_memories", 0)
    by_cat = stats.get("by_category", {})
    outcomes = stats.get("with_outcomes", {})

    cat_parts = []
    for cat in ("decision", "pattern", "warning", "learning"):
        count = by_cat.get(cat, 0)
        if count:
            cat_parts.append(f"{count} {cat}s")

    cat_str = ", ".join(cat_parts) if cat_parts else "empty"
    parts = [f"[Daem0n Briefing] {total} memories ({cat_str})"]

    pending = outcomes.get("pending", 0)
    warnings_count = by_cat.get("warning", 0)
    parts.append(f"Pending outcomes: {pending} | Recent warnings: {warnings_count}")
    parts.append("Commune complete.")

    return "\n".join(parts)


def main() -> None:
    project_path = get_project_path()
    if project_path is None:
        sys.exit(0)

    text = run_async(async_main(project_path))
    succeed(text)


if __name__ == "__main__":
    from daem0nmcp.claude_hooks._client import run_hook_safely

    run_hook_safely(main)
