"""
UI Resource Registration for MCP Apps

Registers HTML UI resources with FastMCP using the ui:// URI scheme
and text/html;profile=mcp-app MIME type.

This module provides:
- Template loading from templates/ directory
- Asset injection (CSS and JavaScript)
- Resource registration via register_ui_resources(mcp)

Resource registrations:
- ui://daem0n/test - Test UI for infrastructure validation (06-03)
- ui://daem0n/search - Search results UI (Phase 7)
- ui://daem0n/briefing - Briefing dashboard (Phase 8)
- ui://daem0n/covenant - Covenant status dashboard (Phase 9)
- ui://daem0n/community - Community cluster map (Phase 10)
- ui://daem0n/graph - Memory graph viewer (Phase 11)
"""
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp import FastMCP

# MIME type for MCP Apps (SEP-1865)
# Signals to MCP hosts that this resource should be rendered as HTML UI
MCP_APPS_MIME = "text/html;profile=mcp-app"

# Directory paths for template and static assets
_UI_DIR = Path(__file__).parent
TEMPLATES_DIR = _UI_DIR / "templates"
STATIC_DIR = _UI_DIR / "static"
BUILD_DIR = _UI_DIR / "build"


def _load_template(name: str) -> str:
    """Load an HTML template from the templates directory."""
    template_path = TEMPLATES_DIR / name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {name}")
    return template_path.read_text(encoding="utf-8")


def _load_static(name: str) -> str:
    """Load a static asset from the static directory."""
    static_path = STATIC_DIR / name
    if not static_path.exists():
        return ""  # Return empty if asset doesn't exist yet
    return static_path.read_text(encoding="utf-8")


def _inject_assets(html: str, include_d3: bool = False) -> str:
    """
    Inject CSS and JavaScript assets into HTML template.

    Replaces:
    - {{CSS}} with daemon.css contents
    - {{SCRIPT}} with D3 bundle (if include_d3=True) + custom script
    """
    css = _load_static("daemon.css")
    html = html.replace("{{CSS}}", css)

    if include_d3:
        d3_bundle = _load_static("d3.bundle.js")
        html = html.replace("{{SCRIPT}}", d3_bundle)
    else:
        html = html.replace("{{SCRIPT}}", "// No D3 required for this template")

    return html


def _highlight_keywords(text: str, query: str) -> str:
    """
    Wrap query keywords in <mark> tags for highlighting.

    Args:
        text: The text content to highlight within
        query: Space-separated query words

    Returns:
        Text with matching keywords wrapped in <mark> tags
    """
    if not query or not text:
        return text

    words = query.split()
    result = text
    for word in words:
        if len(word) > 2:  # Skip short words
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            result = pattern.sub(f"<mark>{word}</mark>", result)
    return result


def _format_date(date_str: str) -> str:
    """Format an ISO date string for display."""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, AttributeError):
        return str(date_str) if date_str else ""


