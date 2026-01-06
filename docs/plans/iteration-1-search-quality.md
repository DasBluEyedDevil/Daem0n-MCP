# Implementation Plan: Iteration 1 - Search Quality

**Date:** 2026-01-06
**Estimated Effort:** 6-8 hours
**Priority:** Highest ROI enhancement

---

## Executive Summary

This plan details three enhancements to Daem0n-MCP's search capabilities:
1. **Configurable hybrid weight** - Move hardcoded `0.3` to settings
2. **Result diversity** - Limit results from same source file (max 3 per file)
3. **Lightweight tag inference** - Auto-add semantic tags (`bugfix`, `tech-debt`, `perf`, `warning`)

All changes are isolated, testable, and maintain backward compatibility.

---

## 1. Configurable Hybrid Weight

### Current State

The hybrid weight is hardcoded in two locations:

**Location 1: `/home/user/Daem0n-MCP/daem0nmcp/vectors.py` line 157**
```python
class HybridSearch:
    def __init__(self, tfidf_index, vector_index: Optional[VectorIndex] = None):
        self.tfidf = tfidf_index
        self.vectors = vector_index or VectorIndex()
        self.vector_weight = 0.3  # How much to weight vectors vs TF-IDF
```

**Location 2: `/home/user/Daem0n-MCP/daem0nmcp/memory.py` lines 219**
```python
def _hybrid_search(
    self,
    query: str,
    top_k: int = 10,
    tfidf_threshold: float = 0.1,
    vector_threshold: float = 0.3
) -> List[Tuple[int, float]]:
    """..."""
    vector_weight = 0.3  # Same as HybridSearch.vector_weight
```

### Implementation Steps

#### Step 1.1: Add Config Option

**File:** `/home/user/Daem0n-MCP/daem0nmcp/config.py`

**Location:** After line 65 (after `watcher_watch_extensions`)

**Add these new settings:**
```python
    # Search tuning
    hybrid_vector_weight: float = 0.3  # 0.0 = TF-IDF only, 1.0 = vectors only
    search_diversity_max_per_file: int = 3  # Max results from same source file
```

#### Step 1.2: Update memory.py

**File:** `/home/user/Daem0n-MCP/daem0nmcp/memory.py`

**Change line 219 from:**
```python
        vector_weight = 0.3  # Same as HybridSearch.vector_weight
```

**To:**
```python
        vector_weight = settings.hybrid_vector_weight
```

The `settings` import already exists at line 22:
```python
from .config import settings
```

#### Step 1.3: Update vectors.py

**File:** `/home/user/Daem0n-MCP/daem0nmcp/vectors.py`

**Add import at top (after line 7):**
```python
from .config import settings
```

**Change line 157 from:**
```python
        self.vector_weight = 0.3  # How much to weight vectors vs TF-IDF
```

**To:**
```python
        self.vector_weight = settings.hybrid_vector_weight  # Configurable via DAEM0NMCP_HYBRID_VECTOR_WEIGHT
```

---

## 2. Result Diversity

### Current State

Search returns top-k results by score only. If 10 memories relate to the same file, all 10 may be returned, reducing diversity of context.

### Implementation Steps

#### Step 2.1: Add Diversity Function

**File:** `/home/user/Daem0n-MCP/daem0nmcp/memory.py`

**Location:** Add after the `_hybrid_search()` method (after line 268)

