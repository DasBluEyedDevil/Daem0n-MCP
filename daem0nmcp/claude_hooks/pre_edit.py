"""
Claude Code PreToolUse hook for Edit/Write/NotebookEdit - preflight enforcement.

Checks that a preflight context_check was performed recently. If not,
blocks the edit (exit 2) with a message telling Claude to call consult().
When allowed, recalls file memories and outputs them as context.
"""

import sys
from pathlib import Path

from ._client import (
    get_project_path,
    get_file_path_from_input,
    get_managers,
    run_async,
    block,
    succeed,
)


def _format_file_context(file_memories: dict, rule_result: dict) -> str:
    """Format recalled memories and rules as human-readable context."""
    parts: list[str] = []

    warnings = file_memories.get("warnings", [])
    failed = [w for w in warnings if w.get("type") == "FAILED_APPROACH"]
    general = [w for w in warnings if w.get("type") == "WARNING"]
    rule_warnings = [w for w in warnings if w.get("type") == "RULE_WARNING"]

    if failed:
        parts.append("**Failed approaches (avoid repeating):**")
        for f in failed[:3]:
            content = f.get("content", "")[:150]
            parts.append(f"  - {content}")
            outcome = f.get("outcome")
            if outcome:
                parts.append(f"    Outcome: {outcome[:100]}")

    if general:
        parts.append("**Warnings for this file:**")
        for w in general[:3]:
            parts.append(f"  - {w.get('content', '')[:150]}")

    if rule_warnings:
        parts.append("**Rule warnings:**")
        for w in rule_warnings[:2]:
            parts.append(f"  - {w.get('content', '')[:150]}")

    must_do = file_memories.get("must_do", [])
    if must_do:
        parts.append("**Must do:**")
        for item in must_do[:3]:
            parts.append(f"  - {item[:100]}")

    must_not = file_memories.get("must_not", [])
    if must_not:
        parts.append("**Must NOT do:**")
        for item in must_not[:3]:
            parts.append(f"  - {item[:100]}")

    # Add rule guidance if any
    guidance = rule_result.get("guidance")
    if guidance:
        for md in guidance.get("must_do", []):
            if md not in must_do:
                if "**Must do:**" not in "\n".join(parts):
                    parts.append("**Must do:**")
                parts.append(f"  - {md[:100]}")
        for mn in guidance.get("must_not", []):
            if mn not in must_not:
                if "**Must NOT do:**" not in "\n".join(parts):
                    parts.append("**Must NOT do:**")
                parts.append(f"  - {mn[:100]}")
        for w in guidance.get("warnings", []):
            parts.append(f"  [rule] {w[:150]}")

    return "\n".join(parts)


def main() -> None:
    project_path = get_project_path()
    if project_path is None:
        sys.exit(0)

    file_path = get_file_path_from_input()
    if not file_path:
        sys.exit(0)

    db, memory, rules = get_managers(project_path)

    async def _check():
        await db.init_db()

        # Check preflight token
        from ..enforcement import SessionManager

        session_mgr = SessionManager(db)
        has_token = await session_mgr.has_recent_context_check(project_path)

        if not has_token:
            return False, "", {}

        # Recall file memories
        from ..cli import check_file

        file_result = await check_file(file_path, db, memory, rules)

        # Check rules for this file
        filename = Path(file_path).name
        rule_result = await rules.check_rules(f"editing {filename}")

        return True, file_result, rule_result

    allowed, file_result, rule_result = run_async(_check())

    if not allowed:
        block(
            "[Daem0n blocks] No preflight token. "
            "You must call consult(action='preflight', description='<what you plan to do>') "
            "before editing files. This ensures awareness of existing memories, warnings, and rules."
        )

    # Output file context if any
    context = _format_file_context(file_result, rule_result)
    filename = Path(file_path).name
    if context:
        succeed(f"[Daem0n recalls for {filename}]\n{context}")
    else:
        sys.exit(0)


if __name__ == "__main__":
    from daem0nmcp.claude_hooks._client import run_hook_safely

    run_hook_safely(main, timeout_seconds=10)
