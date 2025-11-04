"""
Context Manager Module
Provides comprehensive project context tracking and retrieval capabilities.
"""

import os
import json
import ast
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages project context, file relationships, and architectural understanding."""

    def __init__(self, storage_path: str = "./storage"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self.context_file = self.storage_path / "project_context.json"
        self.context_data = self._load_context()

    def _load_context(self) -> Dict:
        """Load existing context data or create new."""
        if self.context_file.exists():
            try:
                with open(self.context_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading context: {e}")

        return {
            "projects": {},
            "file_map": {},
            "dependencies": {},
            "last_updated": None
        }

    def _save_context(self):
        """Persist context data to storage."""
        self.context_data["last_updated"] = datetime.now().isoformat()
        try:
            with open(self.context_file, 'w') as f:
                json.dump(self.context_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving context: {e}")

    def analyze_project_structure(self, project_path: str) -> Dict:
        """
        Analyze entire project structure and create comprehensive context map.

        Args:
            project_path: Root path of the project to analyze

        Returns:
            Dictionary containing project structure, file types, and organization
        """
        project_path = Path(project_path).resolve()

        if not project_path.exists():
            return {"error": f"Project path does not exist: {project_path}"}

        structure = {
            "root": str(project_path),
            "name": project_path.name,
            "directories": [],
            "files": {},
            "file_types": {},
            "total_files": 0,
            "total_lines": 0,
            "languages": set(),
            "analyzed_at": datetime.now().isoformat()
        }

        # Ignore common directories
        ignore_dirs = {'.git', '__pycache__', 'node_modules', 'venv', 'env', '.venv',
                      'dist', 'build', '.next', '.nuxt', 'target'}

        for root, dirs, files in os.walk(project_path):
            # Filter ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs]

            rel_root = Path(root).relative_to(project_path)
            structure["directories"].append(str(rel_root))

            for file in files:
                file_path = Path(root) / file
                rel_path = file_path.relative_to(project_path)

                # Get file extension
                ext = file_path.suffix
                if ext:
                    structure["file_types"][ext] = structure["file_types"].get(ext, 0) + 1
                    structure["languages"].add(self._detect_language(ext))

                # Count lines for text files
                try:
                    if self._is_text_file(file_path):
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = len(f.readlines())
                            structure["total_lines"] += lines

                            structure["files"][str(rel_path)] = {
                                "type": ext,
                                "lines": lines,
                                "size": file_path.stat().st_size,
                                "language": self._detect_language(ext)
                            }
                except Exception as e:
                    logger.debug(f"Could not read {rel_path}: {e}")

                structure["total_files"] += 1

        structure["languages"] = list(structure["languages"])

        # Store in context
        self.context_data["projects"][str(project_path)] = structure
        self._save_context()

        return structure

    def track_file_dependencies(self, file_path: str, project_root: Optional[str] = None) -> Dict:
        """
        Analyze file dependencies including imports, requires, and relationships.

        Args:
            file_path: Path to file to analyze
            project_root: Root of project for relative path resolution

        Returns:
            Dictionary of dependencies and relationships
        """
        file_path = Path(file_path).resolve()

        if not file_path.exists():
            return {"error": f"File does not exist: {file_path}"}

        dependencies = {
            "file": str(file_path),
            "imports": [],
            "exports": [],
            "internal_deps": [],
            "external_deps": [],
            "analyzed_at": datetime.now().isoformat()
        }

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')

            # Python files
            if file_path.suffix == '.py':
                dependencies.update(self._analyze_python_deps(content, file_path, project_root))

            # JavaScript/TypeScript files
            elif file_path.suffix in ['.js', '.jsx', '.ts', '.tsx', '.mjs']:
                dependencies.update(self._analyze_js_deps(content, file_path, project_root))

            # Store in context
            self.context_data["dependencies"][str(file_path)] = dependencies
            self._save_context()

        except Exception as e:
            dependencies["error"] = str(e)
            logger.error(f"Error analyzing dependencies for {file_path}: {e}")

        return dependencies

    def _analyze_python_deps(self, content: str, file_path: Path, project_root: Optional[str]) -> Dict:
        """Analyze Python file dependencies."""
        deps = {"imports": [], "internal_deps": [], "external_deps": []}

        try:
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        deps["imports"].append(alias.name)
                        if self._is_internal_module(alias.name, project_root):
                            deps["internal_deps"].append(alias.name)
                        else:
                            deps["external_deps"].append(alias.name)

                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        full_import = f"{module}.{alias.name}" if module else alias.name
                        deps["imports"].append(full_import)

                        if self._is_internal_module(module, project_root):
                            deps["internal_deps"].append(full_import)
                        else:
                            deps["external_deps"].append(full_import)

        except Exception as e:
            logger.debug(f"Error parsing Python AST: {e}")

        return deps

    def _analyze_js_deps(self, content: str, file_path: Path, project_root: Optional[str]) -> Dict:
        """Analyze JavaScript/TypeScript file dependencies."""
        import re

        deps = {"imports": [], "internal_deps": [], "external_deps": []}

        # Match ES6 imports
        import_pattern = r'import\s+(?:{[^}]+}|\*\s+as\s+\w+|\w+)\s+from\s+[\'"]([^\'"]+)[\'"]'
        # Match require statements
        require_pattern = r'require\s*\([\'"]([^\'"]+)[\'"]\)'

        for match in re.finditer(import_pattern, content):
            module = match.group(1)
            deps["imports"].append(module)

            if module.startswith('.') or module.startswith('/'):
                deps["internal_deps"].append(module)
            else:
                deps["external_deps"].append(module)

        for match in re.finditer(require_pattern, content):
            module = match.group(1)
            deps["imports"].append(module)

            if module.startswith('.') or module.startswith('/'):
                deps["internal_deps"].append(module)
            else:
                deps["external_deps"].append(module)

        return deps

    def _is_internal_module(self, module: str, project_root: Optional[str]) -> bool:
        """Determine if module is internal to the project."""
        if not module:
            return False

        # Relative imports are internal
        if module.startswith('.'):
            return True

        # Check if module exists in project
        if project_root:
            project_path = Path(project_root)
            module_path = project_path / module.replace('.', '/')
            return module_path.exists() or (module_path.parent / f"{module_path.name}.py").exists()

        return False

    def _detect_language(self, ext: str) -> str:
        """Detect programming language from file extension."""
        lang_map = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.jsx': 'JavaScript',
            '.ts': 'TypeScript',
            '.tsx': 'TypeScript',
            '.java': 'Java',
            '.cpp': 'C++',
            '.c': 'C',
            '.h': 'C/C++',
            '.cs': 'C#',
            '.go': 'Go',
            '.rs': 'Rust',
            '.rb': 'Ruby',
            '.php': 'PHP',
            '.swift': 'Swift',
            '.kt': 'Kotlin',
            '.scala': 'Scala',
            '.html': 'HTML',
            '.css': 'CSS',
            '.scss': 'SCSS',
            '.vue': 'Vue',
            '.json': 'JSON',
            '.yml': 'YAML',
            '.yaml': 'YAML',
            '.md': 'Markdown',
            '.sh': 'Shell',
            '.sql': 'SQL'
        }
        return lang_map.get(ext.lower(), 'Unknown')

    def _is_text_file(self, file_path: Path) -> bool:
        """Check if file is likely a text file."""
        text_extensions = {
            '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.cpp', '.c', '.h', '.cs',
            '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala', '.html', '.css',
            '.scss', '.vue', '.json', '.yml', '.yaml', '.md', '.txt', '.sh', '.sql',
            '.xml', '.toml', '.ini', '.cfg', '.conf'
        }
        return file_path.suffix.lower() in text_extensions

    def get_project_context(self, project_path: Optional[str] = None,
                           include_dependencies: bool = True) -> Dict:
        """
        Retrieve comprehensive project context.

        Args:
            project_path: Optional specific project to get context for
            include_dependencies: Whether to include dependency information

        Returns:
            Complete context information for the project(s)
        """
        if project_path:
            project_path = str(Path(project_path).resolve())
            context = {
                "project": self.context_data["projects"].get(project_path, {}),
                "last_updated": self.context_data["last_updated"]
            }

            if include_dependencies:
                # Get all dependencies for files in this project
                project_deps = {
                    path: deps for path, deps in self.context_data["dependencies"].items()
                    if path.startswith(project_path)
                }
                context["dependencies"] = project_deps

            return context
        else:
            # Return all context
            return self.context_data

    def search_context(self, query: str, context_type: str = "all") -> List[Dict]:
        """
        Search context data for specific information.

        Args:
            query: Search query string
            context_type: Type of context to search ('files', 'dependencies', 'all')

        Returns:
            List of matching context entries
        """
        results = []
        query_lower = query.lower()

        if context_type in ["files", "all"]:
            for project_path, project_data in self.context_data["projects"].items():
                for file_path, file_data in project_data.get("files", {}).items():
                    if query_lower in file_path.lower() or query_lower in file_data.get("language", "").lower():
                        results.append({
                            "type": "file",
                            "project": project_path,
                            "path": file_path,
                            "data": file_data
                        })

        if context_type in ["dependencies", "all"]:
            for file_path, deps in self.context_data["dependencies"].items():
                for imp in deps.get("imports", []):
                    if query_lower in imp.lower():
                        results.append({
                            "type": "dependency",
                            "file": file_path,
                            "import": imp,
                            "data": deps
                        })

        return results
