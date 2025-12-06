"""
Python parser using the built-in ast module.

Note: We intentionally use ast instead of tree-sitter for Python because:
1. ast is always available (stdlib)
2. ast is accurate for valid Python code
3. No binary compatibility issues across platforms
"""

import ast
import logging
from typing import List

from .base import CodeParser, Import, Function, Class

logger = logging.getLogger(__name__)


class PythonParser(CodeParser):
    """Python code parser using the standard library ast module."""

    def parse_imports(self, source: str) -> List[Import]:
        """Extract all import statements from Python source."""
        imports = []
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(Import(
                            module=alias.name,
                            names=[],
                            line=node.lineno
                        ))
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    names = [alias.name for alias in node.names]
                    imports.append(Import(
                        module=module,
                        names=names,
                        line=node.lineno,
                        is_relative=node.level > 0
                    ))
        except SyntaxError as e:
            logger.warning(f"Failed to parse Python source: {e}")
        return imports

    def parse_functions(self, source: str) -> List[Function]:
        """Extract all function definitions from Python source."""
        functions = []
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    params = [arg.arg for arg in node.args.args]
                    functions.append(Function(
                        name=node.name,
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        params=params
                    ))
        except SyntaxError as e:
            logger.warning(f"Failed to parse Python source: {e}")
        return functions

    def parse_classes(self, source: str) -> List[Class]:
        """Extract all class definitions from Python source."""
        classes = []
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    methods = [
                        n.name for n in node.body
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    ]
                    classes.append(Class(
                        name=node.name,
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        methods=methods
                    ))
        except SyntaxError as e:
            logger.warning(f"Failed to parse Python source: {e}")
        return classes
