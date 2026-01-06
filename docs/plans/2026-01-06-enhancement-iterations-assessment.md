# Daem0n-MCP Enhancement Iterations: ROI Assessment

**Date:** 2026-01-06
**Focus:** Sharpening existing capabilities, not expanding scope

---

## Overview

Four proposed iterations to enhance what Daem0n-MCP already does well:

| Iteration | Focus | Effort | Impact | Priority |
|-----------|-------|--------|--------|----------|
| 1. Search Quality | Hybrid tuning, diversity, tags | Low-Medium | **High** | **1st** |
| 2. Code Entity Fidelity | Symbol IDs, references, memory linking | Medium | Medium-High | 2nd |
| 3. Impact + Watcher Refinement | Better analyze_impact, incremental indexing | Medium-High | Medium | 3rd |
| 4. Performance & UX Polish | Caching, config, diagnostics | Low | Medium | 4th |

**Recommendation:** Start with Iteration 1. It's the highest ROI with lowest risk.

---

## Iteration 1: Search Quality

### What's Proposed
1. Make hybrid weighting configurable (currently hardcoded at `0.3`)
2. Add diversity to results (avoid 10 hits from same file)
3. Add lightweight tags to memories (`bugfix`, `design-note`, `todo`, `hack`, `perf`)

### Current State Analysis

**Hybrid weighting** - Found in two places:
- `vectors.py:157` - `self.vector_weight = 0.3`
- `memory.py:219` - `vector_weight = 0.3  # Same as HybridSearch.vector_weight`

Both are hardcoded. No config option exists.

**Diversity** - Not implemented. Current search just returns top-k by score.

**Tags** - Already partially supported:
- `Memory` model has `tags: List[str]` field
- TF-IDF gives tags 3x weight boost
- But no auto-inference of tag types

### ROI Assessment

| Change | Effort | Impact | Verdict |
|--------|--------|--------|---------|
| Configurable hybrid weight | **2 hours** | Medium | ✅ Easy win |
| Auto-tune by project size | 4-6 hours | Low | ⚠️ Defer - needs benchmarking first |
| Result diversity | **3-4 hours** | **High** | ✅ **Best ROI** |
| Memory type tags | 2-3 hours | Medium | ✅ Good addition |

### Implementation Specifics

**1. Configurable hybrid weight:**
```python
# config.py - add:
hybrid_vector_weight: float = 0.3  # 0.0 = TF-IDF only, 1.0 = vectors only
```

Then reference `settings.hybrid_vector_weight` in `memory.py:219` and `vectors.py:157`.

**2. Result diversity (file deduplication):**
```python
def _diversify_results(results: List[Tuple[int, float]], memories: Dict, max_per_file: int = 3):
    """Limit results from same file to improve diversity."""
    file_counts = {}
    diverse = []
    for mem_id, score in results:
        file_path = memories[mem_id].get('file_path', '')
        if file_counts.get(file_path, 0) < max_per_file:
            diverse.append((mem_id, score))
            file_counts[file_path] = file_counts.get(file_path, 0) + 1
    return diverse
```

Apply after `_hybrid_search()` in `recall()` and `search_memories()`.

**3. Lightweight tags:**
Add to `remember()` - infer tags from content/category:
```python
def _infer_tags(content: str, category: str) -> List[str]:
    tags = []
    content_lower = content.lower()
    if 'fix' in content_lower or 'bug' in content_lower:
        tags.append('bugfix')
    if 'todo' in content_lower or 'hack' in content_lower:
        tags.append('tech-debt')
    if 'perf' in content_lower or 'slow' in content_lower or 'optim' in content_lower:
        tags.append('perf')
    if category == 'warning':
        tags.append('warning')
    return tags
```

### Verdict: **HIGH ROI - DO FIRST**

**Time estimate:** 6-8 hours total
**Risk:** Low - isolated changes, easy to test
**Dependencies:** None

---

## Iteration 2: Code Entity Fidelity

### What's Proposed
1. Improve symbol/usage mapping ("who calls this?", "where is this used?")
2. Store stable symbol IDs (module + name + kind + signature)
3. Wire memories to `CodeEntity` IDs, not just file paths

### Current State Analysis

**Symbol IDs** - Currently using:
```python
# code_indexer.py:452-454
id_string = f"{kwargs['project_path']}:{kwargs['file_path']}:{kwargs['name']}:{kwargs['entity_type']}:{line_start}"
entity_id = hashlib.sha256(id_string.encode()).hexdigest()[:16]
```

Problem: Line number in ID means any code shift breaks the ID.

**Usage tracking** - `CodeEntity` model has fields but they're always empty:
```python
# code_indexer.py:466-469
'calls': [],
'called_by': [],
'imports': [],
'inherits': [],
```

