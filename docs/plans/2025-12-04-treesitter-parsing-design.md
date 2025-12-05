# Tree-sitter Code Parsing Design

**Date:** 2025-12-04
**Status:** Approved
**Scope:** Replace regex-based parsing with Tree-sitter for accurate multi-language AST analysis

---

## Problem Statement

Current state in `context_manager.py`:
- Python: Uses `ast` module (good, accurate)
- JavaScript/TypeScript: Uses regex (fragile)
  - Finds imports inside comments
  - Misses multi-line imports
  - Can't detect functions or classes

---

## Design

### Parser Architecture

```
devilmcp/parsers/
├── __init__.py          # Registry and get_parser()
├── base.py              # Abstract CodeParser class
├── python_parser.py     # Uses tree-sitter-python
├── javascript_parser.py # Uses tree-sitter-javascript
└── typescript_parser.py # Uses tree-sitter-typescript
```

### Base Parser Interface

```python
# devilmcp/parsers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class Import:
    module: str
    names: list[str]
    line: int
    is_relative: bool = False

@dataclass
class Function:
    name: str
    start_line: int
    end_line: int
    params: list[str]

@dataclass
class Class:
    name: str
    start_line: int
    end_line: int
    methods: list[str]

class CodeParser(ABC):
    @abstractmethod
    def parse_imports(self, source: str) -> list[Import]:
        """Extract all import statements."""
        pass

    @abstractmethod
    def parse_functions(self, source: str) -> list[Function]:
        """Extract all function definitions."""
        pass

    @abstractmethod
    def parse_classes(self, source: str) -> list[Class]:
        """Extract all class definitions."""
        pass
```

### Parser Registry

```python
# devilmcp/parsers/__init__.py
from pathlib import Path
from typing import Optional
from .base import CodeParser
from .python_parser import PythonParser
from .javascript_parser import JavaScriptParser
from .typescript_parser import TypeScriptParser

PARSERS: dict[str, CodeParser] = {
    '.py': PythonParser(),
    '.js': JavaScriptParser(),
    '.jsx': JavaScriptParser(),
    '.ts': TypeScriptParser(),
    '.tsx': TypeScriptParser(),
}

def get_parser(file_path: str) -> Optional[CodeParser]:
    """Get appropriate parser for file extension."""
    ext = Path(file_path).suffix.lower()
    return PARSERS.get(ext)

def parse_file(file_path: str, source: str) -> dict:
    """Parse a file and return all extracted info."""
    parser = get_parser(file_path)
    if not parser:
        return {'imports': [], 'functions': [], 'classes': []}

    return {
        'imports': parser.parse_imports(source),
        'functions': parser.parse_functions(source),
        'classes': parser.parse_classes(source),
    }
```

### JavaScript Parser Example

```python
# devilmcp/parsers/javascript_parser.py
import tree_sitter_javascript as ts_js
from tree_sitter import Language, Parser
from .base import CodeParser, Import, Function

class JavaScriptParser(CodeParser):
    def __init__(self):
        self.language = Language(ts_js.language())
        self.parser = Parser(self.language)

    def parse_imports(self, source: str) -> list[Import]:
        tree = self.parser.parse(bytes(source, 'utf8'))
        imports = []

        # Query for import declarations
        query = self.language.query("""
            (import_statement
                source: (string) @source
            ) @import
        """)

        for match in query.matches(tree.root_node):
            for capture in match.captures:
                if capture[1] == 'source':
                    module = capture[0].text.decode().strip('\'"')
                    imports.append(Import(
                        module=module,
                        names=[],  # Could extract named imports
                        line=capture[0].start_point[0] + 1
                    ))

        return imports

    def parse_functions(self, source: str) -> list[Function]:
        tree = self.parser.parse(bytes(source, 'utf8'))
        functions = []

        query = self.language.query("""
            (function_declaration
                name: (identifier) @name
            ) @func
        """)

        for match in query.matches(tree.root_node):
            node = match.captures[0][0]
            name_node = node.child_by_field_name('name')
            functions.append(Function(
                name=name_node.text.decode() if name_node else 'anonymous',
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                params=[]
            ))

        return functions
```

### Integration with ContextManager

```python
# In context_manager.py
from devilmcp.parsers import parse_file

async def track_file_dependencies(self, file_path: str, project_root: str):
    content = Path(file_path).read_text()
    parsed = parse_file(file_path, content)

    for imp in parsed['imports']:
        # Record dependency with line number
        await self._record_import(file_path, imp.module, imp.line)
```

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `devilmcp/parsers/__init__.py` | CREATE |
| `devilmcp/parsers/base.py` | CREATE |
| `devilmcp/parsers/python_parser.py` | CREATE |
| `devilmcp/parsers/javascript_parser.py` | CREATE |
| `devilmcp/parsers/typescript_parser.py` | CREATE |
| `devilmcp/context_manager.py` | MODIFY - use new parsers |
| `requirements.txt` | MODIFY - add tree-sitter deps |
| `tests/test_parsers.py` | CREATE |

---

## Dependencies

```
tree-sitter>=0.21.0
tree-sitter-python>=0.21.0
tree-sitter-javascript>=0.21.0
tree-sitter-typescript>=0.21.0
```

---

## Success Criteria

- [ ] Python imports parsed correctly (same as current ast behavior)
- [ ] JavaScript imports parsed correctly (better than regex)
- [ ] TypeScript imports parsed correctly
- [ ] Functions detected with line ranges
- [ ] Classes detected with method names
- [ ] Comments and strings ignored (no false positives)
- [ ] Multi-line imports handled correctly