def _build_search_ui(data: Dict[str, Any]) -> str:
    """
    Build the search results UI HTML from recall data.

    Args:
        data: Recall output containing:
            - topic: Search query string
            - decisions: List of decision results
            - patterns: List of pattern results
            - warnings: List of warning results
            - learnings: List of learning results
            - total_count: Total results count
            - offset: Pagination offset
            - limit: Pagination limit
            - has_more: Whether more results exist

    Returns:
        Complete HTML string for the search results UI
    """
    template = _load_template("search.html")

    topic = data.get("topic", "")
    decisions = data.get("decisions", [])
    patterns = data.get("patterns", [])
    warnings = data.get("warnings", [])
    learnings = data.get("learnings", [])

    # Calculate totals
    total_results = len(decisions) + len(patterns) + len(warnings) + len(learnings)
    total_count = data.get("total_count", total_results)

    # Build result cards
    cards_html = []

    # Helper to render a single card
    def render_card(result: Dict[str, Any], category: str) -> str:
        content = result.get("content", "")
        highlighted_content = _highlight_keywords(content, topic)
        relevance = result.get("relevance", result.get("score", 0))
        semantic_match = result.get("semantic_match", relevance)  # Fallback to relevance if not provided
        recency_weight = result.get("recency_weight", 1.0)  # Default to 1.0 if not provided
        score_width = int(relevance * 100) if relevance <= 1 else int(relevance)
        created_at = _format_date(result.get("created_at", ""))
        tags = result.get("tags", [])
        memory_id = result.get("id")
        worked = result.get("worked")

        tags_html = ""
        if tags:
            tag_spans = [f'<span class="result-card__tag">{tag}</span>' for tag in tags]
            tags_html = f'<div class="result-card__tags">{" ".join(tag_spans)}</div>'

        # Format percentages for display
        semantic_pct = f"{semantic_match:.0%}" if semantic_match <= 1 else f"{semantic_match}%"
        recency_pct = f"{recency_weight:.0%}" if recency_weight <= 1 else f"{recency_weight}%"
        relevance_pct = f"{relevance:.0%}" if relevance <= 1 else f"{relevance}%"

        # Record Outcome button for decisions without outcome yet
        actions_html = ""
        if category == "decision" and worked is None and memory_id is not None:
            actions_html = f'''
    <div class="daemon-card__actions">
        <button class="daemon-btn daemon-btn--small daemon-btn--secondary"
                data-action="record-outcome"
                data-memory-id="{memory_id}">
            Record Outcome
        </button>
    </div>'''

        return f'''
<div class="daemon-card result-card" data-category="{category}">
    <div class="result-card__header">
        <span class="daemon-badge daemon-badge--{category}">{category}</span>
        <div class="daemon-score">
            <span class="daemon-score__value">{relevance:.2f}</span>
            <span class="daemon-score__label">relevance</span>
        </div>
    </div>
    <div class="daemon-score-bar">
        <div class="daemon-score-bar__track">
            <div class="daemon-score-bar__fill" style="width: {score_width}%;"></div>
        </div>
    </div>
    <div class="result-card__content">{highlighted_content}</div>
    <details class="daemon-score-breakdown">
        <summary>Score breakdown</summary>
        <div class="daemon-score-components">
            <div class="daemon-score-component">
                <span class="daemon-score-component__label">Semantic match:</span>
                <span class="daemon-score-component__value">{semantic_pct}</span>
            </div>
            <div class="daemon-score-component">
                <span class="daemon-score-component__label">Recency weight:</span>
                <span class="daemon-score-component__value">{recency_pct}</span>
            </div>
            <div class="daemon-score-component">
                <span class="daemon-score-component__label">Final relevance:</span>
                <span class="daemon-score-component__value">{relevance_pct}</span>
            </div>
        </div>
    </details>
    <div class="result-card__meta">
        <span class="result-card__date">{created_at}</span>
        {tags_html}
    </div>{actions_html}
</div>'''

    # Render all categories
    for result in decisions:
        cards_html.append(render_card(result, "decision"))
    for result in warnings:
        cards_html.append(render_card(result, "warning"))
    for result in patterns:
        cards_html.append(render_card(result, "pattern"))
    for result in learnings:
        cards_html.append(render_card(result, "learning"))

    # Handle empty state
    if not cards_html:
        cards_html.append('''
<div class="daemon-empty" style="grid-column: 1 / -1;">
    <div class="daemon-empty__icon">&#x1F50D;</div>
    <p class="daemon-empty__title">No results found</p>
    <p class="daemon-empty__description">
        No memories matched your search query. Try different keywords or broaden your search.
    </p>
</div>''')

    # Pagination data
    offset = data.get("offset", 0)
    limit = data.get("limit", 10)
    has_more = data.get("has_more", False)

    # Build result count text
    if total_count == total_results:
        result_count_text = f"Showing {total_results} result{'s' if total_results != 1 else ''}"
    else:
        result_count_text = f"Showing {total_results} of {total_count} results"

    # Build pagination HTML (only if needed)
    pagination_html = ""
    if has_more or offset > 0:
        # Calculate display range
        range_start = offset + 1
        range_end = offset + total_results

        prev_disabled = "disabled" if offset == 0 else ""
        next_disabled = "disabled" if not has_more else ""

        pagination_html = f'''
            <div class="daemon-pagination" data-offset="{offset}" data-limit="{limit}">
                <button class="daemon-pagination__btn" data-action="prev" {prev_disabled}>
                    Previous
                </button>
                <span class="daemon-pagination__info">
                    Showing {range_start}-{range_end} of {total_count}
                </span>
                <button class="daemon-pagination__btn" data-action="next" {next_disabled}>
                    Next
                </button>
            </div>'''

    # Inject into template
    html = template.replace("{{TITLE}}", f"Search: {topic}" if topic else "Search Results")
    html = html.replace("{{TOPIC}}", topic if topic else "All")
    html = html.replace("{{RESULT_COUNT}}", result_count_text)
    html = html.replace("{{CONTENT}}", "\n".join(cards_html))
    html = html.replace("{{PAGINATION}}", pagination_html)
    html = _inject_assets(html, include_d3=False)

    return html


def _build_test_ui() -> str:
    """Build a test UI to validate infrastructure works."""
    base = _load_template("base.html")

    # Simple test content using daemon theme classes
    content = '''
<div class="daemon-card" style="padding: 20px; text-align: center;">
    <h1 style="color: var(--daemon-accent);">Daem0n UI Infrastructure</h1>
    <p style="color: var(--daemon-text-muted);">
        If you can see this styled card, the MCP Apps infrastructure is working.
    </p>
    <div class="daemon-badge" style="display: inline-block;">
        INFRA-03 Validated
    </div>
</div>
'''

    html = base.replace("{{TITLE}}", "Daem0n Test UI")
    html = html.replace("{{CONTENT}}", content)
    html = _inject_assets(html, include_d3=False)

    return html


def register_ui_resources(mcp: "FastMCP") -> None:
    """
    Register all UI resources with the FastMCP instance.

    Called during server initialization to make UI resources available
    via the ui:// URI scheme.

    Args:
        mcp: The FastMCP server instance to register resources on.
    """

    @mcp.resource(
        uri="ui://daem0n/test",
        name="Test UI",
        description="Test UI to validate MCP Apps infrastructure",
        mime_type=MCP_APPS_MIME
    )
    def get_test_ui() -> str:
        """Serve the test UI template."""
        return _build_test_ui()

    @mcp.resource(
        uri="ui://daem0n/search/{data}",
        name="Search Results",
        description="Visual search results with filtering and score insights",
        mime_type=MCP_APPS_MIME
    )
    def get_search_ui(data: str) -> str:
        """
        Render search results as visual cards.

        Args:
            data: JSON string containing recall output with topic,
                  decisions, patterns, warnings, learnings, etc.

        Returns:
            Complete HTML for the search results UI
        """
        parsed = json.loads(data) if data else {}
        return _build_search_ui(parsed)

    # Additional resources will be registered in later phases:
    # - ui://daem0n/briefing (Phase 8)
    # - ui://daem0n/covenant (Phase 9)
    # - ui://daem0n/community (Phase 10)
    # - ui://daem0n/graph (Phase 11)


__all__ = [
    "MCP_APPS_MIME",
    "TEMPLATES_DIR",
    "STATIC_DIR",
    "BUILD_DIR",
    "register_ui_resources",
    "_build_search_ui",
    "_highlight_keywords",
]
