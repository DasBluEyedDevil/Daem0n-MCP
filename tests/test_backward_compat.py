"""Tests for backward compatibility of deprecated tools."""

import pytest


class TestDeprecatedToolsExist:
    """Verify old tool names still work as aliases."""

    @pytest.mark.asyncio
    async def test_get_briefing_still_exists(self):
        from daem0nmcp.server import mcp
        tools = {t.name for t in await mcp.list_tools()}
        assert "get_briefing" in tools

    @pytest.mark.asyncio
    async def test_remember_still_exists(self):
        from daem0nmcp.server import mcp
        tools = {t.name for t in await mcp.list_tools()}
        assert "remember" in tools

    @pytest.mark.asyncio
    async def test_recall_still_exists(self):
        from daem0nmcp.server import mcp
        tools = {t.name for t in await mcp.list_tools()}
        assert "recall" in tools

    @pytest.mark.asyncio
    async def test_context_check_still_exists(self):
        from daem0nmcp.server import mcp
        tools = {t.name for t in await mcp.list_tools()}
        assert "context_check" in tools

    @pytest.mark.asyncio
    async def test_record_outcome_still_exists(self):
        from daem0nmcp.server import mcp
        tools = {t.name for t in await mcp.list_tools()}
        assert "record_outcome" in tools
