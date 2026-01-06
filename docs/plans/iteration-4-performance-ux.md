# Implementation Plan: Iteration 4 - Performance & UX Polish

**Date:** 2026-01-06
**Estimated Effort:** 11-15 hours
**Dependencies:** None (can run in parallel with other iterations)

---

## Executive Summary

This iteration focuses on performance optimizations and user experience improvements:

1. **Parse tree caching** - Avoid re-parsing unchanged files
2. **Config centralization** - Add all tunable parameters in one place
3. **Enhanced status command** - Comprehensive diagnostic output
4. **Health tool improvements** - Index freshness and config validation

---

## 1. Parse Tree Caching

### Current State

The `TreeSitterIndexer` re-parses every file on each call:

```python
# code_indexer.py:226-231
source = file_path.read_bytes()
parser, language = self.get_parser(lang)
tree = parser.parse(source)  # No caching
```

### Implementation

#### 1.1 Add Cache to TreeSitterIndexer

**File:** `daem0nmcp/code_indexer.py`

```python
def __init__(self):
    self._parsers: Dict[str, Any] = {}
    self._languages: Dict[str, Any] = {}
    self._available = _check_tree_sitter_available()
    # NEW: Parse tree cache
    self._parse_cache: Dict[str, Tuple[str, Any]] = {}  # path -> (hash, tree)
    self._cache_maxsize: int = 200
    self._cache_hits: int = 0
    self._cache_misses: int = 0
```

#### 1.2 Add Caching Method

```python
def _get_cached_tree(self, file_path: Path, source: bytes, lang: str):
    """Get parse tree from cache or parse and cache."""
    import hashlib

    content_hash = hashlib.md5(source).hexdigest()
    cache_key = str(file_path)

    # Check cache
    if cache_key in self._parse_cache:
        cached_hash, cached_tree = self._parse_cache[cache_key]
        if cached_hash == content_hash:
            self._cache_hits += 1
            return cached_tree

    # Cache miss - parse
    self._cache_misses += 1
    parser, language = self.get_parser(lang)
    if parser is None:
        return None

    tree = parser.parse(source)

    # Evict oldest if at capacity
    if len(self._parse_cache) >= self._cache_maxsize:
        oldest_key = next(iter(self._parse_cache))
        del self._parse_cache[oldest_key]

    self._parse_cache[cache_key] = (content_hash, tree)
    return tree

@property
def cache_stats(self) -> Dict[str, Any]:
    """Return cache statistics."""
    total = self._cache_hits + self._cache_misses
    return {
        "size": len(self._parse_cache),
        "maxsize": self._cache_maxsize,
        "hits": self._cache_hits,
        "misses": self._cache_misses,
        "hit_rate": self._cache_hits / total if total > 0 else 0.0
    }

def clear_cache(self) -> int:
    """Clear the parse tree cache."""
    count = len(self._parse_cache)
    self._parse_cache.clear()
    return count
```

#### 1.3 Modify index_file() to Use Cache

```python
def index_file(self, file_path: Path, project_path: Path):
    # ... existing code ...

    try:
        source = file_path.read_bytes()
        parser, language = self.get_parser(lang)
        if parser is None or language is None:
            return

        # Use cached tree if available
        tree = self._get_cached_tree(file_path, source, lang)
        if tree is None:
            return
    except Exception as e:
        logger.debug(f"Failed to parse {file_path}: {e}")
        return
    # ... rest unchanged
```

---

## 2. Config Centralization

### New Config Options

**File:** `daem0nmcp/config.py`

Add to `Settings` class:

```python
# --- Search Tuning ---
hybrid_vector_weight: float = 0.3  # 0.0 = TF-IDF only, 1.0 = vectors only
search_diversity_max_per_file: int = 3  # Max results from same file
search_default_limit: int = 20
search_tfidf_threshold: float = 0.1
search_vector_threshold: float = 0.3

# --- Code Indexing ---
index_languages: List[str] = []  # Empty = all supported
index_skip_patterns: List[str] = []
parse_tree_cache_maxsize: int = 200

# --- Embedding Model ---
embedding_model: str = "all-MiniLM-L6-v2"
```

### Add Validation

```python
from pydantic import field_validator

@field_validator('hybrid_vector_weight')
@classmethod
def validate_hybrid_weight(cls, v):
    if not 0.0 <= v <= 1.0:
        raise ValueError(f'hybrid_vector_weight must be 0.0-1.0, got {v}')
    return v

@field_validator('search_default_limit', 'search_diversity_max_per_file')
@classmethod
def validate_positive_int(cls, v):
    if v < 1:
        raise ValueError(f'Value must be >= 1, got {v}')
    return v

def get_config_warnings(self) -> List[str]:
    """Return warnings about config that may cause issues."""
    warnings = []

    if self.hybrid_vector_weight == 0.0:
        warnings.append("hybrid_vector_weight=0.0: Using TF-IDF only")
    elif self.hybrid_vector_weight == 1.0:
        warnings.append("hybrid_vector_weight=1.0: Using vectors only")

    if self.parse_tree_cache_maxsize > 1000:
        warnings.append(f"Large cache may use significant memory")

    return warnings
```

