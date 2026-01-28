"""
Resource registration for MCP Apps UI.

This module defines constants and utilities for registering UI resources
with FastMCP 3.0. The MCP_APPS_MIME type signals to MCP hosts that the
content should be rendered as an interactive HTML application.

Resource registrations will be added in Plan 06-03 (Resource Registration).
"""

from pathlib import Path

# MIME type for MCP Apps (SEP-1865)
# Signals to MCP hosts that this resource should be rendered as HTML UI
MCP_APPS_MIME = "text/html;profile=mcp-app"

# Directory paths for template and static assets
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"
BUILD_DIR = Path(__file__).parent / "build"

__all__ = [
    "MCP_APPS_MIME",
    "TEMPLATES_DIR",
    "STATIC_DIR",
    "BUILD_DIR",
]
