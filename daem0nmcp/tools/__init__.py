"""
Daem0nMCP tool modules.

Each module in this package registers @mcp.tool decorated functions
against the shared FastMCP instance from mcp_instance.py.

Import hierarchy:
    mcp_instance  (shared FastMCP -- zero business imports)
        <- context_manager  (ProjectContext lifecycle)
            <- tools/*  (THIS PACKAGE -- tool definitions)
                <- server.py  (composition root)

Do NOT import tool modules in this __init__.py -- registration
happens via side-effect imports in server.py.
"""
