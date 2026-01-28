"""
Text Fallback Formatting for Non-MCP-Apps Hosts

Provides human-readable text formatting for tool results when the
host doesn't support MCP Apps visual rendering.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime


def format_with_ui_hint(data: Dict[str, Any], ui_resource: str, text: str) -> Dict[str, Any]:
    """
    Wrap tool result with UI hint and text fallback.

    This is the standard pattern for tools that have visual UIs:
    - MCP Apps hosts read ui_resource and fetch the UI
    - Other hosts use the text field for display
    - All hosts receive the structured data

    Args:
        data: The structured result data
        ui_resource: URI of the UI resource (e.g., "ui://daem0n/search")
        text: Human-readable text fallback

    Returns:
        Dict with data, ui_resource hint, and text fallback
    """
    return {
        **data,
        "ui_resource": ui_resource,
        "text": text,
    }


def format_search_results(
    query: str,
    results: List[Dict[str, Any]],
    total_count: Optional[int] = None
) -> str:
    """
    Format search/recall results as readable text.

    Args:
        query: The search query
        results: List of result dicts with id, category, content, score
        total_count: Total matching results (if paginated)

    Returns:
        Formatted text string
    """
    if not results:
        return f"No results found for: {query}"

    lines = [
        f"Search Results for: {query}",
        f"Found {total_count or len(results)} result(s)",
        "-" * 40,
    ]

    for i, result in enumerate(results, 1):
        category = result.get("category", "unknown")
        score = result.get("score", 0)
        content = result.get("content", "")

        # Truncate long content
        if len(content) > 200:
            content = content[:197] + "..."

        lines.append(f"\n[{i}] {category.upper()} (score: {score:.2f})")
        lines.append(content)

    return "\n".join(lines)


def format_briefing(
    project: str,
    stats: Dict[str, Any],
    warnings: List[Dict[str, Any]],
    recent_decisions: List[Dict[str, Any]],
    focus_areas: List[str],
) -> str:
    """
    Format briefing as readable text.

    Args:
        project: Project name/path
        stats: Statistics dict with memory counts, outcome rates
        warnings: List of active warnings
        recent_decisions: List of recent decisions with outcomes
        focus_areas: List of focus area strings

    Returns:
        Formatted briefing text
    """
    lines = [
        f"=== BRIEFING: {project} ===",
        "",
        "STATISTICS",
        "-" * 20,
    ]

    # Format stats
    for key, value in stats.items():
        lines.append(f"  {key}: {value}")

    if warnings:
        lines.extend([
            "",
            "ACTIVE WARNINGS",
            "-" * 20,
        ])
        for w in warnings:
            lines.append(f"  ! {w.get('content', 'Unknown warning')}")

    if recent_decisions:
        lines.extend([
            "",
            "RECENT DECISIONS",
            "-" * 20,
        ])
        for d in recent_decisions[:5]:
            outcome = d.get("outcome", "pending")
            outcome_marker = {"success": "+", "failure": "-", "pending": "?"}
            marker = outcome_marker.get(outcome, "?")
            lines.append(f"  [{marker}] {d.get('content', '')[:60]}")

    if focus_areas:
        lines.extend([
            "",
            "FOCUS AREAS",
            "-" * 20,
        ])
        for area in focus_areas:
            lines.append(f"  * {area}")

    lines.append("")
    lines.append("=" * 40)

    return "\n".join(lines)


def format_covenant_status(
    phase: str,
    is_briefed: bool,
    context_checks: int,
    preflight_valid: bool,
    preflight_expires: Optional[datetime] = None,
) -> str:
    """
    Format covenant status as readable text.

    Args:
        phase: Current covenant phase
        is_briefed: Whether briefing has been received
        context_checks: Number of context checks performed
        preflight_valid: Whether preflight token is valid
        preflight_expires: When preflight expires (if valid)

    Returns:
        Formatted status text
    """
    lines = [
        "COVENANT STATUS",
        "-" * 20,
        f"Phase: {phase}",
        f"Briefed: {'Yes' if is_briefed else 'No'}",
        f"Context Checks: {context_checks}",
        f"Preflight: {'Valid' if preflight_valid else 'Invalid/Expired'}",
    ]

    if preflight_valid and preflight_expires:
        lines.append(f"Expires: {preflight_expires.isoformat()}")

    return "\n".join(lines)


def format_covenant_status_text(data: Dict[str, Any]) -> str:
    """
    Format covenant status as readable text for non-MCP-Apps hosts.

    Args:
        data: get_covenant_status output

    Returns:
        Formatted text string suitable for terminal/text display
    """
    lines = []

    phase_label = data.get("phase_label", "UNKNOWN")
    phase_desc = data.get("phase_description", "")
    is_briefed = data.get("is_briefed", False)
    context_checks = data.get("context_check_count", 0)
    preflight = data.get("preflight", {})
    message = data.get("message", "")

    lines.append("=== COVENANT STATUS ===")
    lines.append("")
    lines.append(f"Phase: {phase_label}")
    lines.append(f"  {phase_desc}")
    lines.append("")
    lines.append(f"Briefed: {'Yes' if is_briefed else 'No'}")
    lines.append(f"Context Checks: {context_checks}")
    lines.append("")

    # Token status
    token_status = preflight.get("status", "none").upper()
    lines.append(f"Preflight Token: {token_status}")

    if token_status == "VALID":
        remaining = preflight.get("remaining_seconds", 0)
        if remaining:
            minutes = remaining // 60
            seconds = remaining % 60
            lines.append(f"  Expires in: {minutes}:{seconds:02d}")
        expires_at = preflight.get("expires_at")
        if expires_at:
            lines.append(f"  Expires at: {expires_at}")

    lines.append("")
    lines.append(f"Message: {message}")
    lines.append("")
    lines.append("=" * 24)

    return "\n".join(lines)


def format_community_cluster(
    community_id: int,
    members: List[str],
    summary: str,
    sub_communities: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Format community cluster as readable text.

    Args:
        community_id: Leiden community ID
        members: List of member memory IDs
        summary: Community summary text
        sub_communities: List of sub-community dicts

    Returns:
        Formatted cluster text
    """
    lines = [
        f"COMMUNITY #{community_id}",
        "-" * 20,
        f"Members: {len(members)}",
        "",
        "Summary:",
        summary,
    ]

    if sub_communities:
        lines.extend([
            "",
            "Sub-communities:",
        ])
        for sub in sub_communities:
            sub_id = sub.get("id", "?")
            sub_size = len(sub.get("members", []))
            lines.append(f"  - #{sub_id}: {sub_size} members")

    return "\n".join(lines)


