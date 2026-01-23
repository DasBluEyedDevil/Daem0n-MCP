# Testing Patterns

**Analysis Date:** 2026-01-22

## Test Framework

**Runner:**
- pytest 7.0.0+
- Config: `pytest.ini` and `pyproject.toml [tool.pytest.ini_options]`

**Async Testing:**
- pytest-asyncio 0.23.0+
- Asyncio mode: `auto`
- Default loop scope: `function` (fresh event loop per test)

**Assertion Library:**
- Python `assert` statements (built-in)
- No custom assertion helpers defined

**Run Commands:**
```bash
pytest                                    # Run all tests
pytest tests/test_memory.py               # Run specific test file
pytest tests/test_memory.py::TestMemoryManager  # Run specific test class
pytest -v                                 # Verbose output
pytest -x                                 # Stop on first failure
pytest -k "test_remember"                 # Run tests matching pattern
pytest --asyncio-mode=auto                # Explicit async mode
```

**Coverage:**
- Not configured in pyproject.toml
- No coverage requirements enforced

## Test File Organization

**Location:**
- Separate from source: `tests/` directory at project root
- Mirrors source structure conceptually but is flat
- Files prefixed with `test_`

**Naming:**
- File: `test_*.py` (e.g., `test_memory.py`, `test_covenant.py`)
- Class: `Test*` (e.g., `TestMemoryManager`, `TestCovenantViolation`)
- Function: `test_*` (e.g., `test_remember_decision`, `test_communion_required_response`)

**Example from `tests/test_memory.py`:**
```
tests/
├── test_memory.py
│   ├── TestExtractKeywords
│   │   ├── test_basic_extraction()
│   │   ├── test_with_tags()
│   │   └── ...
│   └── TestMemoryManager
│       ├── test_remember_decision()
│       ├── test_remember_warning()
│       └── ...
```

**Test Count:** 635 test functions across 54 test files
- Comprehensive coverage of core functionality
- Integration tests included

## Test Structure

**Suite Organization:**

Classes group related tests by functionality:

```python
class TestExtractKeywords:
    """Test keyword extraction."""

    def test_basic_extraction(self):
        text = "Use JWT tokens for authentication"
        keywords = extract_keywords(text)
        assert "jwt" in keywords
        assert "tokens" in keywords

    def test_with_tags(self):
        text = "Add rate limiting"
        tags = ["api", "security"]
        keywords = extract_keywords(text, tags)
        assert "api" in keywords
```

Fixtures create reusable test resources:

```python
@pytest.fixture
async def memory_manager(temp_storage):
    """Create a memory manager with temporary storage."""
    db = DatabaseManager(temp_storage)
    await db.init_db()
    manager = MemoryManager(db)
    yield manager
    # Cleanup
    if manager._qdrant:
        manager._qdrant.close()
    await db.close()
```

**Patterns:**

Setup fixtures use `@pytest.fixture` decorator:
```python
@pytest.fixture
def temp_storage():
    """Create a temporary storage directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)
```

Teardown via `yield` - code after yield runs after test:
```python
@pytest.fixture
async def memory_manager(temp_storage):
    db = DatabaseManager(temp_storage)
    await db.init_db()
    manager = MemoryManager(db)
    yield manager  # Test uses manager
    # Cleanup after test
    await db.close()
```

Async test functions marked with `@pytest.mark.asyncio`:
```python
@pytest.mark.asyncio
async def test_remember_decision(self, memory_manager):
    """Test storing a decision."""
    result = await memory_manager.remember(
        category="decision",
        content="Use PostgreSQL instead of MySQL",
        rationale="Better JSON support and performance",
        tags=["database", "architecture"]
    )
    assert "id" in result
    assert result["category"] == "decision"
```

## Fixtures and Factories

**Built-in Test Fixtures:**

**conftest.py** (`tests/conftest.py`) provides global fixtures:

```python
# Safe temporary directory (Windows-compatible)
@pytest.fixture
def tmp_path(tmp_path_factory):
    """Override tmp_path to use our safe temp root."""
    path = Path(_safe_mkdtemp(prefix="pytest_"))
    yield path
    shutil.rmtree(path, ignore_errors=True)
```

