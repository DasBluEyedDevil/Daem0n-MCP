"""Test CovenantTransform implementation for FastMCP 3.0.

This tests the middleware-style Sacred Covenant enforcement that intercepts
tool calls to ensure proper communion (get_briefing) and counsel (context_check)
before allowing operations.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_covenant_transform_exists():
    """Verify CovenantTransform can be imported."""
    from daem0nmcp.transforms.covenant import CovenantTransform
    assert CovenantTransform is not None


@pytest.mark.asyncio
async def test_covenant_transform_blocks_without_briefing():
    """Tool calls should be blocked if get_briefing not called."""
    from daem0nmcp.transforms.covenant import CovenantTransform

    transform = CovenantTransform()

    # Should return blocked response when not briefed
    result = transform.check_tool_access(
        tool_name="remember",
        project_path="/test/project",
        get_state=lambda p: {"briefed": False, "context_checks": []}
    )

    assert result is not None
    assert result["status"] == "blocked"
    assert result["violation"] == "COMMUNION_REQUIRED"


@pytest.mark.asyncio
async def test_covenant_transform_allows_exempt_tools():
    """Exempt tools should always be allowed."""
    from daem0nmcp.transforms.covenant import CovenantTransform

    transform = CovenantTransform()

    # get_briefing is exempt - should be allowed even without briefing
    result = transform.check_tool_access(
        tool_name="get_briefing",
        project_path="/test/project",
        get_state=lambda p: {"briefed": False, "context_checks": []}
    )

    assert result is None  # None means allowed


@pytest.mark.asyncio
async def test_covenant_transform_blocks_counsel_required():
    """Counsel-required tools need context_check."""
    from daem0nmcp.transforms.covenant import CovenantTransform

    transform = CovenantTransform()

    # Briefed but no context_check
    result = transform.check_tool_access(
        tool_name="remember",
        project_path="/test/project",
        get_state=lambda p: {"briefed": True, "context_checks": []}
    )

    assert result is not None
    assert result["status"] == "blocked"
    assert result["violation"] == "COUNSEL_REQUIRED"


@pytest.mark.asyncio
async def test_covenant_transform_allows_with_fresh_counsel():
    """Tools should be allowed when counsel is fresh."""
    from daem0nmcp.transforms.covenant import CovenantTransform

    transform = CovenantTransform()

    # Briefed with fresh context_check
    result = transform.check_tool_access(
        tool_name="remember",
        project_path="/test/project",
        get_state=lambda p: {
            "briefed": True,
            "context_checks": [
                {"topic": "remember", "timestamp": datetime.now(timezone.utc).isoformat()}
            ]
        }
    )

    assert result is None  # None means allowed


@pytest.mark.asyncio
async def test_covenant_transform_blocks_stale_counsel():
    """Tools should be blocked when counsel is stale (expired)."""
    from daem0nmcp.transforms.covenant import CovenantTransform
    from datetime import timedelta

    transform = CovenantTransform()

    # Briefed with stale context_check (10 minutes old, TTL is 5 minutes)
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    result = transform.check_tool_access(
        tool_name="remember",
        project_path="/test/project",
        get_state=lambda p: {
            "briefed": True,
            "context_checks": [
                {"topic": "remember", "timestamp": stale_time.isoformat()}
            ]
        }
    )

    assert result is not None
    assert result["status"] == "blocked"
    assert result["violation"] == "COUNSEL_EXPIRED"


@pytest.mark.asyncio
async def test_covenant_transform_communion_only_tools():
    """Some tools require communion but not counsel."""
    from daem0nmcp.transforms.covenant import CovenantTransform

    transform = CovenantTransform()

    # record_outcome requires communion but not counsel
    result = transform.check_tool_access(
        tool_name="record_outcome",
        project_path="/test/project",
        get_state=lambda p: {"briefed": True, "context_checks": []}
    )

    # Should be allowed because record_outcome only needs communion, not counsel
    assert result is None


@pytest.mark.asyncio
async def test_covenant_transform_read_only_tools_exempt():
    """Read-only tools should be exempt."""
    from daem0nmcp.transforms.covenant import CovenantTransform

    transform = CovenantTransform()

    # recall is a read-only tool - should be allowed without briefing
    result = transform.check_tool_access(
        tool_name="recall",
        project_path="/test/project",
        get_state=lambda p: {"briefed": False, "context_checks": []}
    )

    assert result is None  # None means allowed


@pytest.mark.asyncio
async def test_covenant_transform_health_exempt():
    """Health tool should always be exempt."""
    from daem0nmcp.transforms.covenant import CovenantTransform

    transform = CovenantTransform()

    # health is always allowed
    result = transform.check_tool_access(
        tool_name="health",
        project_path="/test/project",
        get_state=lambda p: {"briefed": False, "context_checks": []}
    )

    assert result is None  # None means allowed


@pytest.mark.asyncio
async def test_covenant_transform_context_check_exempt():
    """context_check itself should be exempt."""
    from daem0nmcp.transforms.covenant import CovenantTransform

    transform = CovenantTransform()

    # context_check is part of the covenant flow - should be allowed
    result = transform.check_tool_access(
        tool_name="context_check",
        project_path="/test/project",
        get_state=lambda p: {"briefed": True, "context_checks": []}
    )

    assert result is None  # None means allowed


@pytest.mark.asyncio
async def test_covenant_transform_tool_classifications():
    """Verify tool classification sets are properly defined."""
    from daem0nmcp.transforms.covenant import (
        COVENANT_EXEMPT_TOOLS,
        COMMUNION_REQUIRED_TOOLS,
        COUNSEL_REQUIRED_TOOLS,
    )

    # Entry points and diagnostics should be exempt
    assert "get_briefing" in COVENANT_EXEMPT_TOOLS
    assert "health" in COVENANT_EXEMPT_TOOLS
    assert "context_check" in COVENANT_EXEMPT_TOOLS

    # Read-only query tools should be exempt
    assert "recall" in COVENANT_EXEMPT_TOOLS
    assert "recall_for_file" in COVENANT_EXEMPT_TOOLS
    assert "search_memories" in COVENANT_EXEMPT_TOOLS

    # Mutating tools require communion
    assert "remember" in COMMUNION_REQUIRED_TOOLS
    assert "remember_batch" in COMMUNION_REQUIRED_TOOLS
    assert "add_rule" in COMMUNION_REQUIRED_TOOLS

    # Highly destructive operations require both communion and counsel
    assert "remember" in COUNSEL_REQUIRED_TOOLS
    assert "prune_memories" in COUNSEL_REQUIRED_TOOLS


@pytest.mark.asyncio
async def test_covenant_violation_response_structure():
    """Test the CovenantViolation response structure."""
    from daem0nmcp.transforms.covenant import CovenantViolation

    # Test communion_required response
    response = CovenantViolation.communion_required("/test/project")
    assert response["status"] == "blocked"
    assert response["violation"] == "COMMUNION_REQUIRED"
    assert "remedy" in response
    assert response["remedy"]["tool"] == "get_briefing"
    assert response["project_path"] == "/test/project"

    # Test counsel_required response
    response = CovenantViolation.counsel_required("remember", "/test/project")
    assert response["status"] == "blocked"
    assert response["violation"] == "COUNSEL_REQUIRED"
    assert "remedy" in response
    assert response["remedy"]["tool"] == "context_check"
    assert response["tool_blocked"] == "remember"

    # Test counsel_expired response
    response = CovenantViolation.counsel_expired("remember", "/test/project", 400)
    assert response["status"] == "blocked"
    assert response["violation"] == "COUNSEL_EXPIRED"
    assert "400" in response["message"]  # Age should be in message


@pytest.mark.asyncio
async def test_covenant_transform_no_project_path():
    """Tools should work when project_path is None (for some tools)."""
    from daem0nmcp.transforms.covenant import CovenantTransform

    transform = CovenantTransform()

    # health tool doesn't need project_path
    result = transform.check_tool_access(
        tool_name="health",
        project_path=None,
        get_state=lambda p: None
    )

    assert result is None  # None means allowed


@pytest.mark.asyncio
async def test_covenant_transform_missing_state():
    """Handle case when state is unavailable."""
    from daem0nmcp.transforms.covenant import CovenantTransform

    transform = CovenantTransform()

    # State callback returns None
    result = transform.check_tool_access(
        tool_name="remember",
        project_path="/test/project",
        get_state=lambda p: None
    )

    assert result is not None
    assert result["status"] == "blocked"
    assert result["violation"] == "COMMUNION_REQUIRED"
