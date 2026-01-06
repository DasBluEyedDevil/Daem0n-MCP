# Implementation Plan: Iteration 2 - Code Entity Fidelity

**Date:** 2026-01-06
**Estimated Effort:** 12-16 hours
**Risk Level:** Medium - AST query changes require per-language testing

---

## Executive Summary

This plan details the implementation of "Code Entity Fidelity" for Daem0n-MCP, improving how code entities are tracked and linked to memories:

1. **Stable symbol IDs** - Remove line_start from ID, use qualified_name instead
2. **Extract imports from AST** - Add import extraction queries per language
3. **Compute qualified names** - Walk parent scopes (module.class.method)
4. **Wire memories to CodeEntity IDs** - Use MemoryCodeRef table, auto-link on remember()

---

## Current State Analysis

### 1. Symbol ID Generation (Problem: Unstable IDs)

**File:** `daem0nmcp/code_indexer.py` (lines 449-454)

```python
def _make_entity_dict(self, **kwargs) -> Dict[str, Any]:
    # Include line_start in ID to distinguish same-named entities
    line_start = kwargs.get('line_start', 0)
    id_string = f"{kwargs['project_path']}:{kwargs['file_path']}:{kwargs['name']}:{kwargs['entity_type']}:{line_start}"
    entity_id = hashlib.sha256(id_string.encode()).hexdigest()[:16]
```

**Problem:** Line numbers change when code is edited, breaking entity IDs.

### 2. Empty Usage Tracking Fields

```python
# code_indexer.py:466-469
'calls': [],
'called_by': [],
'imports': [],
'inherits': [],
```

**Problem:** Tree-sitter queries only extract definitions, not usages.

### 3. Unused MemoryCodeRef Table

The `MemoryCodeRef` table exists in `models.py` but is never populated.

### 4. No Qualified Names

The `qualified_name` field exists but is never computed.

---

## Phase 1: Qualified Name Computation (4-5 hours)

### 1.1 Add Qualified Name Extraction Logic

**File:** `daem0nmcp/code_indexer.py`

Add method to walk parent scopes:

```python
def _compute_qualified_name(self, node, source: bytes, lang: str, file_path: str) -> str:
    """
    Compute fully qualified name by walking parent scopes.

    Examples:
      - Python class method: module.ClassName.method_name
      - Nested class: module.Outer.Inner.method
      - Top-level function: module.function_name
    """
    parts = []

    # Walk up the tree collecting scope names
    current = node.parent
    while current is not None:
        if lang == 'python':
            if current.type == 'class_definition':
                name_node = self._find_name_child(current, source)
                if name_node:
                    parts.insert(0, name_node)
        elif lang in ('typescript', 'javascript', 'tsx'):
            if current.type == 'class_declaration':
                name_node = self._find_name_child(current, source)
                if name_node:
                    parts.insert(0, name_node)
        elif lang == 'go':
            if current.type == 'method_declaration':
                receiver = self._extract_go_receiver(current, source)
                if receiver:
                    parts.insert(0, receiver)
        current = current.parent

    # Add the entity's own name
    entity_name = self._extract_name_from_node(node, source)
    if entity_name:
        parts.append(entity_name)

    # Prepend module name from file path
    module_name = self._file_path_to_module(file_path, lang)
    if module_name:
        parts.insert(0, module_name)

    return '.'.join(parts) if parts else entity_name or "anonymous"

def _file_path_to_module(self, file_path: str, lang: str) -> str:
    """Convert file path to module name."""
    from pathlib import Path
    p = Path(file_path)

    parts = list(p.parts)
    if parts:
        stem = p.stem
        if stem == '__init__':
            parts = parts[:-1]
        else:
            parts[-1] = stem

    return '.'.join(parts)

def _find_name_child(self, node, source: bytes) -> Optional[str]:
    """Find the name identifier within a scope node."""
    name_types = {'identifier', 'type_identifier', 'constant', 'name'}
    for child in node.children:
        if child.type in name_types:
            return source[child.start_byte:child.end_byte].decode('utf-8', errors='replace')
    return None
```