**Covenant Compliance Fixture:**
```python
@pytest.fixture
async def covenant_compliant_project(tmp_path):
    """
    Fixture that creates a project and ensures covenant compliance.

    Returns the project path that can be used with tools requiring
    communion and/or counsel.
    """
    from daem0nmcp.database import DatabaseManager
    from daem0nmcp import server

    project_path = str(tmp_path)
    storage_path = str(tmp_path / "storage")

    db_manager = DatabaseManager(storage_path)
    await db_manager.init_db()

    server._project_contexts.clear()

    await ensure_covenant_compliance(project_path)

    yield project_path

    await db_manager.close()
```

**Test Data Fixtures:**

Memory manager fixture creates database with pre-initialized state:
```python
@pytest.fixture
async def memory_manager(temp_storage):
    """Create a memory manager with temporary storage."""
    db = DatabaseManager(temp_storage)
    await db.init_db()
    manager = MemoryManager(db)
    yield manager
    if manager._qdrant:
        manager._qdrant.close()
    await db.close()
```

Temporary directories:
```python
@pytest.fixture
def temp_project():
    """Create a temporary project directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)
```

## Mocking

**Framework:** `unittest.mock` (Python standard library)

**Patterns:**

Basic mocking with `patch` decorator:
```python
from unittest.mock import patch

@patch('module.function')
def test_something(mock_func):
    mock_func.return_value = "mocked"
    result = function_under_test()
    assert result == "mocked"
```

Mock with context manager:
```python
with patch('module.function') as mock_func:
    mock_func.return_value = "test"
    # Test code using mocked function
    assert mock_func.called
```

From `test_covenant.py` - mocking datetime:
```python
from unittest.mock import patch

@patch('module.datetime')
def test_token_expiry(mock_datetime):
    # Manually expire token by setting datetime
    token.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert token.is_expired()
```

**What to Mock:**
- External services (APIs, databases when using real instances in other tests)
- Time-dependent functions (datetime.now() for time-based tests)
- File I/O when testing logic independent of filesystem
- System calls (subprocess, os.system)

**What NOT to Mock:**
- The actual functionality being tested
- Database operations in integration tests (use real DatabaseManager)
- Core business logic (memory storage, retrieval)
- Type validation and schema checks

## Test Types

**Unit Tests:**
- Scope: Single function/class in isolation
- Example: `test_basic_extraction()` - tests `extract_keywords()` function alone
- Approach: Direct function calls, simple inputs/assertions
- Fixture use: Minimal, use test data directly
- Location: `test_*.py` files

```python
def test_basic_extraction(self):
    """Test keyword extraction."""
    text = "Use JWT tokens for authentication"
    keywords = extract_keywords(text)
    assert "jwt" in keywords
    assert "tokens" in keywords
    assert "for" not in keywords  # Stop words removed
```

**Integration Tests:**
- Scope: Multiple components working together
- Example: `test_remember_decision()` - tests MemoryManager with real DatabaseManager
- Approach: Use real fixtures (DatabaseManager), test through public API
- Fixture use: Heavy - use `memory_manager`, `temp_storage` fixtures
- Location: Same `test_*.py` files, often async

```python
@pytest.mark.asyncio
async def test_remember_decision(self, memory_manager):
    """Test storing a decision."""
    result = await memory_manager.remember(
        category="decision",
        content="Use PostgreSQL instead of MySQL",
        rationale="Better JSON support and performance",
        tags=["database", "architecture"]
    )
    assert "id" in result
    assert result["category"] == "decision"
    assert "database" in result["tags"]
```

**E2E Tests:**
- Framework: CLI subprocess testing
- Example: `test_cli.py` - runs daem0nmcp CLI as subprocess
- Approach: Launch process, check stdout/stderr/return code
- Fixture use: Temporary project directory, environment setup

```python
def test_briefing_json_output(self, temp_project):
    """Test briefing command with JSON output."""
    result = run_cli("--json", "briefing", project_path=temp_project)
    assert result.returncode == 0

    data = json.loads(result.stdout)
    assert "total_memories" in data
    assert "by_category" in data
```

## Common Patterns

**Async Testing:**

Use `@pytest.mark.asyncio` decorator:
```python
@pytest.mark.asyncio
async def test_remember_decision(self, memory_manager):
    """Test storing a decision."""
    result = await memory_manager.remember(
        category="decision",
        content="Use PostgreSQL instead of MySQL",
    )
    assert "id" in result
```

Async fixtures with `yield`:
```python
@pytest.fixture
async def memory_manager(temp_storage):
    db = DatabaseManager(temp_storage)
    await db.init_db()
    manager = MemoryManager(db)
    yield manager  # Test runs here
    await db.close()  # Cleanup after
```

**Error Testing:**

