from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from contextlib import asynccontextmanager
from pathlib import Path
from models import Base, Tool
from sqlalchemy import select
import toml
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, storage_path: str = "./storage", db_name: str = "devilmcp.db"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self.db_url = f"sqlite+aiosqlite:///{self.storage_path}/{db_name}"
        
        self.engine = create_async_engine(
            self.db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = async_sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            class_=AsyncSession
        )

    async def init_db(self):
        """Initialize the database tables and default tools."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        await self._init_default_tools()

    async def _init_default_tools(self):
        """Initialize default tool configurations from tools.toml into the database."""
        tools_toml_path = Path("tools.toml")
        if not tools_toml_path.exists():
            logger.warning(f"tools.toml not found at {tools_toml_path}. Skipping default tool initialization.")
            return

        try:
            config = toml.load(tools_toml_path)
            if "tools" not in config:
                logger.warning("No 'tools' section found in tools.toml. Skipping default tool initialization.")
                return

            async with self.get_session() as session:
                for tool_name, tool_data in config["tools"].items():
                    # Check if tool exists
                    result = await session.execute(
                        select(Tool).where(Tool.name == tool_name)
                    )
                    existing_tool = result.scalar_one_or_none()
                    
                    if existing_tool:
                        # Update existing tool
                        existing_tool.display_name = tool_data.get("display_name", existing_tool.display_name)
                        existing_tool.command = tool_data.get("command", existing_tool.command)
                        existing_tool.args = tool_data.get("args", existing_tool.args)
                        existing_tool.capabilities = tool_data.get("capabilities", existing_tool.capabilities)
                        existing_tool.enabled = 1 if tool_data.get("enabled", True) else 0
                        existing_tool.config = tool_data.get("config", existing_tool.config)
                        logger.info(f"Updated default tool: {tool_name}")
                    else:
                        # Create new tool
                        new_tool = Tool(
                            name=tool_name,
                            display_name=tool_data.get("display_name", tool_name),
                            command=tool_data.get("command", tool_name),
                            args=tool_data.get("args", []),
                            capabilities=tool_data.get("capabilities", []),
                            enabled=1 if tool_data.get("enabled", True) else 0,
                            config=tool_data.get("config", {}),
                            created_at=datetime.now(timezone.utc)
                        )
                        session.add(new_tool)
                        logger.info(f"Registered default tool: {tool_name}")
                await session.commit()
        except Exception as e:
            logger.error(f"Error initializing default tools from tools.toml: {e}", exc_info=True)

    @asynccontextmanager
    async def get_session(self):
        """Provide a transactional scope around a series of operations."""
        session = self.SessionLocal()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def close(self):
        """Dispose of the engine."""
        await self.engine.dispose()