**New function:**
```python
    def _diversify_results(
        self,
        scored_results: List[Tuple[int, float]],
        memories: Dict[int, Any],
        max_per_file: int
    ) -> List[Tuple[int, float]]:
        """
        Limit results from same source file to improve diversity.

        Results are already sorted by score descending. This preserves
        highest-scoring items but caps per-file representation.

        Args:
            scored_results: List of (memory_id, score) tuples, sorted by score desc
            memories: Dict mapping memory_id to Memory object
            max_per_file: Maximum results to allow from any single file

        Returns:
            Filtered list maintaining score order
        """
        if max_per_file <= 0:
            return scored_results  # No limit

        file_counts: Dict[Optional[str], int] = {}
        diverse: List[Tuple[int, float]] = []

        for mem_id, score in scored_results:
            mem = memories.get(mem_id)
            if not mem:
                continue

            # Use file_path or file_path_relative, defaulting to None for memories without file
            file_key = getattr(mem, 'file_path', None) or getattr(mem, 'file_path_relative', None)

            current_count = file_counts.get(file_key, 0)
            if current_count < max_per_file:
                diverse.append((mem_id, score))
                file_counts[file_key] = current_count + 1

        return diverse
```

#### Step 2.2: Apply Diversity in recall()

**File:** `/home/user/Daem0n-MCP/daem0nmcp/memory.py`

**Location:** In `recall()` method, after line 723 where `memories` dict is populated

**Add after the memories dict is built (after line 744), before the tag filtering (line 747):**
```python
        # Apply diversity limit before further filtering
        max_per_file = settings.search_diversity_max_per_file
        if max_per_file > 0 and search_results:
            search_results = self._diversify_results(
                search_results,
                memories,
                max_per_file
            )
```

#### Step 2.3: Apply Diversity in search()

**File:** `/home/user/Daem0n-MCP/daem0nmcp/memory.py`

**Location:** In `search()` method, around line 1122

**Add after memories dict is built (after line 1131), before the return:**
```python
        # Apply diversity limit
        max_per_file = settings.search_diversity_max_per_file
        if max_per_file > 0 and results:
            results = self._diversify_results(results, memories, max_per_file)
```

---

## 3. Lightweight Tag Inference

### Current State

Tags are passed explicitly to `remember()`. The `TFIDFIndex.add_document()` already gives tags 3x weight boost (line 211 in similarity.py). But there's no auto-inference.

### Implementation Steps

#### Step 3.1: Add Tag Inference Function

**File:** `/home/user/Daem0n-MCP/daem0nmcp/memory.py`

**Location:** Add as a module-level function after the `_normalize_file_path()` function (after line 95)

**New function:**
```python
def _infer_tags(content: str, category: str, existing_tags: Optional[List[str]] = None) -> List[str]:
    """
    Infer semantic tags from memory content and category.

    Auto-detects common patterns to improve search recall:
    - bugfix: mentions of fixing bugs, errors, issues
    - tech-debt: TODOs, hacks, workarounds, temporary solutions
    - perf: performance, optimization, speed improvements
    - warning: category-based or explicit warnings

    Args:
        content: The memory content text
        category: Memory category (decision, pattern, warning, learning)
        existing_tags: Already-provided tags (won't duplicate)

    Returns:
        List of inferred tags (excludes duplicates from existing_tags)
    """
    inferred: List[str] = []
    existing = set(t.lower() for t in (existing_tags or []))
    content_lower = content.lower()

    # Bugfix patterns
    bugfix_patterns = ['fix', 'bug', 'error', 'issue', 'broken', 'crash', 'failure']
    if any(p in content_lower for p in bugfix_patterns):
        if 'bugfix' not in existing:
            inferred.append('bugfix')

    # Tech debt patterns
    debt_patterns = ['todo', 'hack', 'workaround', 'temporary', 'temp fix', 'quick fix', 'tech debt', 'refactor later']
    if any(p in content_lower for p in debt_patterns):
        if 'tech-debt' not in existing:
            inferred.append('tech-debt')

    # Performance patterns
    perf_patterns = ['perf', 'performance', 'slow', 'fast', 'optim', 'speed', 'latency', 'cache']
    if any(p in content_lower for p in perf_patterns):
        if 'perf' not in existing:
            inferred.append('perf')

    # Warning category auto-tag
    if category == 'warning':
        if 'warning' not in existing:
            inferred.append('warning')

    # Explicit warning mentions in non-warning categories
    if category != 'warning' and ('warn' in content_lower or 'avoid' in content_lower or "don't" in content_lower):
        if 'warning' not in existing:
            inferred.append('warning')

    return inferred
```