### Update References

**memory.py:**
```python
vector_weight = settings.hybrid_vector_weight  # Was hardcoded 0.3
```

**vectors.py:**
```python
def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        from .config import settings
        _model = SentenceTransformer(settings.embedding_model)
    return _model

# In HybridSearch.__init__
self.vector_weight = settings.hybrid_vector_weight
```

---

## 3. Enhanced CLI Status Command

### Implementation

**File:** `daem0nmcp/cli.py`

```python
async def get_comprehensive_status(db, memory, project_path: str) -> dict:
    """Get comprehensive status including code entities and config."""
    from sqlalchemy import select, func
    from .models import Memory, CodeEntity, Rule
    from .config import settings

    await db.init_db()

    status = {
        "project_path": project_path,
        "storage_path": settings.get_storage_path(),
    }

    async with db.get_session() as session:
        # Memory counts by category
        result = await session.execute(
            select(Memory.category, func.count(Memory.id))
            .group_by(Memory.category)
        )
        status["memories"] = {
            "total": 0,
            "by_category": {row[0]: row[1] for row in result.all()},
        }
        status["memories"]["total"] = sum(status["memories"]["by_category"].values())

        # Pending decisions
        result = await session.execute(
            select(func.count(Memory.id))
            .where(Memory.category == "decision", Memory.outcome.is_(None))
        )
        status["memories"]["pending_decisions"] = result.scalar() or 0

        # Code entities
        result = await session.execute(select(func.count(CodeEntity.id)))
        status["code_entities"] = {"total": result.scalar() or 0}

        # Entity types
        result = await session.execute(
            select(CodeEntity.entity_type, func.count(CodeEntity.id))
            .group_by(CodeEntity.entity_type)
        )
        status["code_entities"]["by_type"] = {row[0]: row[1] for row in result.all()}

        # Last index time
        result = await session.execute(select(func.max(CodeEntity.indexed_at)))
        last_indexed = result.scalar()
        status["code_entities"]["last_indexed_at"] = (
            last_indexed.isoformat() if last_indexed else None
        )

        # Rules
        result = await session.execute(select(func.count(Rule.id)))
        status["rules"] = {"total": result.scalar() or 0}

    # Config summary
    status["config"] = {
        "hybrid_vector_weight": settings.hybrid_vector_weight,
        "embedding_model": settings.embedding_model,
        "watcher_enabled": settings.watcher_enabled,
    }

    return status
```

### Enhanced Output

```python
elif args.command == "status":
    result = asyncio.run(get_comprehensive_status(db, memory, project_path))

    if args.json:
        print(json.dumps(result, default=str, indent=2))
    else:
        print(f"Project: {result['project_path']}")
        print(f"Storage: {result['storage_path']}")
        print()

        m = result['memories']
        print(f"MEMORIES: {m['total']} total")
        for cat, count in m['by_category'].items():
            print(f"  {cat}: {count}")
        if m['pending_decisions'] > 0:
            print(f"  [!] {m['pending_decisions']} decisions pending")
        print()

        e = result['code_entities']
        print(f"CODE ENTITIES: {e['total']} indexed")
        if e['total'] > 0:
            for etype, count in e['by_type'].items():
                print(f"  {etype}: {count}")
            if e['last_indexed_at']:
                print(f"  Last indexed: {e['last_indexed_at']}")
        print()

        r = result['rules']
        print(f"RULES: {r['total']} total")
        print()

        c = result['config']
        print("CONFIG:")
        for key, value in c.items():
            print(f"  {key}: {value}")
```

---

## 4. Enhanced Health Tool

### Implementation

**File:** `daem0nmcp/server.py`

```python
@mcp.tool()
async def health(project_path: Optional[str] = None) -> Dict[str, Any]:
    """Get server health, version, and diagnostics."""
    from sqlalchemy import select, func
    from .models import CodeEntity

    ctx = await get_project_context(project_path)
    stats = await ctx.memory_manager.get_statistics()
    rules = await ctx.rules_engine.list_rules(enabled_only=False, limit=1000)

    async with ctx.db_manager.get_session() as session:
        # Entity count
        result = await session.execute(select(func.count(CodeEntity.id)))
        entity_count = result.scalar() or 0

        # Last indexed
        result = await session.execute(select(func.max(CodeEntity.indexed_at)))
        last_indexed = result.scalar()

        # Types breakdown
        result = await session.execute(
            select(CodeEntity.entity_type, func.count(CodeEntity.id))
            .group_by(CodeEntity.entity_type)
        )
        entities_by_type = {row[0]: row[1] for row in result.all()}

    # Index freshness
    index_age_seconds = None
    index_stale = False
    if last_indexed:
        now = datetime.now(timezone.utc)
        if last_indexed.tzinfo is None:
            last_indexed = last_indexed.replace(tzinfo=timezone.utc)
        index_age_seconds = (now - last_indexed).total_seconds()
        index_stale = index_age_seconds > 86400  # 24 hours

    # Cache stats
    cache_stats = None
    try:
        from .code_indexer import TreeSitterIndexer
        indexer = TreeSitterIndexer()
        cache_stats = indexer.cache_stats
    except Exception:
        pass

    # Config warnings
    config_warnings = settings.get_config_warnings()

    return {
        "status": "healthy",
        "version": __version__,
        "project_path": ctx.project_path,

        # Memory stats
        "memories_count": stats.get("total_memories", 0),
        "by_category": stats.get("by_category", {}),

        # Rules
        "rules_count": len(rules),

        # Code index
        "code_entities_count": entity_count,
        "entities_by_type": entities_by_type,
        "last_indexed_at": last_indexed.isoformat() if last_indexed else None,
        "index_age_seconds": index_age_seconds,
        "index_stale": index_stale,

        # Cache
        "parse_cache": cache_stats,

        # Validation
        "config_warnings": config_warnings if config_warnings else None,

        "timestamp": time.time()
    }
```

