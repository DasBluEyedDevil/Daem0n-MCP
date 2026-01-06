# Implementation Plan: Iteration 3 - Impact Analysis + Watcher Refinement

**Date:** 2026-01-06
**Estimated Effort:** 16-20 hours
**Dependencies:** Partial dependency on Iteration 2 (for full analyze_impact value)

---

## Executive Summary

This iteration focuses on two interconnected improvements:

1. **Incremental Indexing** - Track file content hashes to avoid re-parsing unchanged files
2. **Watcher-Triggered Re-indexing** - Selectively re-index changed files
3. **Enhanced analyze_impact** - Add risk assessment and suggested checks

The key insight is that incremental indexing is independent of Iteration 2, while analyze_impact delivers maximum value only after Iteration 2 populates calls/imports.

---

## Current State Analysis

### 1. analyze_impact is Nearly Useless

```python
# code_indexer.py:838-918 - searches empty lists
for other in all_entities:
    calls = other.calls or []      # Always empty
    imports = other.imports or []  # Always empty

    if entity_name in calls or entity_name in imports:
        affected.append(...)  # Never triggered
```

### 2. No Incremental Indexing

```python
# code_indexer.py - every index_project() re-parses ALL files
async def index_project(self, project_path, patterns):
    for file_path in project.glob(pattern):
        for entity in self.indexer.index_file(file_path, project):
            entities.append(entity)

    # Deletes ALL existing entities
    await session.execute(delete(CodeEntity).where(...))
```

### 3. Watcher Doesn't Trigger Re-indexing

```python
# watcher.py:510-565 - only queries memories
async def _handle_change(self, file_path):
    result = await self._memory_manager.recall_for_file(...)
    # No call to re-index
```

---

## Phase 1: File Hash Infrastructure (2-3 hours)

### 1.1 Create FileHash Model

**File:** `daem0nmcp/models.py`

```python
class FileHash(Base):
    """Tracks content hashes for indexed files."""
    __tablename__ = "file_hashes"

    id = Column(Integer, primary_key=True, index=True)
    project_path = Column(String, nullable=False, index=True)
    file_path = Column(String, nullable=False)  # Relative to project
    content_hash = Column(String(64), nullable=False)  # SHA256
    indexed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint('project_path', 'file_path', name='uix_file_project'),
    )
```

### 1.2 Add Migration

**File:** `daem0nmcp/migrations/schema.py`

```python
(11, "Add file_hashes table for incremental indexing", [
    """
    CREATE TABLE IF NOT EXISTS file_hashes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_path TEXT NOT NULL,
        file_path TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(project_path, file_path)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_file_hashes_project ON file_hashes(project_path);",
]),
```

---

## Phase 2: Incremental Indexing (6-8 hours)

### 2.1 Add Hash Computation

**File:** `daem0nmcp/code_indexer.py`

```python
def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of file content."""
    content = file_path.read_bytes()
    return hashlib.sha256(content).hexdigest()
```

### 2.2 Add Single-File Indexing Method

```python
async def index_file_if_changed(
    self,
    file_path: Path,
    project_path: Path,
    force: bool = False
) -> Dict[str, Any]:
    """
    Index a single file only if its content has changed.

    Returns:
        Dict with changed, entities_count, file_path
    """
    if file_path.suffix.lower() not in LANGUAGE_CONFIG:
        return {'changed': False, 'reason': 'unsupported_extension'}

    if self._should_skip(file_path):
        return {'changed': False, 'reason': 'excluded_directory'}

    try:
        rel_path = str(file_path.relative_to(project_path))
    except ValueError:
        rel_path = str(file_path)

    project_str = str(project_path.resolve())

    # Compute current hash
    try:
        current_hash = compute_file_hash(file_path)
    except (OSError, IOError) as e:
        return {'changed': False, 'error': str(e)}

    # Check stored hash
    if not force:
        stored_hash = await self._get_stored_hash(project_str, rel_path)
        if stored_hash == current_hash:
            return {'changed': False, 'reason': 'unchanged'}

    # Re-index
    entities = list(self.indexer.index_file(file_path, project_path))

    if self.db is not None:
        await self._store_file_entities(entities, project_str, rel_path, current_hash)

    if self.qdrant is not None:
        await self._index_in_qdrant(entities)

    return {'changed': True, 'entities_count': len(entities)}
```

