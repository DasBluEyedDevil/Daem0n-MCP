"""
Context Manager Module
Analyzes project structure and dependencies to build a comprehensive context graph.
"""

import os
import re
import ast
import json
import logging
from pathlib import Path
from typing import Dict, List, Set, Optional
from datetime import datetime

# Try importing gitpython
try:
    import git
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages project context, structure analysis, and dependency tracking."""

    def __init__(self, storage_path: str = "./storage"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self.context_file = self.storage_path / "project_context.json"
        self.context = self._load_context()

    def _load_context(self) -> Dict:
        """Load existing context data."""
        if self.context_file.exists():
            try:
                with open(self.context_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading context: {e}")
        
        return {
            "project_root": None,
            "files": {},
            "dependencies": {},
            "last_updated": None
        }

    def _save_context(self):
        """Persist context data to storage."""
        try:
            with open(self.context_file, 'w') as f:
                json.dump(self.context, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving context: {e}")

    def analyze_project_structure(self, project_path: str) -> Dict:
        """
        Analyze project structure and build file list.
        Uses git to respect .gitignore if available.

        Args:
            project_path: Path to the project root

        Returns:
            Structure analysis with file list and stats
        """
        project_path = os.path.abspath(project_path)
        self.context["project_root"] = project_path
        
        structure = {
            "root": project_path,
            "files": [],
            "directories": [],
            "languages": {},
            "total_files": 0
        }

        file_list = []

        # Try using git first
        if GIT_AVAILABLE:
            try:
                repo = git.Repo(project_path, search_parent_directories=True)
                # Get tracked files
                git_files = repo.git.ls_files().split('\n')
                # Filter out empty strings
                file_list = [os.path.join(repo.working_dir, f) for f in git_files if f]
                logger.info(f"Used git to find {len(file_list)} tracked files")
            except (git.InvalidGitRepositoryError, Exception) as e:
                logger.warning(f"Git lookup failed ({e}), falling back to os.walk")
                file_list = self._walk_directory(project_path)
        else:
            file_list = self._walk_directory(project_path)

        # Process the file list
        for full_path in file_list:
            rel_path = os.path.relpath(full_path, project_path)
            
            # Skip .git directory internal files if they slipped through
            if ".git" + os.sep in full_path:
                continue

            # Determine language/type
            ext = os.path.splitext(full_path)[1].lower()
            if ext:
                structure["languages"][ext] = structure["languages"].get(ext, 0) + 1

            file_info = {
                "path": rel_path,
                "full_path": full_path,
                "extension": ext,
                "size": os.path.getsize(full_path) if os.path.exists(full_path) else 0
            }
            
            structure["files"].append(file_info)
            
            # Update internal state
            self.context["files"][rel_path] = file_info

            # Add directory
            dirname = os.path.dirname(rel_path)
            if dirname and dirname not in structure["directories"]:
                structure["directories"].append(dirname)

        structure["total_files"] = len(structure["files"])
        self._save_context()
        
        return structure

    def _walk_directory(self, project_path: str) -> List[str]:
        """Fallback method to walk directory if git is not available."""
        file_list = []
        ignore_dirs = {'.git', '__pycache__', 'node_modules', 'venv', '.env'}
        
        for root, dirs, files in os.walk(project_path):
            # Modify dirs in-place to skip ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            for file in files:
                if file.startswith('.'):  # Skip hidden files
                    continue
                file_list.append(os.path.join(root, file))
        
        return file_list

    def track_file_dependencies(
        self, 
        file_path: str,
        project_root: Optional[str] = None
    ) -> Dict:
        """
        Analyze file dependencies (imports).

        Args:
            file_path: Path to the file
            project_root: Project root for relative resolution

        Returns:
            Dependency information
        """
        if not os.path.exists(file_path):
            return {"error": f"File {file_path} not found"}

        root = project_root or self.context.get("project_root") or os.path.dirname(file_path)
        rel_path = os.path.relpath(file_path, root)
        
        deps = {
            "file": rel_path,
            "internal_deps": [],
            "external_deps": []
        }

        ext = os.path.splitext(file_path)[1].lower()
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            if ext == '.py':
                deps = self._analyze_python_deps(content, deps)
            elif ext in ['.js', '.ts', '.jsx', '.tsx']:
                deps = self._analyze_js_deps(content, deps)
                
        except Exception as e:
            logger.error(f"Error analyzing dependencies for {file_path}: {e}")

        # Update context
        self.context["dependencies"][rel_path] = deps
        self._save_context()
        
        return deps

    def _analyze_python_deps(self, content: str, deps: Dict) -> Dict:
        """Analyze Python imports using AST."""
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        deps["external_deps"].append(name.name.split('.')[0])
                        
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        # Heuristic: relative imports or local modules are internal
                        if node.level > 0 or os.path.exists(node.module.replace('.', '/') + '.py'):
                            deps["internal_deps"].append(node.module)
                        else:
                            deps["external_deps"].append(node.module.split('.')[0])
                            
        except SyntaxError:
            pass # Skip invalid syntax
            
        return deps

    def _analyze_js_deps(self, content: str, deps: Dict) -> Dict:
        """Analyze JS/TS imports using Regex."""
        # Match: import ... from '...' or require('...')
        import_pattern = re.compile(r'(?:import\s+.*\s+from\s+|require\(\s*)[\'"]([^\'"]+)[\'"]')
        
        matches = import_pattern.findall(content)
        
        for match in matches:
            if match.startswith('.'):
                deps["internal_deps"].append(match)
            else:
                deps["external_deps"].append(match.split('/')[0])
                
        return deps

    def get_project_context(
        self, 
        project_path: Optional[str] = None,
        include_dependencies: bool = True
    ) -> Dict:
        """Retrieve comprehensive project context."""
        # Refresh structure if path provided
        if project_path:
            self.analyze_project_structure(project_path)
            
        return {
            "project": self.context.get("project_root"),
            "total_files": len(self.context.get("files", {})),
            "files": self.context.get("files", {}) if include_dependencies else {},
            "dependencies": self.context.get("dependencies", {}) if include_dependencies else {},
            "last_updated": datetime.now().isoformat()
        }

    def search_context(self, query: str, context_type: str = "all") -> List[Dict]:
        """Search context for specific information."""
        results = []
        query = query.lower()
        
        if context_type in ["all", "files"]:
            for path, info in self.context.get("files", {}).items():
                if query in path.lower():
                    results.append({"type": "file", "path": path, "info": info})
                    
        if context_type in ["all", "dependencies"]:
            for path, deps in self.context.get("dependencies", {}).items():
                if query in str(deps).lower():
                    results.append({"type": "dependency", "path": path, "deps": deps})
                    
        return results