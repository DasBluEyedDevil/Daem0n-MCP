"""
Centralized configuration using Pydantic Settings.

All settings are loaded from environment variables with DEVILMCP_ prefix.
Example: DEVILMCP_LOG_LEVEL=DEBUG
"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """DevilMCP configuration settings."""

    # Core paths
    project_root: str = "."
    storage_path: Optional[str] = None  # Auto-detect if not set

    # Server
    log_level: str = "INFO"

    class Config:
        env_prefix = "DEVILMCP_"
        env_file = ".env"
        env_file_encoding = "utf-8"

    def get_storage_path(self) -> str:
        """
        Determine storage path with project isolation.

        Priority:
        1. storage_path setting (explicit override via DEVILMCP_STORAGE_PATH)
        2. project_root/.devilmcp/storage (if project_root is set)
        3. <cwd>/.devilmcp/storage (current working directory)
        4. ./storage (fallback for centralized storage)
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

        # If we're running from the DevilMCP server directory itself, use centralized storage
        if project_path == server_path:
            storage = server_path / "storage" / "centralized"
            logger.info("Using centralized storage (running from DevilMCP directory)")
        else:
            # Use project-specific storage
            storage = project_path / ".devilmcp" / "storage"
            logger.info(f"Project detected: {project_path.name}")
            logger.info(f"Using project-specific storage: {storage}")

        # Create directory if it doesn't exist
        storage.mkdir(parents=True, exist_ok=True)

        return str(storage)


# Singleton instance
settings = Settings()