The tree-sitter queries only extract definitions, not usages.

**Memory-to-entity linking** - `MemoryCodeRef` table exists in models but is unused.

### ROI Assessment

| Change | Effort | Impact | Verdict |
|--------|--------|--------|---------|
| Stable symbol IDs (remove line_start) | **1 hour** | Medium | ✅ Easy fix |
| Extract function calls from AST | **8-12 hours** | Medium | ⚠️ Complex - needs per-language queries |
| Extract imports from AST | 4-6 hours | Medium | ✅ Feasible |
| Wire memories to CodeEntity | 3-4 hours | Medium-High | ✅ Good ROI |

### Implementation Specifics

**1. Stable symbol IDs:**
```python
# Better: use qualified name without line number
id_string = f"{kwargs['project_path']}:{kwargs['file_path']}:{kwargs.get('qualified_name', kwargs['name'])}:{kwargs['entity_type']}"
```

Need to compute `qualified_name` by walking parent scopes (class→method, module→function).

**2. Extract imports (Python example):**
```python
# Add to ENTITY_QUERIES['python']:
(import_statement
    name: (dotted_name) @import.name) @import.def
(import_from_statement
    module_name: (dotted_name) @import.module
    name: (dotted_name) @import.name) @import.def
```

**3. Memory-to-entity linking:**
When `remember()` is called with `file_path` and content containing backtick symbols:
```python
async def _link_memory_to_entities(self, memory_id: int, content: str, file_path: str):
    """Auto-link memory to referenced code entities."""
    symbols = extract_code_symbols(content)  # Already exists in similarity.py
    for symbol in symbols:
        entity = await self.code_index.find_entity(symbol)
        if entity:
            # Insert into memory_code_refs
            ...
```

### Verdict: **MEDIUM-HIGH ROI - DO SECOND**

**Time estimate:** 12-16 hours total
**Risk:** Medium - AST query changes need careful testing per language
**Dependencies:** None (can do in parallel with Iteration 1)

---

## Iteration 3: Impact + Watcher Refinement

### What's Proposed
1. Enhance `analyze_impact` with LLM reasoning step
2. Add `suggested_checks` and `risk_notes` fields to response
3. Watcher: re-index only changed entities (incremental)
4. Watcher: update/expire memories when code moves

### Current State Analysis

**analyze_impact** - Currently does basic lookup:
```python
# code_indexer.py:838-918
# Just searches for entity name in other entities' calls/imports lists
# Returns empty results because calls/imports are never populated
```

Without Iteration 2's usage tracking, this is nearly useless.

**Watcher re-indexing** - Currently watches files but doesn't re-index:
```python
# watcher.py - _analyze_change() just does memory recall
# No call to code_index.index_project()
```

**Memory span tracking** - Memories have `file_path` and `span` but no mechanism to detect when code moves.

### ROI Assessment

| Change | Effort | Impact | Verdict |
|--------|--------|--------|---------|
| analyze_impact + LLM reasoning | 4-6 hours | Medium | ⚠️ Needs Iteration 2 first |
| suggested_checks field | 2 hours | Low | ⚠️ Only useful with better impact data |
| Incremental re-indexing | **6-8 hours** | **High** | ✅ Significant perf improvement |
| Memory span sync | 4-6 hours | Low-Medium | ⚠️ Complex edge cases |

### Implementation Specifics

**1. Incremental re-indexing:**
```python
class CodeIndexManager:
    def __init__(self, ...):
        self._file_hashes: Dict[str, str] = {}  # path -> content hash

    async def index_file_if_changed(self, file_path: Path, project: Path) -> bool:
        """Re-index only if file content changed."""
        content = file_path.read_bytes()
        content_hash = hashlib.sha256(content).hexdigest()[:16]

        cached_hash = self._file_hashes.get(str(file_path))
        if cached_hash == content_hash:
            return False  # No change

        self._file_hashes[str(file_path)] = content_hash
        # Delete old entities for this file, index new ones
        ...
        return True
```

**2. analyze_impact enhancement (requires Iteration 2):**
```python
async def analyze_impact(self, entity_name: str, ...) -> Dict:
    # ... existing lookup ...

    # Add risk assessment
    result['risk_level'] = 'low'
    if len(affected_files) > 5:
        result['risk_level'] = 'high'
    elif any(e['type'] == 'class' for e in affected):
        result['risk_level'] = 'medium'

    # Suggest tests
    result['suggested_checks'] = [
        f"Run tests for {f}" for f in affected_files[:5]
    ]

    return result
```

### Verdict: **MEDIUM ROI - DO THIRD**

**Time estimate:** 16-20 hours total
**Risk:** Medium-High
**Dependencies:**
- Incremental indexing: None (can do independently)
- analyze_impact enhancement: **Requires Iteration 2**

