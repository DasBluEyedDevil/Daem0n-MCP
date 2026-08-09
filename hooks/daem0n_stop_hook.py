#!/usr/bin/env python3
"""Stateless, read-only Claude Stop guidance for the v7 outcome ritual."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path


_MAX_TRANSCRIPT_BYTES = 1_000_000
_MAX_MESSAGES = 50
_COMPLETION = re.compile(
    r"(?i)\b(?:implementation|task|work|feature)\s+(?:is\s+)?"
    r"(?:complete|done|finished)\b|\ball tasks?\s+(?:are\s+)?done\b"
)
_DECISION = re.compile(
    r"(?i)\bi (?:will|chose|decided to)\s+(.{20,240}?)(?:\.|$)"
)
_OUTCOME_TOOL_NAMES = frozenset(
    {
        "memory_record_outcome",
        "daem0nmcp_memory_record_outcome",
        "mcp__daem0nmcp__memory_record_outcome",
    }
)


def _configured_root() -> Path | None:
    raw_root = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not raw_root:
        return None
    root = Path(raw_root).resolve(strict=False)
    return root if (root / ".daem0nmcp").is_dir() else None


def _messages() -> list[dict[str, object]]:
    raw_path = os.environ.get("CLAUDE_TRANSCRIPT_PATH", "")
    if not raw_path:
        return []
    path = Path(raw_path)
    try:
        if not path.is_file() or path.stat().st_size > _MAX_TRANSCRIPT_BYTES:
            return []
        lines = path.read_text(encoding="utf-8").splitlines()[-_MAX_MESSAGES:]
    except OSError:
        return []
    messages: list[dict[str, object]] = []
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            messages.append(value)
    return messages


def _recent_content(messages: list[dict[str, object]]) -> tuple[str, set[str]]:
    text_parts: list[str] = []
    tools: set[str] = set()
    for message in messages:
        if message.get("role") != "assistant":
            continue
        content = message.get("content")
        if isinstance(content, str):
            text_parts.append(content)
        elif isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "text" and isinstance(part.get("text"), str):
                    text_parts.append(str(part["text"]))
                if part.get("type") == "tool_use" and isinstance(part.get("name"), str):
                    tools.add(str(part["name"]).casefold())
    return " ".join(text_parts)[-20_000:], tools


def _reason(root: Path, content: str) -> str:
    key = os.path.normcase(str(root))
    workspace_id = "ws_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    match = _DECISION.search(content)
    decision = (
        re.sub(r"\s+", " ", match.group(1)).strip()
        if match is not None
        else "Summarize the durable decision from the completed task"
    )
    digest = hashlib.sha256(
        f"{workspace_id}\0{decision}".encode("utf-8")
    ).hexdigest()[:24]
    store_key = f"hook-stop-{digest}"
    outcome_key = f"hook-outcome-{digest}"
    target_arguments = {
        "record_type": "decision",
        "content": decision,
        "rationale": "Preserve the verified decision from the completed task",
        "idempotency_key": store_key,
    }
    encoded = json.dumps(target_arguments, ensure_ascii=True, separators=(",", ":"))
    return (
        "[Daem0n blocks] Completion was detected and this hook did not mutate "
        "memory. Review and call "
        f'mcp__daem0nmcp__memory_preflight(workspace_id="{workspace_id}", '
        f'target_tool="memory_store", target_arguments={encoded}, '
        'description="Record the completed task decision"); then call '
        f'mcp__daem0nmcp__memory_store(workspace_id="{workspace_id}", '
        f'record_type="decision", content={json.dumps(decision)}, '
        'rationale="Preserve the verified decision from the completed task", '
        f'idempotency_key="{store_key}", '
        'preflight_token="<token-from-memory_preflight>"). Once verified, call '
        f'mcp__daem0nmcp__memory_record_outcome(workspace_id="{workspace_id}", '
        'record_id="<mem_id>", outcome_text="<verified result>", worked=true, '
        f'idempotency_key="{outcome_key}").'
    )


def main() -> None:
    root = _configured_root()
    if root is None:
        return
    content, tools = _recent_content(_messages())
    if not content or not _COMPLETION.search(content):
        return
    if tools.intersection(_OUTCOME_TOOL_NAMES):
        return
    print(json.dumps({"decision": "block", "reason": _reason(root, content)}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(
            json.dumps(
                {
                    "decision": "block",
                    "reason": (
                        "[Daem0n blocks] Unable to verify v7 outcome state. "
                        "Call session_brief and system_health, then use "
                        "memory_preflight, memory_store, and "
                        "memory_record_outcome through the authenticated host."
                    ),
                }
            )
        )
    sys.exit(0)