### 1.2 Integrate into Entity Extraction

Modify `_extract_entities()` to include `qualified_name`:

```python
yield {
    'entity_type': entity_type,
    'name': name,
    'qualified_name': self._compute_qualified_name(def_node, source, lang, file_path),
    'line_start': def_node.start_point[0] + 1,
    'line_end': def_node.end_point[0] + 1,
    'signature': signature,
    'docstring': docstring,
}
```

---

## Phase 2: Stable Symbol IDs (1 hour)

### 2.1 Update ID Generation Logic

**File:** `daem0nmcp/code_indexer.py`

Replace the ID generation:

```python
def _make_entity_dict(self, **kwargs) -> Dict[str, Any]:
    """Create a CodeEntity-compatible dictionary."""
    # Use qualified_name for stable IDs (no line numbers)
    identifier = kwargs.get('qualified_name') or kwargs['name']
    id_string = f"{kwargs['project_path']}:{kwargs['file_path']}:{identifier}:{kwargs['entity_type']}"
    entity_id = hashlib.sha256(id_string.encode()).hexdigest()[:16]

    return {
        'id': entity_id,
        'project_path': kwargs['project_path'],
        'entity_type': kwargs['entity_type'],
        'name': kwargs['name'],
        'qualified_name': kwargs.get('qualified_name'),
        'file_path': kwargs['file_path'],
        # ... rest unchanged
    }
```

---

## Phase 3: Import Extraction from AST (4-6 hours)

### 3.1 Add Import Queries

**File:** `daem0nmcp/code_indexer.py`

Add after `ENTITY_QUERIES`:

```python
IMPORT_QUERIES = {
    'python': """
        (import_statement
            name: (dotted_name) @import.name) @import.def
        (import_from_statement
            module_name: (dotted_name) @import.module
            name: (dotted_name) @import.name) @import.def
        (import_from_statement
            module_name: (dotted_name) @import.module
            name: (aliased_import
                name: (dotted_name) @import.name)) @import.def
    """,
    'typescript': """
        (import_statement
            source: (string) @import.source) @import.def
        (import_clause
            (identifier) @import.default) @import.clause
        (import_clause
            (named_imports
                (import_specifier
                    name: (identifier) @import.name))) @import.clause
    """,
    'javascript': """
        (import_statement
            source: (string) @import.source) @import.def
        (import_clause
            (identifier) @import.default) @import.clause
        (import_clause
            (named_imports
                (import_specifier
                    name: (identifier) @import.name))) @import.clause
    """,
    'go': """
        (import_declaration
            (import_spec
                path: (interpreted_string_literal) @import.path)) @import.def
        (import_declaration
            (import_spec_list
                (import_spec
                    path: (interpreted_string_literal) @import.path))) @import.def
    """,
    'rust': """
        (use_declaration
            argument: (scoped_identifier) @import.path) @import.def
        (use_declaration
            argument: (use_wildcard) @import.path) @import.def
    """,
}
```

### 3.2 Add Import Extraction Method

```python
def _extract_imports(self, tree, language, lang: str, source: bytes) -> List[str]:
    """Extract import statements from a parsed file."""
    import tree_sitter

    query_text = IMPORT_QUERIES.get(lang)
    if not query_text:
        return []

    try:
        query = tree_sitter.Query(language, query_text)
        cursor = tree_sitter.QueryCursor(query)
        matches = list(cursor.matches(tree.root_node))
    except Exception as e:
        logger.debug(f"Import query failed for {lang}: {e}")
        return []

    imports = []
    for pattern_index, captures_dict in matches:
        for capture_name, nodes in captures_dict.items():
            if capture_name in ('import.name', 'import.module', 'import.path',
                               'import.default', 'import.source'):
                for node in nodes:
                    text = node.text.decode('utf-8', errors='replace')
                    text = text.strip('"\'')
                    if text and text not in imports:
                        imports.append(text)

    return imports
```

### 3.3 Integrate into index_file()

