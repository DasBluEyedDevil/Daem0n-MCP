#!/usr/bin/env python
"""
Start Daem0nMCP as an HTTP server for Claude Code.

Usage:
  python start_server.py [--port PORT] [--project PATH]

Default port is 9876. Server will be at http://localhost:9876/mcp

On Windows, stdio transport has known issues, so HTTP is required.
Run this server BEFORE starting Claude Code.
"""
import sys
import os
import argparse

# Add the package to path if running from this directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(description="Start Daem0nMCP HTTP server")
    parser.add_argument('--port', '-p', type=int, default=9876, help="Port to listen on (default: 9876)")
    parser.add_argument('--host', default='127.0.0.1', help="Host to bind to")
    parser.add_argument('--project', help="Project directory for storage (default: current directory)")
    args = parser.parse_args()

    # Set project root
    project_root = args.project or os.getcwd()
    os.environ['DAEM0NMCP_PROJECT_ROOT'] = project_root

    # Import after setting environment
    from daem0nmcp.server import mcp
    import fastmcp

    # Configure server
    fastmcp.settings.host = args.host
    fastmcp.settings.port = args.port

    print(f"=" * 60)
    print(f"Daem0nMCP HTTP Server")
    print(f"=" * 60)
    print(f"URL: http://{args.host}:{args.port}/mcp")
    print(f"Project: {project_root}")
    print(f"")
    print(f"Add this to Claude Code config (~/.claude.json):")
    print(f'  "daem0nmcp": {{')
    print(f'    "type": "http",')
    print(f'    "url": "http://localhost:{args.port}/mcp"')
    print(f'  }}')
    print(f"=" * 60)
    print(f"Press Ctrl+C to stop")
    print()

    mcp.run(transport="streamable-http")


if __name__ == '__main__':
    main()