---

## Iteration 4: Performance & UX Polish

### What's Proposed
1. Cache parse trees and language configs
2. Detect unchanged files via content hash (not just timestamps)
3. Centralize config in one file with `config` tool/CLI
4. Add "what is daemon doing?" status to existing tools

### Current State Analysis

**Parse tree caching** - Not implemented. Each `index_file()` call re-parses.

**Content hashing** - Not implemented. Would overlap with Iteration 3's incremental indexing.

**Config centralization** - `config.py` exists but missing many tunables:
- No hybrid weight config
- No diversity config
- No embedding model choice
- No language inclusion/exclusion

**Status reporting** - `index_project` returns stats but no progress during execution.

### ROI Assessment

| Change | Effort | Impact | Verdict |
|--------|--------|--------|---------|
| Parse tree caching | 2-3 hours | Low-Medium | ✅ Minor win |
| Content hash (same as Iteration 3) | — | — | ⚠️ Duplicate |
| Config centralization | **3-4 hours** | **Medium** | ✅ Good UX |
| `daem0n status` command | 2-3 hours | Low | ✅ Nice to have |
| Progress in index_project | 2 hours | Low | ⚠️ Limited value (MCP is request/response) |

### Implementation Specifics

**1. Parse tree caching:**
```python
class TreeSitterIndexer:
    def __init__(self):
        self._parsers: Dict[str, Any] = {}  # Already exists
        self._parse_cache: Dict[str, Tuple[bytes, Any]] = {}  # path -> (hash, tree)

    def parse_file(self, file_path: Path, lang: str):
        content = file_path.read_bytes()
        content_hash = hashlib.md5(content).hexdigest()

        cache_key = str(file_path)
        if cache_key in self._parse_cache:
            cached_hash, cached_tree = self._parse_cache[cache_key]
            if cached_hash == content_hash:
                return cached_tree

        parser, _ = self.get_parser(lang)
        tree = parser.parse(content)
        self._parse_cache[cache_key] = (content_hash, tree)
        return tree
```

**2. Config centralization - add to config.py:**
```python
# Search tuning
hybrid_vector_weight: float = 0.3
search_diversity_max_per_file: int = 3
search_default_limit: int = 20

# Code indexing
index_languages: List[str] = []  # Empty = all supported
index_skip_patterns: List[str] = []

# Embedding model
embedding_model: str = "all-MiniLM-L6-v2"
```

**3. Status command:**
```python
# cli.py
@cli.command()
def status():
    """Show daemon status and statistics."""
    # Count memories, entities, rules
    # Show last index time
    # Show config summary
```

### Verdict: **MEDIUM ROI - DO FOURTH**

**Time estimate:** 8-10 hours total
**Risk:** Low
**Dependencies:** Overlaps with Iteration 3 (content hashing)

---

## Recommended Implementation Order

```
Week 1: Iteration 1 - Search Quality (6-8 hours)
├── Configurable hybrid weight (2h)
├── Result diversity (3-4h)
└── Lightweight tag inference (2-3h)

Week 2: Iteration 2 - Code Entity Fidelity (12-16 hours)
├── Stable symbol IDs (1h)
├── Extract imports from AST (4-6h)
├── Wire memories to CodeEntity IDs (3-4h)
└── Qualified name computation (4-5h)

Week 3: Iteration 3 - Incremental Indexing Only (6-8 hours)
├── Content hash tracking (2h)
├── Selective re-indexing (4-6h)
└── Skip unchanged files (1h)

Week 4: Iteration 4 + Iteration 3 Completion (10-14 hours)
├── Parse tree caching (2-3h)
├── Config centralization (3-4h)
├── Status command (2-3h)
├── analyze_impact enhancement (4-6h) [needs Iteration 2]
└── Watcher integration (2h)
```

---

## What NOT to Do

| Suggestion | Why Skip |
|------------|----------|
| Auto-tune hybrid weight by project size | Needs benchmarks first. Premature optimization. |
| Full call graph extraction | Too complex per-language. Start with imports only. |
| Memory span sync when code moves | Edge cases are gnarly. Low ROI for complexity. |
| LLM reasoning in analyze_impact | Adds dependency, latency. Rule-based is fine for now. |
| Progress callbacks in index_project | MCP is request/response, no streaming. Limited value. |

---

## Summary

**Best ROI:** Iteration 1 (Search Quality) - low effort, high user-visible impact
**Second best:** Iteration 2 (Code Entity Fidelity) - enables future improvements
**Third:** Iteration 3 (Incremental Indexing part only) - perf wins
**Fourth:** Iteration 4 (Polish) - nice to have

**Total estimated time:** 32-46 hours across 4 iterations
**Scope creep risk:** Low - all changes enhance existing tools, no new domains