### 2.3 Add Incremental Project Index

```python
async def index_project_incremental(
    self,
    project_path: str,
    patterns: Optional[List[str]] = None,
    force: bool = False
) -> Dict[str, Any]:
    """Index project incrementally - only re-parse changed files."""
    project = Path(project_path).resolve()
    patterns = patterns or self.DEFAULT_PATTERNS

    stats = {
        'files_checked': 0,
        'files_changed': 0,
        'files_unchanged': 0,
        'entities_indexed': 0,
    }

    for pattern in patterns:
        for file_path in project.glob(pattern):
            if self._should_skip(file_path) or not file_path.is_file():
                continue

            stats['files_checked'] += 1

            result = await self.index_file_if_changed(file_path, project, force=force)

            if result.get('changed'):
                stats['files_changed'] += 1
                stats['entities_indexed'] += result.get('entities_count', 0)
            elif result.get('reason') == 'unchanged':
                stats['files_unchanged'] += 1

    # Cleanup deleted files
    if self.db is not None:
        await self._cleanup_deleted_files(str(project))

    return stats
```

### 2.4 Store File Entities Method

```python
async def _store_file_entities(
    self,
    entities: List[Dict],
    project_path: str,
    file_path: str,
    content_hash: str
) -> None:
    """Store entities for a single file, replacing existing."""
    from .models import CodeEntity, FileHash
    from sqlalchemy import delete, and_

    async with self.db.get_session() as session:
        # Delete existing entities for this file only
        await session.execute(
            delete(CodeEntity).where(
                and_(
                    CodeEntity.project_path == project_path,
                    CodeEntity.file_path == file_path
                )
            )
        )

        # Insert new entities
        for entity_dict in entities:
            entity = CodeEntity(**entity_dict)
            session.add(entity)

        # Update file hash (upsert)
        await self._update_stored_hash(session, project_path, file_path, content_hash)

        await session.commit()
```

---

## Phase 3: Watcher Integration (3-4 hours)

### 3.1 Add CodeIndexManager to FileWatcher

**File:** `daem0nmcp/watcher.py`

```python
def __init__(
    self,
    project_path: Path,
    memory_manager: Any,
    channels: List[NotificationChannel],
    config: Optional[WatcherConfig] = None,
    code_index: Optional[Any] = None  # NEW
):
    self._project_path = project_path.resolve()
    self._memory_manager = memory_manager
    self._channels = channels
    self._config = config or WatcherConfig()
    self._code_index = code_index  # NEW

    self._stats = {
        "files_changed": 0,
        "notifications_sent": 0,
        "files_reindexed": 0,  # NEW
        "errors": 0,
    }
```

### 3.2 Modify _handle_change

```python
async def _handle_change(self, file_path: Path) -> None:
    """Re-index changed file and check for memories."""
    try:
        # Step 1: Re-index the changed file
        if self._code_index is not None:
            try:
                index_result = await self._code_index.index_file_if_changed(
                    file_path, self._project_path
                )
                if index_result.get('changed'):
                    self._stats["files_reindexed"] += 1
            except Exception as e:
                logger.warning(f"Re-indexing failed for {file_path}: {e}")

        # Step 2: Query memories (existing behavior)
        result = await self._memory_manager.recall_for_file(
            file_path=str(file_path),
            project_path=str(self._project_path),
            limit=20
        )

        # Continue with notifications...
```

---

## Phase 4: Enhanced analyze_impact (4-6 hours)

### 4.1 Add Risk Assessment

**File:** `daem0nmcp/code_indexer.py`