def format_graph_path(
    start: str,
    end: str,
    path: List[Dict[str, Any]],
    hops: int,
) -> str:
    """
    Format graph traversal path as readable text.

    Args:
        start: Starting node ID
        end: Ending node ID
        path: List of path step dicts with node, edge info
        hops: Number of hops in path

    Returns:
        Formatted path text
    """
    if not path:
        return f"No path found from {start} to {end}"

    lines = [
        f"PATH: {start} -> {end}",
        f"Hops: {hops}",
        "-" * 20,
    ]

    for i, step in enumerate(path):
        node = step.get("node", {})
        edge = step.get("edge", {})
        node_label = node.get("label", node.get("id", "?"))
        edge_type = edge.get("type", "relates_to")

        if i == 0:
            lines.append(f"  [{node_label}]")
        else:
            lines.append(f"    --{edge_type}-->")
            lines.append(f"  [{node_label}]")

    return "\n".join(lines)


def format_briefing_text(data: Dict[str, Any]) -> str:
    """
    Format briefing data as readable text for non-MCP-Apps hosts.

    Args:
        data: get_briefing output

    Returns:
        Formatted text string suitable for terminal/text display
    """
    lines = []

    status = data.get("status", "unknown")
    lines.append(f"=== Session Briefing [{status.upper()}] ===")
    lines.append("")

    # Statistics
    stats = data.get("statistics", {})
    if stats:
        lines.append("## Statistics")
        lines.append(f"  Total Memories: {stats.get('total_memories', 0)}")
        by_cat = stats.get("by_category", {})
        lines.append(f"  Decisions: {by_cat.get('decision', 0)}")
        lines.append(f"  Warnings: {by_cat.get('warning', 0)}")
        lines.append(f"  Patterns: {by_cat.get('pattern', 0)}")
        lines.append(f"  Learnings: {by_cat.get('learning', 0)}")
        outcome_rates = stats.get("outcome_rates", {})
        success_rate = outcome_rates.get("success_rate", 0)
        lines.append(f"  Success Rate: {success_rate:.0%}")
        lines.append("")

    # Message
    message = data.get("message")
    if message:
        lines.append("## Briefing Message")
        lines.append(message)
        lines.append("")

    # Recent Decisions
    decisions = data.get("recent_decisions", [])
    if decisions:
        lines.append(f"## Recent Decisions ({len(decisions)})")
        for d in decisions[:5]:  # Limit for text output
            worked = d.get("worked")
            status_str = "[SUCCESS]" if worked is True else "[FAILED]" if worked is False else "[PENDING]"
            content = d.get("content", "")[:100]  # Truncate
            lines.append(f"  {status_str} {content}")
        if len(decisions) > 5:
            lines.append(f"  ... and {len(decisions) - 5} more")
        lines.append("")

    # Active Warnings
    warnings = data.get("active_warnings", [])
    if warnings:
        lines.append(f"## Active Warnings ({len(warnings)})")
        for w in warnings[:5]:
            severity = w.get("severity", "medium").upper()
            content = w.get("content", "")[:100]
            lines.append(f"  [{severity}] {content}")
        if len(warnings) > 5:
            lines.append(f"  ... and {len(warnings) - 5} more")
        lines.append("")

    # Git Changes
    git_changes = data.get("git_changes", {})
    if git_changes:
        total = git_changes.get("total", 0)
        if total > 0:
            lines.append(f"## Git Changes ({total} files)")
            files = git_changes.get("files", [])[:10]
            for f in files:
                status_char = f.get("status", "M")
                path = f.get("path", "")
                lines.append(f"  {status_char} {path}")
            if total > 10:
                lines.append(f"  ... and {total - 10} more files")
            lines.append("")

    # Focus Areas
    focus = data.get("focus_areas")
    if focus:
        lines.append(f"## Focus Areas ({len(focus)})")
        for area in focus:
            topic = area.get("topic", "")
            lines.append(f"  - {topic}")
        lines.append("")

    return "\n".join(lines)