```python
def index_file(self, file_path: Path, project_path: Path):
    # ... existing parsing code ...

    tree = parser.parse(source)

    # Extract file-level imports
    file_imports = self._extract_imports(tree, language, lang, source)

    for entity in self._extract_entities(tree, language, lang, source):
        entity['project_path'] = str(project_path)
        entity['file_path'] = str(relative_path)
        entity['imports'] = file_imports  # Associate imports with entities
        yield self._make_entity_dict(**entity)
```

---

## Phase 4: Wire Memories to CodeEntity IDs (3-4 hours)

### 4.1 Add Auto-Link Helper to MemoryManager

**File:** `daem0nmcp/memory.py`

```python
async def _link_memory_to_entities(
    self,
    memory_id: int,
    content: str,
    file_path: Optional[str],
    project_path: Optional[str]
) -> List[Dict[str, Any]]:
    """Auto-link memory to referenced code entities."""
    from .similarity import extract_code_symbols
    from .models import MemoryCodeRef
    from .code_indexer import CodeIndexManager

    if not project_path:
        return []

    symbols = extract_code_symbols(content)
    if not symbols:
        return []

    code_index = CodeIndexManager(db=self.db, qdrant=self._qdrant)

    created_refs = []
    seen_entity_ids = set()

    async with self.db.get_session() as session:
        for symbol in symbols:
            entity = await code_index.find_entity(
                name=symbol,
                project_path=project_path
            )

            if not entity or entity['id'] in seen_entity_ids:
                continue

            seen_entity_ids.add(entity['id'])

            ref = MemoryCodeRef(
                memory_id=memory_id,
                code_entity_id=entity['id'],
                entity_type=entity.get('entity_type'),
                entity_name=entity.get('name'),
                file_path=entity.get('file_path'),
                line_number=entity.get('line_start'),
                relationship='about'
            )
            session.add(ref)

            created_refs.append({
                'code_entity_id': entity['id'],
                'entity_name': entity['name'],
                'file_path': entity['file_path']
            })

    if created_refs:
        logger.info(f"Linked memory {memory_id} to {len(created_refs)} code entities")

    return created_refs
```

### 4.2 Call Auto-Link from remember()

In `remember()` method, after storing the memory:

```python
    # Auto-link to code entities
    code_refs = []
    if project_path:
        try:
            code_refs = await self._link_memory_to_entities(
                memory_id=memory_id,
                content=content,
                file_path=file_path,
                project_path=project_path
            )
        except Exception as e:
            logger.debug(f"Code entity linking failed (non-fatal): {e}")

    result = {
        "id": memory_id,
        # ... existing fields ...
        "code_refs": code_refs if code_refs else None,
    }
```

### 4.3 Add Query Method for Code Refs

```python
async def get_memories_for_entity(
    self,
    entity_id: str,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """Get all memories linked to a specific code entity."""
    from .models import Memory, MemoryCodeRef
    from sqlalchemy import select

    async with self.db.get_session() as session:
        query = (
            select(Memory, MemoryCodeRef.relationship)
            .join(MemoryCodeRef, Memory.id == MemoryCodeRef.memory_id)
            .where(
                MemoryCodeRef.code_entity_id == entity_id,
                _not_archived_condition()
            )
            .order_by(Memory.created_at.desc())
            .limit(limit)
        )

        result = await session.execute(query)
        rows = result.all()

        return [
            {
                'id': mem.id,
                'category': mem.category,
                'content': mem.content,
                'relationship': rel,
                'created_at': mem.created_at.isoformat()
            }
            for mem, rel in rows
        ]
```

---

## Phase 5: Migration (2-3 hours)

### 5.1 Add Index for qualified_name

**File:** `daem0nmcp/migrations/schema.py`

```python
(11, "Add index on code_entities qualified_name", [
    "CREATE INDEX IF NOT EXISTS idx_code_entities_qualified_name ON code_entities(qualified_name);",
]),
```

### 5.2 Backfill Script

**File:** `daem0nmcp/migrations/backfill_code_refs.py`

