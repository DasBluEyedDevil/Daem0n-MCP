"""
JavaScript parser with tree-sitter support and regex fallback.

Uses tree-sitter when available for accurate AST analysis.
Falls back to regex patterns when tree-sitter is not installed.
"""

import re
import logging
from typing import List, Set, Optional

from .base import CodeParser, Import, Function, Class

logger = logging.getLogger(__name__)


class JavaScriptParser(CodeParser):
    """JavaScript code parser with tree-sitter and regex fallback."""

    def __init__(self):
        self._parser = None
        self._language = None
        self._initialized = False
        self._tree_sitter_available = False

    def _ensure_initialized(self) -> bool:
        """Lazily initialize tree-sitter parser."""
        if self._initialized:
            return self._tree_sitter_available

        self._initialized = True
        try:
            import tree_sitter_javascript as ts_js
            from tree_sitter import Language, Parser

            self._language = Language(ts_js.language())
            self._parser = Parser(self._language)
            self._tree_sitter_available = True
            return True
        except ImportError:
            logger.info("tree-sitter-javascript not available, using regex fallback")
            self._tree_sitter_available = False
            return False

    def _walk_tree(self, node, node_types: Set[str], results: list):
        """Recursively walk tree collecting nodes of specific types."""
        if node.type in node_types:
            results.append(node)
        for child in node.children:
            self._walk_tree(child, node_types, results)

    def parse_imports(self, source: str) -> List[Import]:
        """Extract all import statements from JavaScript source."""
        if self._ensure_initialized():
            return self._parse_imports_tree_sitter(source)
        return self._parse_imports_regex(source)

    def _parse_imports_tree_sitter(self, source: str) -> List[Import]:
        """Parse imports using tree-sitter AST."""
        tree = self._parser.parse(bytes(source, 'utf8'))
        imports = []

        import_nodes = []
        self._walk_tree(tree.root_node, {'import_statement', 'call_expression'}, import_nodes)

        for node in import_nodes:
            if node.type == 'import_statement':
                source_node = None
                names = []

                for child in node.children:
                    if child.type == 'string':
                        source_node = child
                    elif child.type == 'import_clause':
                        for clause_child in child.children:
                            if clause_child.type == 'identifier':
                                names.append(clause_child.text.decode())
                            elif clause_child.type == 'named_imports':
                                for import_spec in clause_child.children:
                                    if import_spec.type == 'import_specifier':
                                        name = import_spec.child_by_field_name('name')
                                        if name:
                                            names.append(name.text.decode())

                if source_node:
                    module = source_node.text.decode().strip('\'"')
                    imports.append(Import(
                        module=module,
                        names=names,
                        line=node.start_point[0] + 1,
                        is_relative=module.startswith('.')
                    ))

            elif node.type == 'call_expression':
                func = node.child_by_field_name('function')
                args = node.child_by_field_name('arguments')

                if func and func.type == 'identifier' and func.text.decode() == 'require':
                    if args:
                        for arg in args.children:
                            if arg.type == 'string':
                                module = arg.text.decode().strip('\'"')
                                imports.append(Import(
                                    module=module,
                                    names=[],
                                    line=node.start_point[0] + 1,
                                    is_relative=module.startswith('.')
                                ))
                                break

        return imports

    def _parse_imports_regex(self, source: str) -> List[Import]:
        """Fallback: Parse imports using regex patterns."""
        imports = []

        # ES6 imports: import ... from '...'
        es6_pattern = re.compile(
            r"import\s+(?:(\w+)\s*,?\s*)?(?:\{([^}]*)\})?\s*(?:from\s+)?['\"]([^'\"]+)['\"]",
            re.MULTILINE
        )
        for match in es6_pattern.finditer(source):
            default_import = match.group(1)
            named_imports = match.group(2)
            module = match.group(3)

            names = []
            if default_import:
                names.append(default_import)
            if named_imports:
                names.extend([n.strip().split(' as ')[0].strip()
                             for n in named_imports.split(',') if n.strip()])

            line = source[:match.start()].count('\n') + 1
            imports.append(Import(
                module=module,
                names=names,
                line=line,
                is_relative=module.startswith('.')
            ))

        # CommonJS require: require('...')
        require_pattern = re.compile(r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)")
        for match in require_pattern.finditer(source):
            module = match.group(1)
            line = source[:match.start()].count('\n') + 1
            imports.append(Import(
                module=module,
                names=[],
                line=line,
                is_relative=module.startswith('.')
            ))

        return imports

    def parse_functions(self, source: str) -> List[Function]:
        """Extract all function definitions from JavaScript source."""
        if self._ensure_initialized():
            return self._parse_functions_tree_sitter(source)
        return self._parse_functions_regex(source)

    def _parse_functions_tree_sitter(self, source: str) -> List[Function]:
        """Parse functions using tree-sitter AST."""
        tree = self._parser.parse(bytes(source, 'utf8'))
        functions = []

        func_nodes = []
        self._walk_tree(tree.root_node, {'function_declaration', 'method_definition'}, func_nodes)

        for node in func_nodes:
            name_node = node.child_by_field_name('name')
            params_node = node.child_by_field_name('parameters')

            params = self._extract_params(params_node)

            functions.append(Function(
                name=name_node.text.decode() if name_node else 'anonymous',
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                params=params
            ))

        return functions

    def _parse_functions_regex(self, source: str) -> List[Function]:
        """Fallback: Parse functions using regex patterns."""
        functions = []

        # Match function declarations and expressions
        func_pattern = re.compile(
            r"(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>))\s*\(([^)]*)\)",
            re.MULTILINE
        )

        for match in func_pattern.finditer(source):
            name = match.group(1) or match.group(2) or 'anonymous'
            params_str = match.group(3) or ""
            params = [p.strip().split('=')[0].strip()
                     for p in params_str.split(',') if p.strip()]

            line = source[:match.start()].count('\n') + 1
            functions.append(Function(
                name=name,
                start_line=line,
                end_line=line,  # Can't determine end line with regex
                params=params
            ))

        return functions

    def _extract_params(self, params_node) -> List[str]:
        """Extract parameter names from a parameters node."""
        params = []
        if params_node:
            for child in params_node.children:
                if child.type == 'identifier':
                    params.append(child.text.decode())
                elif child.type in ('assignment_pattern', 'rest_pattern'):
                    left = child.child_by_field_name('left')
                    if left is None and child.children:
                        left = child.children[0]
                    if left and left.type == 'identifier':
                        params.append(left.text.decode())
        return params

    def parse_classes(self, source: str) -> List[Class]:
        """Extract all class definitions from JavaScript source."""
        if self._ensure_initialized():
            return self._parse_classes_tree_sitter(source)
        return self._parse_classes_regex(source)

    def _parse_classes_tree_sitter(self, source: str) -> List[Class]:
        """Parse classes using tree-sitter AST."""
        tree = self._parser.parse(bytes(source, 'utf8'))
        classes = []

        class_nodes = []
        self._walk_tree(tree.root_node, {'class_declaration'}, class_nodes)

        for node in class_nodes:
            name_node = node.child_by_field_name('name')
            body_node = node.child_by_field_name('body')

            methods = []
            if body_node:
                for child in body_node.children:
                    if child.type == 'method_definition':
                        method_name = child.child_by_field_name('name')
                        if method_name:
                            methods.append(method_name.text.decode())

            classes.append(Class(
                name=name_node.text.decode() if name_node else 'unknown',
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                methods=methods
            ))

        return classes

    def _parse_classes_regex(self, source: str) -> List[Class]:
        """Fallback: Parse classes using regex patterns."""
        classes = []

        # Match class declarations
        class_pattern = re.compile(r"class\s+(\w+)(?:\s+extends\s+\w+)?\s*\{", re.MULTILINE)

        for match in class_pattern.finditer(source):
            name = match.group(1)
            line = source[:match.start()].count('\n') + 1

            # Try to find methods within the class (simple heuristic)
            methods = []
            class_start = match.end()
            # Find matching closing brace (simplified - doesn't handle nested braces)
            brace_count = 1
            pos = class_start
            class_body = ""
            while pos < len(source) and brace_count > 0:
                if source[pos] == '{':
                    brace_count += 1
                elif source[pos] == '}':
                    brace_count -= 1
                if brace_count > 0:
                    class_body += source[pos]
                pos += 1

            # Extract method names from class body
            method_pattern = re.compile(r"(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{")
            for method_match in method_pattern.finditer(class_body):
                method_name = method_match.group(1)
                if method_name not in ('if', 'for', 'while', 'switch', 'catch'):
                    methods.append(method_name)

            classes.append(Class(
                name=name,
                start_line=line,
                end_line=line,  # Can't determine end line accurately with regex
                methods=methods
            ))

        return classes