Test invalid input rejection:
```python
@pytest.mark.asyncio
async def test_remember_invalid_category(self, memory_manager):
    """Test that invalid categories are rejected."""
    result = await memory_manager.remember(
        category="invalid",
        content="This should fail"
    )
    # Expect error in result or exception raised
```

Test expected exceptions:
```python
def test_token_tamper_detection(self):
    """Tampered token should fail verification."""
    token = PreflightToken.issue(...)
    serialized = token.serialize()

    # Tamper with token
    tampered = serialized[:-5] + "xxxxx"

    verified = PreflightToken.verify(tampered, project_path="/test")
    assert verified is None  # Should fail verification
```

**Database Testing:**

Verify SQLite PRAGMA settings:
```python
@pytest.mark.asyncio
async def test_wal_mode_enabled(self):
    """Verify WAL mode is enabled."""
    from daem0nmcp.database import DatabaseManager
    from sqlalchemy import text

    with tempfile.TemporaryDirectory() as temp_dir:
        db = DatabaseManager(temp_dir)
        await db.init_db()

        async with db.get_session() as session:
            result = await session.execute(text("PRAGMA journal_mode"))
            mode = result.scalar()
            assert mode.lower() == "wal"

        await db.close()
```

**CLI Testing:**

Launch subprocess and check output:
```python
def run_cli(*args, env=None, project_path=None):
    """Run CLI command and return result."""
    cmd = [sys.executable, "-m", "daem0nmcp.cli"]
    if project_path:
        cmd.extend(["--project-path", project_path])
    cmd.extend(args)

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        env=env
    )
    stdout, stderr = process.communicate()
    return subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)

def test_briefing_json_output(self, temp_project):
    """Test briefing command with JSON output."""
    result = run_cli("--json", "briefing", project_path=temp_project)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "total_memories" in data
```

## Test Configuration

**conftest.py Customizations:**

Windows compatibility for temporary directories:
```python
# Override tempfile helpers to avoid restricted temp directories on Windows
SAFE_TMP_ROOT = Path(__file__).resolve().parent.parent / ".test_tmp"

tempfile.tempdir = str(SAFE_TMP_ROOT)
tempfile.mkdtemp = _safe_mkdtemp  # Custom implementation
tempfile.TemporaryDirectory = _SafeTemporaryDirectory  # Custom class
os.environ["GIT_CEILING_DIRECTORIES"] = str(SAFE_TMP_ROOT)
```

Custom pytest hooks:
```python
def pytest_configure(config):
    """Configure custom pytest markers and ensure tmp directories exist."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as an asyncio test."
    )
```

**pyproject.toml Configuration:**

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
```

## Key Test Files by Category

**Memory System:**
- `test_memory.py` - Memory storage and retrieval
- `test_search_quality.py` - Search and ranking
- `test_temporal.py` - Time-based decay and recall
- `test_similarity.py` - Similarity calculations

**Covenant/Enforcement:**
- `test_covenant.py` - Sacred Covenant violations and preflight tokens
- `test_covenant_integration.py` - Covenant flow with tools
- `test_covenant_transform.py` - Request/response transformation
- `test_enforcement.py` - Tool enforcement rules

**Code Analysis:**
- `test_code_indexer.py` - Code entity extraction
- `test_code_entity_fidelity.py` - Entity extraction accuracy
- `test_entity_extraction.py` - Entity recognition patterns

**Integration:**
- `test_bootstrap.py` - Project bootstrap flow
- `test_hybrid_integration.py` - Vector + BM25 hybrid search
- `test_incremental_indexing.py` - Incremental index updates

**CLI:**
- `test_cli.py` - Command-line interface
- `test_scanner.py` - TODO/FIXME scanner

**Database:**
- `test_database.py` - SQLite configuration and pragmas
- `test_migrations.py` - Schema migrations

## Coverage Strategy

**Not Enforced:** No coverage targets configured

**Areas with High Test Density:**
- Memory operations (remember, recall, search)
- Covenant enforcement (violations, preflight tokens)
- Database operations (pragmas, session management)
- Entity extraction (code understanding)

**How to Add Tests:**
1. Create `test_*.py` file in `tests/` directory
2. Use `TestClassName` for test classes
3. Use `test_function_name()` for test functions
4. Mark async tests with `@pytest.mark.asyncio`
5. Use fixtures from `conftest.py` or define locally
6. Follow AAA pattern: Arrange, Act, Assert

---

*Testing analysis: 2026-01-22*