```python
async def analyze_impact(self, entity_name: str, project_path: Optional[str] = None):
    """Analyze impact with risk assessment and suggestions."""
    # ... existing lookup code ...

    # Find affected entities
    affected = []
    affected_files = set()

    for other in all_entities:
        if other.id == entity.id:
            continue

        calls = other.calls or []
        imports = other.imports or []
        inherits = other.inherits or []

        relationship = None
        if entity_name in calls:
            relationship = 'calls'
        elif entity_name in imports:
            relationship = 'imports'
        elif entity_name in inherits:
            relationship = 'inherits'

        if relationship:
            affected.append({
                'name': other.name,
                'type': other.entity_type,
                'file': other.file_path,
                'relationship': relationship,
            })
            affected_files.add(other.file_path)

    # Calculate risk level
    risk_level = self._calculate_risk_level(entity, len(affected), affected_files)

    # Generate suggestions
    suggested_checks = self._generate_suggested_checks(
        entity, affected, affected_files, risk_level
    )

    return {
        'entity': entity_name,
        'found': True,
        'risk_level': risk_level,
        'suggested_checks': suggested_checks,
        'affected_files': list(affected_files),
        'affected_entities': affected,
        'affected_count': len(affected),
    }


def _calculate_risk_level(self, entity, affected_count: int, affected_files: set) -> str:
    """Calculate risk based on entity type and impact scope."""
    score = 0

    type_weights = {'class': 3, 'interface': 3, 'function': 2, 'method': 1}
    score += type_weights.get(entity.entity_type, 1)

    if len(affected_files) > 10:
        score += 4
    elif len(affected_files) > 5:
        score += 2

    if affected_count > 20:
        score += 4
    elif affected_count > 10:
        score += 2

    if score >= 8:
        return 'high'
    elif score >= 4:
        return 'medium'
    return 'low'


def _generate_suggested_checks(self, entity, affected, affected_files, risk_level) -> List[str]:
    """Generate actionable testing suggestions."""
    checks = [f"Test {entity.file_path} directly"]

    if risk_level == 'high':
        checks.append("Run full test suite before committing")

    for file_path in list(affected_files)[:5]:
        if file_path != entity.file_path:
            checks.append(f"Test {file_path}")

    if not affected:
        checks.append("Note: Run `daem0n index` for full dependency tracking")

    return checks
```

---

## Phase 5: Configuration (1-2 hours)

**File:** `daem0nmcp/config.py`

```python
# Code Indexing
index_incremental: bool = True  # Use incremental indexing by default
index_cleanup_deleted: bool = True  # Remove entries for deleted files
index_on_file_change: bool = True  # Re-index when watcher detects changes
```

---

## Test Cases

### Test Incremental Indexing

```python
class TestIndexFileIfChanged:
    @pytest.mark.asyncio
    async def test_first_index_marks_changed(self, temp_project_with_db):
        ctx = temp_project_with_db
        result = await ctx['indexer'].index_file_if_changed(
            ctx['project'] / "main.py", ctx['project']
        )
        assert result['changed'] is True

    @pytest.mark.asyncio
    async def test_unchanged_file_not_reindexed(self, temp_project_with_db):
        ctx = temp_project_with_db
        main_py = ctx['project'] / "main.py"

        await ctx['indexer'].index_file_if_changed(main_py, ctx['project'])
        result = await ctx['indexer'].index_file_if_changed(main_py, ctx['project'])

        assert result['changed'] is False
        assert result['reason'] == 'unchanged'

    @pytest.mark.asyncio
    async def test_modified_file_reindexed(self, temp_project_with_db):
        ctx = temp_project_with_db
        main_py = ctx['project'] / "main.py"

        await ctx['indexer'].index_file_if_changed(main_py, ctx['project'])
        main_py.write_text('class NewClass: pass')
        result = await ctx['indexer'].index_file_if_changed(main_py, ctx['project'])

        assert result['changed'] is True
```

### Test Enhanced analyze_impact

```python
class TestAnalyzeImpact:
    @pytest.mark.asyncio
    async def test_impact_returns_risk_level(self, indexed_project):
        result = await indexed_project['indexer'].analyze_impact('User')

        assert result['found'] is True
        assert result['risk_level'] in ('low', 'medium', 'high')
        assert 'suggested_checks' in result
```

---

## Performance Expectations

| Scenario | Before | After |
|----------|--------|-------|
| Initial full index (1000 files) | ~30s | ~30s |
| Re-index unchanged project | ~30s | **<1s** |
| Single file change + watcher | N/A | ~50ms |

---

## Dependencies

### Independent of Iteration 2:
- FileHash model and migration
- index_file_if_changed()
- index_project_incremental()
- Watcher integration

### Dependent on Iteration 2:
- analyze_impact enhancements (returns empty results until imports populated)
