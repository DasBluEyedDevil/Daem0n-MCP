"""
Claude Code PreToolUse hook for Bash - rule enforcement.

Checks the command against Daem0n rules. If a ``must_not`` rule matches,
blocks the command (exit 2). Warnings are output as context (exit 0).
"""

import sys

from ._client import (
    get_project_path,
    get_command_from_input,
    get_managers,
    run_async,
    block,
    succeed,
)


def main() -> None:
    project_path = get_project_path()
    if project_path is None:
        sys.exit(0)

    command = get_command_from_input()
    if not command:
        sys.exit(0)

    db, _memory, rules = get_managers(project_path)

    async def _check():
        await db.init_db()
        return await rules.check_rules(f"executing bash: {command[:200]}")

    result = run_async(_check())

    guidance = result.get("guidance")
    if not guidance:
        sys.exit(0)

    must_not = guidance.get("must_not", [])
    warnings = guidance.get("warnings", [])

    if must_not:
        lines = ["[Daem0n blocks] Rule violation for bash command:", "MUST NOT:"]
        for item in must_not:
            lines.append(f"  - {item}")
        block("\n".join(lines))

    if warnings:
        lines = ["[Daem0n warns] Rule guidance for bash command:"]
        for w in warnings:
            lines.append(f"  - {w}")
        succeed("\n".join(lines))

    sys.exit(0)


if __name__ == "__main__":
    from daem0nmcp.claude_hooks._client import run_hook_safely

    run_hook_safely(main, timeout_seconds=10)
