"""Pure rendering for the retained v7-to-legacy recall envelope.

Every field consumed here was authenticated and loaded by the retrieval
repository in its policy-consistent, bounded SQLite worker transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .types import EvidenceItem, EvidenceRef


_CATEGORY_KEYS = {
    "decision": "decisions",
    "pattern": "patterns",
    "warning": "warnings",
    "learning": "learnings",
}
_MAX_LEGACY_ITEMS = 100


@dataclass(frozen=True, slots=True)
class _SelectedItem:
    item: EvidenceItem
    primary: EvidenceRef
    category_key: str


def _selected_items(
    items: tuple[EvidenceItem, ...],
    per_category_limit: int,
) -> tuple[_SelectedItem, ...]:
    if not isinstance(items, tuple) or not all(
        isinstance(item, EvidenceItem) for item in items
    ):
        raise ValueError("items must contain EvidenceItem values")
    if len(items) > _MAX_LEGACY_ITEMS:
        raise ValueError("items must contain at most 100 values")
    if (
        isinstance(per_category_limit, bool)
        or not isinstance(per_category_limit, int)
        or per_category_limit < 1
        or per_category_limit > _MAX_LEGACY_ITEMS
    ):
        raise ValueError("per_category_limit must be between 1 and 100")
    counts = {category: 0 for category in _CATEGORY_KEYS.values()}
    selected: list[_SelectedItem] = []
    for item in items:
        category_key = _CATEGORY_KEYS.get(item.category, "learnings")
        if counts[category_key] == per_category_limit:
            continue
        counts[category_key] += 1
        selected.append(
            _SelectedItem(
                item=item,
                primary=item.evidence_refs[0],
                category_key=category_key,
            )
        )
    return tuple(selected)


def _render_selection(
    selection: _SelectedItem,
    *,
    condensed: bool,
) -> dict[str, Any]:
    item = selection.item
    content = (
        item.excerpt
        if not condensed or len(item.excerpt) <= 150
        else item.excerpt[:150] + "..."
    )
    rendered: dict[str, Any] = {
        "id": selection.primary.record_id,
        "content": content,
        "rationale": None if condensed else item.rationale,
        # v7 contexts are schemaless and may contain paths, prompts, or secrets.
        # A typed allowlist is required before this legacy field can be exposed.
        "context": None,
        "tags": list(item.tags),
        "relevance": round(item.score, 6),
        "outcome": item.outcome,
        "worked": item.worked,
        "citation": item.citation,
        "status": item.status,
        "channels": sorted(item.channels),
        "evidence_refs": [
            {
                "record_id": ref.record_id,
                "event_id": ref.event_id,
                "content_hash": ref.content_hash,
                "version_id": ref.version_id,
                "relation_path": list(ref.relation_path),
                "provider": ref.provider,
            }
            for ref in item.evidence_refs
        ],
    }
    if item.outcome_failed:
        rendered["_warning"] = (
            f"This approach FAILED: {item.outcome or 'no details recorded'}"
        )
    return rendered


def build_legacy_recall_categories(
    items: tuple[EvidenceItem, ...],
    *,
    per_category_limit: int,
    condensed: bool,
) -> dict[str, list[dict[str, Any]]]:
    """Render only repository-authenticated post-policy evidence."""

    if not isinstance(condensed, bool):
        raise ValueError("condensed must be boolean")
    selections = _selected_items(items, per_category_limit)
    categories: dict[str, list[dict[str, Any]]] = {
        category: [] for category in _CATEGORY_KEYS.values()
    }
    for selection in selections:
        categories[selection.category_key].append(
            _render_selection(selection, condensed=condensed)
        )
    return categories


__all__ = ["build_legacy_recall_categories"]
