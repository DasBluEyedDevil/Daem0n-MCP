"""
Tool Registry Module
Manages CLI tool configurations and capabilities.

Simplified from the over-engineered version that had:
- Native executor routing (only git was implemented - YAGNI)
- Executor caching (unnecessary complexity)
- Factory patterns (overkill for this use case)
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import toml

from .database import DatabaseManager
from .models import Tool
from .executor import ExecutionResult
from sqlalchemy import select
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ToolCapability(Enum):
    """Capabilities that CLI tools can provide."""
    # Core capabilities
    CODEBASE_ANALYSIS = "codebase_analysis"
    IMPLEMENTATION = "implementation"
    REFACTORING = "refactoring"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    DEBUGGING = "debugging"
    CODE_REVIEW = "code_review"
    FILE_OPERATIONS = "file_operations"
    PROJECT_SETUP = "project_setup"
    UTILITIES = "utilities"


@dataclass
class ToolConfig:
    """Configuration for a CLI tool."""
    name: str
    display_name: str
    command: str
    args: List[str]
    capabilities: List[ToolCapability]
    enabled: bool
    config: Dict
    command_timeout: int = 30000  # 30 seconds default


class ToolRegistry:
    """Registry for CLI tools - simplified."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self._tools_cache: Dict[str, ToolConfig] = {}

    async def load_tools(self) -> None:
        """Load tool configurations from database."""
        self._tools_cache.clear()

        async with self.db.get_session() as session:
            result = await session.execute(select(Tool).where(Tool.enabled == 1))
            tools = result.scalars().all()

            for tool in tools:
                cfg = tool.config or {}

                # Parse capabilities, skip invalid ones
                valid_capabilities = []
                for cap_str in (tool.capabilities or []):
                    try:
                        valid_capabilities.append(ToolCapability(cap_str))
                    except ValueError:
                        logger.warning(f"Tool '{tool.name}' has unknown capability '{cap_str}'")

                tool_config = ToolConfig(
                    name=tool.name,
                    display_name=tool.display_name,
                    command=tool.command,
                    args=tool.args or [],
                    capabilities=valid_capabilities,
                    enabled=bool(tool.enabled),
                    config=cfg,
                    command_timeout=cfg.get("command_timeout", 30000)
                )
                self._tools_cache[tool.name] = tool_config

        logger.info(f"Loaded {len(self._tools_cache)} tools from DB")

    def get_tool(self, name: str) -> Optional[ToolConfig]:
        """Get tool configuration by name."""
        return self._tools_cache.get(name)

    def get_tools_by_capability(self, capability: ToolCapability) -> List[ToolConfig]:
        """Get all tools that have a specific capability."""
        return [
            tool for tool in self._tools_cache.values()
            if capability in tool.capabilities and tool.enabled
        ]

    def get_all_tools(self) -> List[ToolConfig]:
        """Get all enabled tools."""
        return [tool for tool in self._tools_cache.values() if tool.enabled]

    async def register_tool(
        self,
        name: str,
        display_name: str,
        command: str,
        capabilities: List[str],
        args: Optional[List[str]] = None,
        config: Optional[Dict] = None
    ) -> bool:
        """Register a new tool."""
        async with self.db.get_session() as session:
            tool = Tool(
                name=name,
                display_name=display_name,
                command=command,
                capabilities=capabilities,
                args=args or [],
                enabled=1,
                config=config or {},
                created_at=datetime.now(timezone.utc)
            )
            session.add(tool)
            await session.commit()

        await self.load_tools()
        logger.info(f"Registered tool: {name}")
        return True

    async def update_tool(
        self,
        name: str,
        display_name: Optional[str] = None,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        capabilities: Optional[List[str]] = None,
        enabled: Optional[bool] = None,
        config: Optional[Dict] = None
    ) -> Optional[ToolConfig]:
        """Update an existing tool's configuration."""
        async with self.db.get_session() as session:
            stmt = select(Tool).where(Tool.name == name)
            result = await session.execute(stmt)
            tool = result.scalar_one_or_none()

            if not tool:
                logger.warning(f"Tool '{name}' not found")
                return None

            if display_name is not None:
                tool.display_name = display_name
            if command is not None:
                tool.command = command
            if args is not None:
                tool.args = args
            if capabilities is not None:
                tool.capabilities = capabilities
            if enabled is not None:
                tool.enabled = 1 if enabled else 0
            if config is not None:
                tool.config = config

            await session.commit()
            await self.load_tools()
            logger.info(f"Updated tool: {name}")
            return self.get_tool(name)

    async def disable_tool(self, name: str) -> bool:
        """Disable a tool."""
        result = await self.update_tool(name, enabled=False)
        return result is not None

    async def enable_tool(self, name: str) -> bool:
        """Enable a tool."""
        result = await self.update_tool(name, enabled=True)
        return result is not None

    async def execute_tool(
        self,
        tool_name: str,
        command: str,
        args: List[str] = None
    ) -> ExecutionResult:
        """Execute a tool command.

        Security: Checks that tool execution is enabled and command is whitelisted.
        """
        from .subprocess_executor import SubprocessExecutor
        from .config import settings

        args = args or []

        # Security check: is tool execution enabled?
        if not settings.tool_execution_enabled:
            return ExecutionResult(
                success=False,
                output="",
                error="Tool execution is disabled. Set DEVILMCP_TOOL_EXECUTION_ENABLED=true to enable."
            )

        tool_config = self.get_tool(tool_name)
        if not tool_config:
            return ExecutionResult(
                success=False,
                output="",
                error=f"Tool '{tool_name}' not found or not enabled"
            )

        # Security check: is the command whitelisted?
        if not settings.is_command_allowed(tool_config.command):
            return ExecutionResult(
                success=False,
                output="",
                error=f"Command '{tool_config.command}' is not in the allowed list. "
                      f"Allowed commands: {settings.allowed_commands}"
            )

        executor = SubprocessExecutor(tool_config)
        try:
            return await executor.execute(command, args)
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return ExecutionResult(
                success=False,
                output="",
                error=f"Execution failed: {e}"
            )
