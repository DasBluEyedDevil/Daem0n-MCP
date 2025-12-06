"""
Centralized configuration using Pydantic Settings.

All settings are loaded from environment variables with DEVILMCP_ prefix.
Example: DEVILMCP_PORT=9000, DEVILMCP_LOG_LEVEL=DEBUG
"""

from pathlib import Path
from typing import Optional, List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """DevilMCP configuration settings."""

    # Core paths
    project_root: str = "."
    storage_path: Optional[str] = None  # Auto-detect if not set

    # Server
    port: int = 8080
    log_level: str = "INFO"

    # Timeouts (milliseconds)
    default_command_timeout: int = 30000
    default_init_timeout: int = 10000

    # Feature flags
    auto_migrate: bool = True  # Run Alembic on startup

    # Security settings
    # IMPORTANT: Tool execution is DISABLED by default for security.
    # Set DEVILMCP_TOOL_EXECUTION_ENABLED=true to enable.
    tool_execution_enabled: bool = False

    # Comma-separated list of allowed commands.
    # Only these commands can be executed when tool execution is enabled.
    # Example: DEVILMCP_ALLOWED_COMMANDS="git,python,pytest,npm"
    allowed_commands: str = "git,python,pytest,npm,node"

    class Config:
        env_prefix = "DEVILMCP_"
        env_file = ".env"
        env_file_encoding = "utf-8"

    def get_allowed_commands_list(self) -> List[str]:
        """Get list of allowed commands from comma-separated string."""
        if not self.allowed_commands:
            return []
        return [cmd.strip() for cmd in self.allowed_commands.split(",") if cmd.strip()]

    def is_command_allowed(self, command: str) -> bool:
        """Check if a command is in the whitelist."""
        if not self.tool_execution_enabled:
            return False
        allowed = self.get_allowed_commands_list()
        # Check the base command (e.g., 'python' from 'python3.11')
        base_cmd = command.split("/")[-1]  # Handle full paths
        return base_cmd in allowed or any(base_cmd.startswith(cmd) for cmd in allowed)

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

    def get_database_url(self) -> str:
        """Get SQLite database URL for SQLAlchemy."""
        storage = self.get_storage_path()
        return f"sqlite+aiosqlite:///{storage}/devilmcp.db"


# Singleton instance
settings = Settings()
