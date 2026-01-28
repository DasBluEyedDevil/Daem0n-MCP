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
from pathlib import Path
from typing import TYPE_CHECKING

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

    # Additional resources will be registered in later phases:
    # - ui://daem0n/search (Phase 7)
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
]
