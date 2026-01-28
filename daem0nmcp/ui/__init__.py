"""
UI module for Daem0n MCP Apps.

This module provides the infrastructure for visual interfaces that display
daemon knowledge through MCP Apps (SEP-1865). All UIs share a consistent
daemon aesthetic defined in static/daemon.css.

Components:
- templates/: HTML template sources for each UI view
- static/: Bundled assets (CSS, JS) for browser rendering
- build/: Build scripts for asset bundling
- resources.py: FastMCP resource registration

The MCP Apps architecture renders HTML in sandboxed iframes within MCP hosts,
enabling rich visual exploration of memories, patterns, and knowledge graphs.
"""

from .resources import MCP_APPS_MIME

__all__ = [
    "MCP_APPS_MIME",
]