#### Step 3.2: Integrate Into remember()

**File:** `/home/user/Daem0n-MCP/daem0nmcp/memory.py`

**Location:** In `remember()` method, around line 299

**Add before the keywords extraction block (after line 297):**
```python
        # Infer semantic tags from content
        inferred_tags = _infer_tags(content, category, tags)
        if inferred_tags:
            tags = list(tags or []) + inferred_tags
```

#### Step 3.3: Integrate Into remember_batch()

**File:** `/home/user/Daem0n-MCP/daem0nmcp/memory.py`

**Location:** In `remember_batch()` method, around line 472

**Change to:**
```python
                category = mem["category"]
                content = mem["content"]
                rationale = mem.get("rationale")
                base_tags = mem.get("tags") or []

                # Infer semantic tags from content
                inferred_tags = _infer_tags(content, category, base_tags)
                tags = list(base_tags) + inferred_tags if inferred_tags else base_tags
```

---

## 4. Test Cases

### New Test File: `/home/user/Daem0n-MCP/tests/test_search_quality.py`

```python
"""Tests for Iteration 1: Search Quality enhancements."""

import pytest
from daem0nmcp.memory import _infer_tags, MemoryManager
from daem0nmcp.config import Settings


class TestConfigurableHybridWeight:
    """Test hybrid weight configuration."""

    def test_default_hybrid_weight(self):
        """Default hybrid weight is 0.3."""
        settings = Settings()
        assert settings.hybrid_vector_weight == 0.3

    def test_hybrid_weight_from_env(self, monkeypatch):
        """Hybrid weight can be set via environment."""
        monkeypatch.setenv("DAEM0NMCP_HYBRID_VECTOR_WEIGHT", "0.5")
        settings = Settings()
        assert settings.hybrid_vector_weight == 0.5

    def test_hybrid_weight_bounds(self, monkeypatch):
        """Verify extreme values work."""
        # TF-IDF only
        monkeypatch.setenv("DAEM0NMCP_HYBRID_VECTOR_WEIGHT", "0.0")
        settings = Settings()
        assert settings.hybrid_vector_weight == 0.0

        # Vectors only
        monkeypatch.setenv("DAEM0NMCP_HYBRID_VECTOR_WEIGHT", "1.0")
        settings = Settings()
        assert settings.hybrid_vector_weight == 1.0


class TestResultDiversity:
    """Test result diversity (file deduplication)."""

    def test_default_diversity_setting(self):
        """Default max_per_file is 3."""
        settings = Settings()
        assert settings.search_diversity_max_per_file == 3

    def test_diversity_from_env(self, monkeypatch):
        """Diversity limit can be set via environment."""
        monkeypatch.setenv("DAEM0NMCP_SEARCH_DIVERSITY_MAX_PER_FILE", "5")
        settings = Settings()
        assert settings.search_diversity_max_per_file == 5


class TestInferTags:
    """Test lightweight tag inference."""

    def test_infer_bugfix_from_fix(self):
        """Detects 'fix' as bugfix."""
        tags = _infer_tags("Fixed the login bug", "decision")
        assert "bugfix" in tags

    def test_infer_bugfix_from_error(self):
        """Detects 'error' as bugfix."""
        tags = _infer_tags("Resolved the connection error", "learning")
        assert "bugfix" in tags

    def test_infer_tech_debt_from_todo(self):
        """Detects 'TODO' as tech-debt."""
        tags = _infer_tags("TODO: refactor this later", "pattern")
        assert "tech-debt" in tags

    def test_infer_tech_debt_from_hack(self):
        """Detects 'hack' as tech-debt."""
        tags = _infer_tags("This is a temporary hack", "decision")
        assert "tech-debt" in tags

    def test_infer_perf_from_performance(self):
        """Detects 'performance' as perf."""
        tags = _infer_tags("Improved query performance", "learning")
        assert "perf" in tags

    def test_infer_perf_from_cache(self):
        """Detects 'cache' as perf."""
        tags = _infer_tags("Added caching layer", "decision")
        assert "perf" in tags

    def test_infer_warning_from_category(self):
        """Warning category auto-adds warning tag."""
        tags = _infer_tags("Don't use this API", "warning")
        assert "warning" in tags

    def test_infer_warning_from_avoid(self):
        """Detects 'avoid' in non-warning as warning."""
        tags = _infer_tags("Avoid using synchronous calls", "pattern")
        assert "warning" in tags

    def test_no_duplicate_with_existing_tags(self):
        """Doesn't duplicate existing tags."""
        tags = _infer_tags("Fixed a bug", "decision", existing_tags=["bugfix"])
        assert tags.count("bugfix") == 0  # Not added again

    def test_multiple_tags_inferred(self):
        """Can infer multiple tags from one content."""
        tags = _infer_tags("Temporary fix for slow performance", "decision")
        assert "tech-debt" in tags  # 'temporary'
        assert "perf" in tags  # 'slow', 'performance'
        assert "bugfix" in tags  # 'fix'

    def test_empty_content_no_tags(self):
        """Empty content returns empty tags."""
        tags = _infer_tags("", "decision")
        assert tags == []

    def test_no_match_returns_empty(self):
        """Content without patterns returns empty tags."""
        tags = _infer_tags("Use PostgreSQL for the database", "decision")
        assert tags == []
```

