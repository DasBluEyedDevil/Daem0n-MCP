"""
Claude Code SessionStart hook - auto-communion with Daem0n.

Runs at session start to output a briefing summary and mark the
session as briefed. Never blocks.
"""

import sys

from ._client import get_project_path, get_managers, run_async, succeed


def main() -> None:
    project_path = get_project_path()
    if project_path is None:
        sys.exit(0)

    db, memory, _rules = get_managers(project_path)

    async def _run():
        await db.init_db()

        # Get statistics
        stats = await memory.get_statistics()

        # Mark session as briefed
        from ..enforcement import SessionManager

        session_mgr = SessionManager(db)
        await session_mgr.mark_briefed(project_path)

        return stats

    stats = run_async(_run())

    total = stats.get("total_memories", 0)
    by_cat = stats.get("by_category", {})
    outcomes = stats.get("with_outcomes", {})

    parts = []
    cat_parts = []
    for cat in ("decision", "pattern", "warning", "learning"):
        count = by_cat.get(cat, 0)
        if count:
            cat_parts.append(f"{count} {cat}s")

    cat_str = ", ".join(cat_parts) if cat_parts else "empty"
    parts.append(f"[Daem0n Briefing] {total} memories ({cat_str})")

    pending = outcomes.get("pending", 0)
    warnings_count = by_cat.get("warning", 0)
    parts.append(f"Pending outcomes: {pending} | Recent warnings: {warnings_count}")
    parts.append("Commune complete.")

    succeed("\n".join(parts))


if __name__ == "__main__":
    from daem0nmcp.claude_hooks._client import run_hook_safely

    run_hook_safely(main)
