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
    Auto-migrates existing databases on startup.
    """

    def __init__(self, storage_path: str = "./storage", db_name: str = "daem0nmcp.db"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.db_path = self.storage_path / db_name
        self.db_url = f"sqlite+aiosqlite:///{self.db_path}"
        self._migrated = False
        self._initialized = False
        self._engine = None
        self._session_factory = None

    def _get_engine(self):
        """Lazy engine creation - ensures it's created in the right event loop context."""
        if self._engine is None:
            self._engine = create_async_engine(
                self.db_url,
                connect_args={"check_same_thread": False},
                # Use NullPool for SQLite to avoid connection issues across async contexts
                # Each operation gets a fresh connection
                poolclass=StaticPool,
                pool_pre_ping=True,
            )
            self._session_factory = async_sessionmaker(
                bind=self._engine,
                expire_on_commit=False,
                class_=AsyncSession
            )
        return self._engine

    @property
    def engine(self):
        """Property for backward compatibility."""
        return self._get_engine()

    @property
    def SessionLocal(self):
        """Property for backward compatibility."""
        self._get_engine()  # Ensure engine is created
        return self._session_factory

    def _run_migrations(self):
        """Run schema migrations (sync, before async engine starts)."""
        if self._migrated:
            return

        if self.db_path.exists():
            try:
                from .migrations import run_migrations
                count, applied = run_migrations(str(self.db_path))
                if count > 0:
                    logger.info(f"Applied {count} migration(s): {applied}")
            except Exception as e:
                logger.warning(f"Migration check failed: {e}")

        self._migrated = True

    async def init_db(self):
        """Initialize the database tables and run migrations."""
        # Skip if already initialized
        if self._initialized:
            return

        # Run migrations first (sync operation on existing DB)
        # This happens BEFORE we create the async engine to avoid lock conflicts
        self._run_migrations()

        # Then create any new tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self._initialized = True
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
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            self._initialized = False
