# Coding Conventions

**Analysis Date:** 2026-01-22

## Naming Patterns

**Files:**
- Module names: `snake_case` (e.g., `entity_manager.py`, `logging_config.py`)
- Test files: `test_*.py` pattern (e.g., `test_memory.py`, `test_covenant.py`)
- Migration files: `migrate_vectors.py`, `schema.py` in `daem0nmcp/migrations/`

**Functions:**
- Function names: `snake_case` (e.g., `_normalize_file_path`, `extract_keywords`, `remember`)
- Private/internal functions: Prefix with underscore (e.g., `_safe_mkdtemp`, `_get_or_create_entity`)
- Async functions: Same naming as sync (e.g., `async def remember()`, `async def process_memory()`)
- Test functions: `test_*` pattern, organized in test classes (e.g., `def test_remember_decision`)

**Variables:**
- Local variables: `snake_case` (e.g., `temp_dir`, `file_path`, `memory_manager`)
- Constants: `UPPER_CASE` (e.g., `VALID_RELATIONSHIPS`, `FAILED_DECISION_BOOST`, `SAFE_TMP_ROOT`)
- Type hints: Always use `Optional[Type]` for nullable values, use `Union` for multiple types
- Context variables: Suffix with `_var` (e.g., `request_id_var`)

**Classes:**
- Class names: `PascalCase` (e.g., `Settings`, `MemoryManager`, `DatabaseManager`, `EntityExtractor`)
- Exception classes: `PascalCase` with `Exception` suffix (e.g., `CovenantViolation`)
- Base classes: `Base` (e.g., `class Base(DeclarativeBase)`)

**Types and Models:**
- SQLAlchemy models: `PascalCase`, inherit from `Base` (e.g., `Memory`, `Fact`, `ExtractedEntity`)
- Table names: `snake_case` (e.g., `__tablename__ = "memories"`)
- Pydantic settings: `PascalCase` (e.g., `Settings` class in `config.py`)

## Code Style

**Formatting:**
- No explicit formatter configured (not Black, not isort)
- 4-space indentation (Python standard)
- Line length: Not enforced by configuration, but observe practical limits

**Linting:**
- No linter configured in pyproject.toml
- No explicit lint rules defined
- Relies on IDE/editor conventions and manual review

**Docstrings:**
- Module level: Use triple-quoted strings with description (e.g., `"""Module description - what this module does."""`)
- Class level: Document class purpose and key responsibilities
  ```python
  class Memory(Base):
      """
      A memory is any piece of information the AI should remember.

      Categories:
      - decision: An architectural or design choice (episodic - decays)
      - pattern: A recurring approach that should be followed (semantic - permanent)
      ...
      """
  ```
- Function level: Use docstrings with Args, Returns sections for public functions
  ```python
  def _normalize_file_path(file_path: Optional[str], project_path: str) -> Tuple[Optional[str], Optional[str]]:
      """
      Normalize a file path to both absolute and project-relative forms.

      On Windows, also case-folds for consistent matching.

      Args:
          file_path: The file path to normalize (can be absolute or relative)
          project_path: The project root path

      Returns:
          Tuple of (absolute_path, relative_path)
          Returns (None, None) if file_path is empty
      """
  ```

## Import Organization

**Order:**
1. Standard library imports (e.g., `import os`, `import sys`, `from typing import ...`)
2. Third-party imports (e.g., `from sqlalchemy import ...`, `from pydantic_settings import ...`)
3. Local imports (e.g., `from .database import DatabaseManager`, `from . import vectors`)

**Pattern:**
```python
import sys
import os
import re
import logging
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy import select, or_, func
from sqlalchemy.orm import DeclarativeBase

from .database import DatabaseManager
from .models import Memory
from .config import settings
```

**Path Aliases:**
- Relative imports: Use `.` notation (e.g., `from .database import`, `from . import vectors`)
- Absolute imports: Use module path (e.g., `from daem0nmcp.database import`, `from daem0nmcp.models import`)
- Type hints: Use full module path with imports (e.g., `Optional[DatabaseManager]` after import)

## Error Handling

**Patterns:**
- Custom exceptions: Define domain-specific exceptions for semantic meaning
  - `CovenantViolation` in `covenant.py`: Response object for covenant enforcement violations
  - `ValueError` for parameter/state validation (e.g., raising when required args missing)
  - `RuntimeError` for operation state errors (e.g., "FileWatcher is already running")

- Exception handling: Use try/except with specific exception types
  ```python
  try:
      result = await session.execute(...)
  except ValueError as e:
      logger.warning(f"Migration check failed: {e}")
  ```

- Context managers: Use async context managers for resource cleanup
  ```python
  async with self.db.get_session() as session:
      # Database operations
      pass
  # Automatic cleanup via __aexit__
  ```

- Defensive checks: Return early or raise clear errors
  ```python
  if not file_path:
      return None, None

  if not path.is_absolute():
      path = Path(project_path) / path
  ```

## Logging

**Framework:** Python `logging` module

**Setup:** Structured logging via `StructuredFormatter` in `daem0nmcp/logging_config.py`
- JSON-based log output with timestamp, level, logger name, message
- Request IDs tracked via `ContextVar` for tracing

