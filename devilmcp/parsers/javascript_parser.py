"""
JavaScript parser using tree-sitter for accurate AST analysis.

If tree-sitter is not installed, returns empty results with a warning.
We don't maintain regex fallbacks - they break on edge cases and are not worth it.
"""

import logging
from typing import List, Set

from .base import CodeParser, Import, Function, Class

logger = logging.getLogger(__name__)


class JavaScriptParser(CodeParser):
    """JavaScript code parser using tree-sitter."""

    def __init__(self):
        self._parser = None
        self._language = None
        self._initialized = False
        self._available = False

    def _ensure_initialized(self) -> bool:
        """Lazily initialize tree-sitter parser."""
        if self._initialized:
            return self._available

        self._initialized = True
        try:
            import tree_sitter_javascript as ts_js
            from tree_sitter import Language, Parser

            self._language = Language(ts_js.language())
            self._parser = Parser(self._language)
            self._available = True
            return True
        except ImportError:
            logger.warning(
                "tree-sitter-javascript not installed. JS dependency analysis unavailable. "
                "Install with: pip install tree-sitter tree-sitter-javascript"
            )
            self._available = False
            return False

    def _walk_tree(self, node, node_types: Set[str], results: list):
        """Recursively walk tree collecting nodes of specific types."""
        if node.type in node_types:
            results.append(node)
        for child in node.children:
            self._walk_tree(child, node_types, results)

    def parse_imports(self, source: str) -> List[Import]:
        """Extract all import statements from JavaScript source."""
        if not self._ensure_initialized():
            return []

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

    def parse_functions(self, source: str) -> List[Function]:
        """Extract all function definitions from JavaScript source."""
        if not self._ensure_initialized():
            return []

        tree = self._parser.parse(bytes(source, 'utf8'))
        functions = []

        func_nodes = []
        self._walk_tree(tree.root_node, {'function_declaration', 'method_definition'}, func_nodes)

        for node in func_nodes:
            name_node = node.child_by_field_name('name')
            params_node = node.child_by_field_name('parameters')

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

            functions.append(Function(
                name=name_node.text.decode() if name_node else 'anonymous',
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                params=params
            ))

        return functions

    def parse_classes(self, source: str) -> List[Class]:
        """Extract all class definitions from JavaScript source."""
        if not self._ensure_initialized():
            return []

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
