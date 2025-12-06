"""
Database Manager - Simplified for the focused memory system.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from contextlib import asynccontextmanager
from pathlib import Path
import logging

from .models import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages the SQLite database connection.

    Simplified from the original - no more tool initialization or complex migrations.
    Just creates tables and provides session management.
    """

    def __init__(self, storage_path: str = "./storage", db_name: str = "devilmcp.db"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.db_path = self.storage_path / db_name
        self.db_url = f"sqlite+aiosqlite:///{self.db_path}"

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
        """Initialize the database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info(f"Database initialized at {self.db_path}")

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