---

## Test Cases

### Test Parse Tree Cache

```python
class TestParseTreeCache:
    def test_cache_hit_on_unchanged_file(self, temp_project):
        from daem0nmcp.code_indexer import TreeSitterIndexer

        indexer = TreeSitterIndexer()
        py_file = temp_project / "sample.py"
        py_file.write_text("def hello(): pass")

        # First parse - miss
        list(indexer.index_file(py_file, temp_project))
        assert indexer.cache_stats["misses"] == 1

        # Second parse - hit
        list(indexer.index_file(py_file, temp_project))
        assert indexer.cache_stats["hits"] == 1

    def test_cache_invalidation_on_change(self, temp_project):
        indexer = TreeSitterIndexer()
        py_file = temp_project / "sample.py"

        py_file.write_text("def hello(): pass")
        list(indexer.index_file(py_file, temp_project))

        py_file.write_text("def goodbye(): pass")
        list(indexer.index_file(py_file, temp_project))

        assert indexer.cache_stats["misses"] == 2  # Both misses

    def test_cache_eviction(self, temp_project):
        indexer = TreeSitterIndexer()
        indexer._cache_maxsize = 2

        for i in range(3):
            f = temp_project / f"file{i}.py"
            f.write_text(f"def func{i}(): pass")
            list(indexer.index_file(f, temp_project))

        assert indexer.cache_stats["size"] == 2
```

### Test Config Validation

```python
class TestConfigValidation:
    def test_invalid_hybrid_weight_rejected(self):
        from pydantic import ValidationError
        from daem0nmcp.config import Settings

        with pytest.raises(ValidationError):
            Settings(hybrid_vector_weight=1.5)

    def test_config_warnings(self):
        from daem0nmcp.config import Settings

        s = Settings(hybrid_vector_weight=0.0)
        warnings = s.get_config_warnings()
        assert any("TF-IDF only" in w for w in warnings)
```

### Test Enhanced Status

```python
class TestEnhancedStatus:
    @pytest.mark.asyncio
    async def test_status_includes_entities(self, db_and_memory, tmp_path):
        from daem0nmcp.cli import get_comprehensive_status

        db, memory = db_and_memory
        result = await get_comprehensive_status(db, memory, str(tmp_path))

        assert "code_entities" in result
        assert "config" in result
```

### Test Enhanced Health

```python
class TestEnhancedHealth:
    @pytest.mark.asyncio
    async def test_health_includes_index_freshness(self, project):
        from daem0nmcp import server

        result = await server.health(project_path=project)

        assert "last_indexed_at" in result
        assert "index_stale" in result
        assert "parse_cache" in result
```

---

## Implementation Sequence

1. **Phase 1: Config Centralization** (3-4 hours)
   - Add new config options
   - Add validation
   - Update references

2. **Phase 2: Parse Tree Caching** (2-3 hours)
   - Add cache to TreeSitterIndexer
   - Add cache_stats property
   - Update index_file()

3. **Phase 3: Enhanced Status Command** (2-3 hours)
   - Add get_comprehensive_status()
   - Update CLI handler

4. **Phase 4: Enhanced Health Tool** (2-3 hours)
   - Add new response fields
   - Add index freshness
   - Add config warnings

5. **Phase 5: Testing** (2 hours)

**Total: 11-15 hours**

---

## Environment Variables Added

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DAEM0NMCP_HYBRID_VECTOR_WEIGHT` | float | 0.3 | Vector vs TF-IDF weight |
| `DAEM0NMCP_SEARCH_DIVERSITY_MAX_PER_FILE` | int | 3 | Max results per file |
| `DAEM0NMCP_SEARCH_DEFAULT_LIMIT` | int | 20 | Default search limit |
| `DAEM0NMCP_EMBEDDING_MODEL` | str | all-MiniLM-L6-v2 | Sentence transformer model |
| `DAEM0NMCP_PARSE_TREE_CACHE_MAXSIZE` | int | 200 | Max cached parse trees |
| `DAEM0NMCP_INDEX_LANGUAGES` | list | [] | Languages to index |