---

## 5. Migration Considerations

**No migrations required.** All changes are:
- New config options with sensible defaults
- New function that only affects new memories
- Runtime behavior changes (diversity) with no schema impact

Existing memories work as-is. New memories will have inferred tags added.

---

## 6. Verification Steps

### Manual Testing

1. **Hybrid Weight Configuration:**
   ```bash
   # Test default (0.3)
   python -c "from daem0nmcp.config import settings; print(settings.hybrid_vector_weight)"
   # Output: 0.3

   # Test override
   DAEM0NMCP_HYBRID_VECTOR_WEIGHT=0.7 python -c "from daem0nmcp.config import settings; print(settings.hybrid_vector_weight)"
   # Output: 0.7
   ```

2. **Diversity Configuration:**
   ```bash
   python -c "from daem0nmcp.config import settings; print(settings.search_diversity_max_per_file)"
   # Output: 3
   ```

3. **Tag Inference:**
   ```bash
   python -c "from daem0nmcp.memory import _infer_tags; print(_infer_tags('Fixed the bug', 'decision'))"
   # Output: ['bugfix']
   ```

### Automated Testing

```bash
# Run new tests
pytest tests/test_search_quality.py -v

# Run all memory tests (regression check)
pytest tests/test_memory.py -v

# Full test suite
pytest tests/ -v --tb=short
```

---

## 7. Environment Variable Reference

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DAEM0NMCP_HYBRID_VECTOR_WEIGHT` | float | `0.3` | Weight for vector similarity (0.0=TF-IDF only, 1.0=vectors only) |
| `DAEM0NMCP_SEARCH_DIVERSITY_MAX_PER_FILE` | int | `3` | Max results from same source file (0=unlimited) |

---

## 8. Rollback Plan

All changes are backward-compatible:
- Config options have defaults matching current behavior
- Tag inference only adds tags, never removes
- Diversity can be disabled with `DAEM0NMCP_SEARCH_DIVERSITY_MAX_PER_FILE=0`

To rollback:
1. Revert git commits
2. No database changes needed

---

## Summary

| Change | Files | Lines Changed |
|--------|-------|---------------|
| Configurable hybrid weight | config.py, memory.py, vectors.py | ~10 |
| Result diversity | memory.py | ~40 |
| Tag inference | memory.py | ~50 |
| Tests | tests/test_search_quality.py | ~100 |
| **Total** | 4 files | ~200 lines |
