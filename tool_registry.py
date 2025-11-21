"""
Tool Registry Module
Manages CLI tool configurations and capabilities.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import toml

from database import DatabaseManager
from models import Tool
from sqlalchemy import select
from datetime import datetime, timezone # Import for default values if tools.toml is missing created_at

logger = logging.getLogger(__name__)

class ToolCapability(Enum):
    """Capabilities that CLI tools can provide"""
    ORCHESTRATOR = "orchestrator"
    PLANNING = "planning"
    ARCHITECT = "architect"
    UI_DESIGNER = "ui_designer"
    PRIMARY_DEVELOPER = "primary_developer"
    BACKEND_DEVELOPER = "backend_developer"
    API_IMPLEMENTATION = "api_implementation"
    DATABASE_MANAGEMENT = "database_management"
    SERVER_LOGIC = "server_logic"
    CORE_ALGORITHMS = "core_algorithms"
    SECONDARY_DEVELOPER = "secondary_developer"
    TECHNICAL_TASK_PERFORMER = "technical_task_performer"
    SCRIPTING = "scripting"
    UTILITIES = "utilities"
    DEV_OPS = "dev_ops"
    CODEBASE_ANALYSIS = "codebase_analysis"
    IMPLEMENTATION = "implementation"
    REFACTORING = "refactoring"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    DEBUGGING = "debugging"
    CODE_REVIEW = "code_review"
    INLINE_EDITING = "inline_editing"
    FILE_OPERATIONS = "file_operations"
    PROJECT_SETUP = "project_setup"

@dataclass
class ToolConfig:
    """Configuration for a CLI tool"""
    name: str
    display_name: str
    command: str
    args: List[str]
    capabilities: List[ToolCapability]
    enabled: bool
    config: Dict
    
    # Specific config parameters
    prompt_patterns: List[str]
    init_timeout: int
    command_timeout: int
    max_context_size: Optional[int]
    supports_streaming: bool

class ToolRegistry:
    """Central registry for CLI tools"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self._tools_cache: Dict[str, ToolConfig] = {}
    
    async def load_tools(self):
        """Load tool configurations from database"""
        self._tools_cache.clear() # Clear cache first to handle disabled tools removal
        async with self.db.get_session() as session:
            result = await session.execute(select(Tool).where(Tool.enabled == 1))
            tools = result.scalars().all()
            
            for tool in tools:
                # Ensure all config parameters have defaults
                cfg = tool.config
                tool_config = ToolConfig(
                    name=tool.name,
                    display_name=tool.display_name,
                    command=tool.command,
                    args=tool.args,
                    capabilities=[ToolCapability(c) for c in tool.capabilities],
                    enabled=bool(tool.enabled),
                    config=cfg,
                    prompt_patterns=cfg.get("prompt_patterns", [">>> ", "$ ", "> "]),
                    init_timeout=cfg.get("init_timeout", 10000),
                    command_timeout=cfg.get("command_timeout", 30000),
                    max_context_size=cfg.get("max_context_size"),
                    supports_streaming=cfg.get("supports_streaming", False)
                )
                self._tools_cache[tool.name] = tool_config
        
        logger.info(f"Loaded {len(self._tools_cache)} tools from DB")
    
    def get_tool(self, name: str) -> Optional[ToolConfig]:
        """Get tool configuration by name"""
        return self._tools_cache.get(name)
    
    def get_tools_by_capability(self, capability: ToolCapability) -> List[ToolConfig]:
        """Get all tools that have a specific capability"""
        return [
            tool for tool in self._tools_cache.values()
            if capability in tool.capabilities and tool.enabled
        ]
    
    def get_all_tools(self) -> List[ToolConfig]:
        """Get all enabled tools"""
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
        """Register a new tool"""
        tool_data = {
            "name": name,
            "display_name": display_name,
            "command": command,
            "capabilities": capabilities,
            "args": args or [],
            "enabled": 1,
            "config": config or {},
            "created_at": datetime.now(timezone.utc)
        }
        
        async with self.db.get_session() as session:
            tool = Tool(**tool_data)
            session.add(tool)
            await session.commit()
        
        # Reload cache
        await self.load_tools()
        logger.info(f"Registered custom tool: {name}")
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
                logger.warning(f"Tool '{name}' not found for update.")
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
                tool.config = config # Overwrite or merge? For now, overwrite.
            
            await session.commit()
            await session.refresh(tool)
            await self.load_tools() # Reload cache
            logger.info(f"Updated tool: {name}")
            return self.get_tool(name)

    async def disable_tool(self, name: str) -> bool:
        """Disable a tool."""
        async with self.db.get_session() as session:
            stmt = select(Tool).where(Tool.name == name)
            result = await session.execute(stmt)
            tool = result.scalar_one_or_none()
            if tool:
                tool.enabled = 0
                await session.commit()
                await self.load_tools()
                logger.info(f"Disabled tool: {name}")
                return True
            logger.warning(f"Tool '{name}' not found for disabling.")
            return False

    async def enable_tool(self, name: str) -> bool:
        """Enable a tool."""
        async with self.db.get_session() as session:
            stmt = select(Tool).where(Tool.name == name)
            result = await session.execute(stmt)
            tool = result.scalar_one_or_none()
            if tool:
                tool.enabled = 1
                await session.commit()
                await self.load_tools()
                logger.info(f"Enabled tool: {name}")
                return True
            logger.warning(f"Tool '{name}' not found for enabling.")
            return False
