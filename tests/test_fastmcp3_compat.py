# tests/test_fastmcp3_compat.py
"""Test FastMCP 3.0 compatibility."""


def test_fastmcp_import():
    """Verify FastMCP 3.0 import works."""
    from fastmcp import FastMCP
    assert FastMCP is not None


def test_fastmcp_version():
    """Verify FastMCP version is 3.x."""
    import fastmcp
    version = getattr(fastmcp, '__version__', '0.0.0')
    major = int(version.split('.')[0])
    assert major >= 3, f"Expected FastMCP 3.x, got {version}"