```python
async def backfill_code_refs(db_manager, project_path: str) -> dict:
    """Scan existing memories and create MemoryCodeRef entries."""
    from ..models import Memory, MemoryCodeRef
    from ..similarity import extract_code_symbols
    from ..code_indexer import CodeIndexManager

    code_index = CodeIndexManager(db=db_manager, qdrant=None)

    stats = {
        'memories_scanned': 0,
        'refs_created': 0,
    }

    async with db_manager.get_session() as session:
        result = await session.execute(
            select(Memory).where(Memory.file_path.like(f"{project_path}%"))
        )
        memories = result.scalars().all()

        for memory in memories:
            stats['memories_scanned'] += 1
            symbols = extract_code_symbols(memory.content)

            for symbol in symbols:
                entity = await code_index.find_entity(name=symbol, project_path=project_path)
                if entity:
                    ref = MemoryCodeRef(
                        memory_id=memory.id,
                        code_entity_id=entity['id'],
                        entity_name=entity['name'],
                        relationship='about'
                    )
                    session.add(ref)
                    stats['refs_created'] += 1

    return stats
```

---

## Phase 6: Test Cases

### Tests for Qualified Names

```python
class TestQualifiedNames:
    def test_qualified_name_nested_class_method(self, temp_project, nested_python):
        from daem0nmcp.code_indexer import TreeSitterIndexer

        indexer = TreeSitterIndexer()
        entities = list(indexer.index_file(nested_python, temp_project))

        update_method = next(e for e in entities if e['name'] == 'update')
        assert update_method['qualified_name'] == 'models.User.Profile.update'

    def test_qualified_name_top_level_function(self, temp_project, nested_python):
        indexer = TreeSitterIndexer()
        entities = list(indexer.index_file(nested_python, temp_project))

        helper = next(e for e in entities if e['name'] == 'helper')
        assert helper['qualified_name'] == 'models.helper'
```

### Tests for Stable Entity IDs

```python
class TestStableEntityIDs:
    def test_entity_id_stable_after_line_change(self, temp_project):
        py_file = temp_project / "service.py"
        py_file.write_text('class UserService:\n    def authenticate(self): pass')

        indexer = TreeSitterIndexer()
        entities1 = list(indexer.index_file(py_file, temp_project))

        # Add lines before (shifts line numbers)
        py_file.write_text('# comment\n# another\nclass UserService:\n    def authenticate(self): pass')

        entities2 = list(indexer.index_file(py_file, temp_project))

        # IDs should be the same
        for e1 in entities1:
            matching = [e2 for e2 in entities2 if e2['name'] == e1['name']]
            assert matching[0]['id'] == e1['id']
```

### Tests for Import Extraction

```python
class TestImportExtraction:
    def test_python_imports(self, temp_project):
        py_file = temp_project / "app.py"
        py_file.write_text('import os\nfrom pathlib import Path\ndef main(): pass')

        indexer = TreeSitterIndexer()
        entities = list(indexer.index_file(py_file, temp_project))

        main_func = next(e for e in entities if e['name'] == 'main')
        imports = main_func.get('imports', [])

        assert 'os' in imports
        assert 'Path' in imports or 'pathlib' in imports
```

---

## Implementation Order

1. **Phase 1: Qualified Names** (4-5 hours)
2. **Phase 2: Stable IDs** (1 hour)
3. **Phase 3: Import Extraction** (4-6 hours)
4. **Phase 4: Memory Linking** (3-4 hours)
5. **Phase 5: Migration** (2-3 hours)
6. **Phase 6: Testing** (2-3 hours)

---

## Success Criteria

1. **Stable IDs**: Adding lines to a file does NOT change entity IDs
2. **Qualified Names**: `User.save` has qualified_name `models.User.save`
3. **Imports Populated**: Python/TypeScript/JavaScript files have non-empty imports
4. **Memory Linking**: `remember("Use \`UserService\`...")` creates MemoryCodeRef entry
5. **Query Works**: `get_memories_for_entity(entity_id)` returns linked memories