**Patterns:**
```python
import logging

logger = logging.getLogger(__name__)

# Info for important operations
logger.info(f"Applied {count} migration(s): {applied}")

# Warning for recoverable issues
logger.warning(f"Migration check failed: {e}")

# Debug for detailed flow (uncommon in current codebase)
# logger.debug("Detailed trace information")

# Extra fields for structured logging
logger.info(
    "Tool completed",
    extra={'duration_ms': round(duration_ms, 2), 'tool_name': func.__name__}
)
```

**When to Log:**
- Database operations: Log migrations, schema changes
- Tool execution: Log tool calls with timing via `@with_request_id` decorator
- Errors: Log unexpected conditions, failures, recoverable issues
- State changes: Log significant state transitions

## Comments

**When to Comment:**
- Complex algorithms: Explain the "why" behind non-obvious logic
  - Example: Comments explaining Windows path case-folding in `_normalize_file_path`
  - Example: Comments explaining memory decay calculations

- Database PRAGMAs: Document configuration purpose
  ```python
  # WAL mode for better concurrent access
  cursor.execute("PRAGMA journal_mode=WAL")
  ```

- Non-obvious business logic: Explain domain concepts
  ```python
  # Semantic memories (patterns, warnings) don't decay - they're project facts.
  # Episodic memories (decisions, learnings) decay over time.
  ```

**Avoid:**
- Obvious comments ("x = 1  # set x to 1")
- Comments that restate code
- Outdated comments (keep updated or remove)

## Function Design

**Size:** Functions range from 5-50 lines typically
- Aim for single responsibility
- Example: `_normalize_file_path` (20 lines) - single concern: path normalization
- Example: `extract_keywords` (variable) - variable by content extraction complexity

**Parameters:**
- Use type hints always (e.g., `file_path: Optional[str]`)
- Default values for optional parameters
  ```python
  async def process_memory(
      self,
      memory_id: int,
      content: str,
      project_path: str,
      rationale: Optional[str] = None
  ) -> Dict[str, Any]:
  ```

**Return Values:**
- Explicit return types in signature (e.g., `-> Tuple[Optional[str], Optional[str]]`)
- Dict returns for API responses with typed values
- None for operations with side effects only

**Error Propagation:**
- Let exceptions bubble up for critical errors
- Catch and log at appropriate boundaries (database operations, API calls)
- Return default/empty values for non-critical failures (e.g., return empty list if search fails)

## Module Design

**Exports:**
- Use `__all__` in modules with public API (uncommon in current codebase)
- Public functions/classes: Documented, clear purpose
- Private functions: Prefixed with underscore, not meant for external use

**Module Organization:**
- Constants at module top (e.g., `VALID_RELATIONSHIPS`, `FAILED_DECISION_BOOST`)
- Logger setup near top (e.g., `logger = logging.getLogger(__name__)`)
- Class definitions
- Function definitions
- Helper functions after main code

**Example from `memory.py`:**
```python
# Imports
from .database import DatabaseManager

# Constants
VALID_RELATIONSHIPS = frozenset({...})

# Logger
logger = logging.getLogger(__name__)

# Helper functions
def _normalize_file_path(...):
    ...

# Main classes
class MemoryManager:
    ...
```

**Barrel Files:**
- Not used in current codebase
- Prefer explicit imports from specific modules

## Type Hints

**Requirements:**
- Function parameters: Always include type hints
- Function returns: Always include return type hint
- Variables: Use type hints for clarity, especially for complex types

**Patterns:**
```python
# Optional types
file_path: Optional[str] = None
rationale: Optional[str] = None

# Collections with item types
keywords: List[str]
context: Dict[str, Any]
tags: List[str]

# Tuples with specific types
-> Tuple[Optional[str], Optional[str]]

# Union types
-> Union[Dict, List]

# Async functions
async def remember(...) -> Dict[str, Any]:
```

## Async/Await Patterns

**Usage:** Async functions for I/O-bound operations (database, API calls)

**Pattern:**
```python
async def remember(
    self,
    category: str,
    content: str,
    ...
) -> Dict[str, Any]:
    """Store a memory."""
    async with self.db.get_session() as session:
        # Perform async database operations
        result = await session.execute(select(...))
        ...
        await session.commit()
        return result_dict

# Calling async functions
result = await memory_manager.remember(...)

# In fixtures
@pytest.fixture
async def memory_manager(temp_storage):
    """Create a memory manager."""
    db = DatabaseManager(temp_storage)
    await db.init_db()
    manager = MemoryManager(db)
    yield manager
    await db.close()
```

## Configuration

**Style:** Pydantic `BaseSettings` with environment variable prefix

**Pattern:**
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Daem0nMCP configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="DAEM0NMCP_",
        env_file=".env",
        env_file_encoding="utf-8"
    )

    # Settings with Field() for validation
    max_content_size: int = 1_000_000
    log_level: str = "INFO"
    hybrid_vector_weight: float = Field(default=0.3, ge=0.0, le=1.0)
```

**Accessing:** Via `from .config import settings` singleton

---

*Convention analysis: 2026-01-22*
