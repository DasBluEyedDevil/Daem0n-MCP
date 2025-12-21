"""Tests for project context management."""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from pathlib import Path
import tempfile
import shutil


class TestProjectContextConcurrency:
    """Test concurrent access to project contexts."""

    @pytest.fixture
    def temp_projects(self):
        """Create temporary project directories."""
        dirs = [tempfile.mkdtemp() for _ in range(3)]
        yield dirs
        for d in dirs:
            shutil.rmtree(d, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_concurrent_context_creation_uses_lock(self, temp_projects):
        """Verify that concurrent calls to get_project_context don't race."""
        from daem0nmcp.server import get_project_context, _project_contexts, _context_locks

        # Clear existing contexts and locks
        _project_contexts.clear()
        _context_locks.clear()

        project_path = temp_projects[0]

        # Track how many times init_db is called
        init_count = 0
        original_init = None

        async def counting_init(self):
            nonlocal init_count
            init_count += 1
            await asyncio.sleep(0.1)  # Simulate slow init
            if original_init:
                await original_init(self)

        # Patch init_db to count calls
        from daem0nmcp.database import DatabaseManager
        original_init = DatabaseManager.init_db

        with patch.object(DatabaseManager, 'init_db', counting_init):
            # Launch concurrent requests
            tasks = [get_project_context(project_path) for _ in range(5)]
            contexts = await asyncio.gather(*tasks)

        # All should return the same context
        assert all(c is contexts[0] for c in contexts)
        # init_db should only be called once due to locking
        assert init_count == 1, f"init_db called {init_count} times, expected 1"
