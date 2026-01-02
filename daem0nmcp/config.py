"""
Centralized configuration using Pydantic Settings.

All settings are loaded from environment variables with DAEM0NMCP_ prefix.
Example: DAEM0NMCP_LOG_LEVEL=DEBUG
"""

import shutil
from pathlib import Path
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Daem0nMCP configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="DAEM0NMCP_",
        env_file=".env",
        env_file_encoding="utf-8"
    )

    # Core paths
    project_root: str = "."
    storage_path: Optional[str] = None  # Auto-detect if not set

    # Server
    log_level: str = "INFO"

    # Context management
    max_project_contexts: int = 10  # Maximum cached project contexts
    context_ttl_seconds: int = 3600  # 1 hour TTL for unused contexts

    # Enforcement settings
    pending_decision_threshold_hours: int = 24  # Hours before pending decisions block commits

    # Ingestion limits
    max_content_size: int = 1_000_000  # 1MB max content
    max_chunks: int = 50  # Maximum chunks per ingestion
    ingest_timeout: int = 30  # Request timeout in seconds
    allowed_url_schemes: List[str] = ["http", "https"]

    # TODO scanner config
    todo_skip_dirs: List[str] = [
        "node_modules", ".git", ".venv", "venv", "__pycache__",
        "dist", "build", ".tox", ".mypy_cache", ".pytest_cache",
        ".eggs", ".coverage", "htmlcov", ".daem0nmcp", ".svn", ".hg"
    ]
    todo_skip_extensions: List[str] = [".pyc", ".pyo", ".so", ".dylib"]
    todo_max_files: int = 500

    # Qdrant vector storage
    qdrant_path: Optional[str] = None  # Path for local Qdrant storage, auto-detect if not set
    qdrant_url: Optional[str] = None   # Optional remote Qdrant URL (overrides local path)
    qdrant_api_key: Optional[str] = None  # API key for remote Qdrant (if using cloud)

    def _migrate_legacy_storage(self, project_path: Path, new_storage: Path) -> bool:
        """
        Migrate data from legacy .devilmcp directory to .daem0nmcp.

        Returns True if migration occurred.
        """
        import logging
        logger = logging.getLogger(__name__)

        legacy_storage = project_path / ".devilmcp" / "storage"
        legacy_db = legacy_storage / "devilmcp.db"
        new_db = new_storage / "daem0nmcp.db"

        # Check if legacy storage exists and new doesn't have data yet
        if not legacy_storage.exists():
            return False

        if new_db.exists():
            logger.info("New database already exists, skipping legacy migration")
            return False

        # Create new storage directory
        new_storage.mkdir(parents=True, exist_ok=True)

        # Migrate database file
        if legacy_db.exists():
            shutil.copy2(legacy_db, new_db)
            logger.info(f"Migrated database: {legacy_db} -> {new_db}")

        # Also check for any other .db files (e.g., daem0nmcp.db in old location)
        for db_file in legacy_storage.glob("*.db"):
            if db_file.name != "devilmcp.db":
                dest = new_storage / db_file.name
                if not dest.exists():
                    shutil.copy2(db_file, dest)
                    logger.info(f"Migrated database: {db_file} -> {dest}")

        logger.info(
            f"Legacy migration complete. You can safely delete: {project_path / '.devilmcp'}"
        )
        return True

    def get_storage_path(self) -> str:
        """
        Determine storage path with project isolation.

        Priority:
        1. storage_path setting (explicit override via DAEM0NMCP_STORAGE_PATH)
        2. project_root/.daem0nmcp/storage (if project_root is set)
        3. <cwd>/.daem0nmcp/storage (current working directory)
        4. ./storage (fallback for centralized storage)

        Also handles automatic migration from legacy .devilmcp storage.
        """
        import logging
        logger = logging.getLogger(__name__)

        # Check for explicit storage path override
        if self.storage_path:
            Path(self.storage_path).mkdir(parents=True, exist_ok=True)
            return self.storage_path

        # Get project root
        project_path = Path(self.project_root).resolve()
        server_path = Path(__file__).parent.resolve()

        # If we're running from the Daem0nMCP server directory itself, use centralized storage
        if project_path == server_path:
            storage = server_path / "storage" / "centralized"
            logger.info("Using centralized storage (running from Daem0nMCP directory)")
        else:
            # Use project-specific storage
            storage = project_path / ".daem0nmcp" / "storage"

            # Check for and migrate legacy .devilmcp storage
            self._migrate_legacy_storage(project_path, storage)

            logger.info(f"Project detected: {project_path.name}")
            logger.info(f"Using project-specific storage: {storage}")

        # Create directory if it doesn't exist
        storage.mkdir(parents=True, exist_ok=True)

        return str(storage)

    def get_qdrant_path(self) -> Optional[str]:
        """
        Determine Qdrant storage path for local mode.

        Returns None if qdrant_url is set (remote mode).

        Priority for local mode:
        1. qdrant_path setting (explicit override via DAEM0NMCP_QDRANT_PATH)
        2. <storage_path>/qdrant (next to the SQLite database)
        """
        # Remote mode - no local path needed
        if self.qdrant_url:
            return None

        if self.qdrant_path:
            Path(self.qdrant_path).mkdir(parents=True, exist_ok=True)
            return self.qdrant_path

        # Use subdirectory of main storage
        storage = Path(self.get_storage_path())
        qdrant_dir = storage / "qdrant"
        qdrant_dir.mkdir(parents=True, exist_ok=True)
        return str(qdrant_dir)


# Singleton instance
settings = Settings()
