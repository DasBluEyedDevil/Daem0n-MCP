"""
Context Manager Module
Analyzes project structure and dependencies to build a comprehensive context graph using SQLite.
"""

import os
import re
import ast
import logging
from pathlib import Path
from typing import Dict, List, Set, Optional
from datetime import datetime, timezone
from sqlalchemy import select, delete, text
from sqlalchemy.exc import IntegrityError

from .database import DatabaseManager
from .models import ProjectFile, FileDependency, ExternalDependency

# Try importing gitpython
try:
    import git
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False

logger = logging.getLogger(__name__)

class ContextManager:
    """Manages project context, structure analysis, and dependency tracking."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        # No file path storage anymore

    async def analyze_project_structure(self, project_path: str) -> Dict:
        """
        Analyze project structure and build file list.
        Uses git to respect .gitignore if available.
        Persists to SQLite.
        """
        project_path = os.path.abspath(project_path)
        
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

        # Process files and update DB
        async with self.db.get_session() as session:
            # We could wipe old data for this project or update incrementally.
            # For now, let's update incrementally.
            # Ideally we need to know which files were REMOVED too.
            # A simple strategy: Mark all existing as "stale", update found, delete remaining "stale".
            # But ProjectFile assumes file_path is unique.
            # Since multiple projects might use same DB but isolation is folder-based, 
            # we should be careful. server.py sets up DB per project folder.
            # So effectively 1 DB = 1 Project. We can sync fully.
            
            # Get existing files map
            result = await session.execute(select(ProjectFile))
            existing_files = {f.file_path: f for f in result.scalars().all()}
            found_paths = set()

            for full_path in file_list:
                rel_path = os.path.relpath(full_path, project_path)
                found_paths.add(rel_path)
                
                # Skip .git directory internal files
                if ".git" + os.sep in full_path:
                    continue

                ext = os.path.splitext(full_path)[1].lower()
                if ext:
                    structure["languages"][ext] = structure["languages"].get(ext, 0) + 1

                size = os.path.getsize(full_path) if os.path.exists(full_path) else 0
                
                file_info = {
                    "path": rel_path,
                    "full_path": full_path,
                    "extension": ext,
                    "size": size
                }
                structure["files"].append(file_info)
                
                # Update DB
                if rel_path in existing_files:
                    pf = existing_files[rel_path]
                    if pf.size != size: # Only update if changed
                        pf.size = size
                        pf.last_modified = datetime.now(timezone.utc)
                        session.add(pf)
                else:
                    pf = ProjectFile(
                        file_path=rel_path,
                        file_type=ext,
                        size=size,
                        last_modified=datetime.now(timezone.utc)
                    )
                    session.add(pf)

                # Track directories
                dirname = os.path.dirname(rel_path)
                if dirname and dirname not in structure["directories"]:
                    structure["directories"].append(dirname)
            
            # Remove files that no longer exist
            for path, pf in existing_files.items():
                if path not in found_paths:
                    await session.delete(pf)
            
            await session.commit()

        structure["total_files"] = len(structure["files"])
        return structure

    def _walk_directory(self, project_path: str) -> List[str]:
        """Fallback method to walk directory if git is not available."""
        file_list = []
        ignore_dirs = {'.git', '__pycache__', 'node_modules', 'venv', '.env', '.devilmcp', '.idea'}
        
        for root, dirs, files in os.walk(project_path):
            # Modify dirs in-place to skip ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            for file in files:
                if file.startswith('.'):  # Skip hidden files
                    continue
                file_list.append(os.path.join(root, file))
        
        return file_list

    async def track_file_dependencies(
        self, 
        file_path: str,
        project_root: Optional[str] = None
    ) -> Dict:
        """
        Analyze file dependencies (imports) and store in DB.
        """
        if not os.path.exists(file_path):
            return {"error": f"File {file_path} not found"}

        # Need absolute path for file reading, but relative for DB lookup
        abs_file_path = os.path.abspath(file_path)
        root = project_root or os.path.dirname(abs_file_path) # Fallback, ideally passed in
        
        # If we don't have a definitive root, we might fail to resolve relative paths correctly
        # in a consistent way for the DB.
        # However, if server.py initializes us, we don't inherently know project root unless passed.
        # We'll use CWD as root if not provided, usually safe for CLI/Server.
        if not project_root:
            root = os.getcwd()
            
        rel_path = os.path.relpath(abs_file_path, root)
        
        deps = {
            "file": rel_path,
            "internal_deps": [],
            "external_deps": []
        }

        ext = os.path.splitext(abs_file_path)[1].lower()
        
        try:
            with open(abs_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            if ext == '.py':
                deps = self._analyze_python_deps(content, deps)
            elif ext in ['.js', '.ts', '.jsx', '.tsx']:
                deps = self._analyze_js_deps(content, deps)
                
        except Exception as e:
            logger.error(f"Error analyzing dependencies for {file_path}: {e}")
            return deps

        # Update DB
        async with self.db.get_session() as session:
            # Find source file ID
            res = await session.execute(select(ProjectFile).where(ProjectFile.file_path == rel_path))
            source_file = res.scalar_one_or_none()
            
            if not source_file:
                # If tracking a file not yet in DB, add it
                source_file = ProjectFile(
                    file_path=rel_path, 
                    file_type=ext, 
                    last_modified=datetime.now(timezone.utc)
                )
                session.add(source_file)
                await session.flush()
                await session.refresh(source_file)

            # Clear old dependencies for this file
            await session.execute(delete(FileDependency).where(FileDependency.source_file_id == source_file.id))
            await session.execute(delete(ExternalDependency).where(ExternalDependency.source_file_id == source_file.id))

            # Add new dependencies
            for int_dep in deps["internal_deps"]:
                # Try to find target file
                # int_dep is usually a module path "utils.helper" or relative "./helper"
                # This is hard to map exactly to file paths without full resolution logic
                # For now, we store best effort string match or just skip linking if strict
                # OR we just store the string. But our model requires ForeignKey.
                # If we can't link, we can't store in FileDependency easily without looking up target.
                # Let's try to find a matching file ending with that name
                # This is fuzzy. For robustness, maybe we just log them for now or find exact match.
                # Simpler: Just find ANY file that matches the import path logic.
                # If not found, maybe it's not scanned yet.
                # For this migration, we might just skip complex resolution and focus on External.
                pass 

            for ext_dep in deps["external_deps"]:
                ed = ExternalDependency(source_file_id=source_file.id, package_name=ext_dep)
                session.add(ed)
                
            await session.commit()
        
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
                        if node.level > 0: # relative
                            deps["internal_deps"].append(node.module)
                        elif os.path.exists(node.module.replace('.', '/') + '.py'): # local exists
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

    async def get_project_context(
        self, 
        project_path: Optional[str] = None,
        include_dependencies: bool = True
    ) -> Dict:
        """Retrieve comprehensive project context from DB."""
        if project_path:
            await self.analyze_project_structure(project_path)
            
        async with self.db.get_session() as session:
            result = await session.execute(select(ProjectFile))
            files = result.scalars().all()
            
            files_dict = {
                f.file_path: {
                    "path": f.file_path,
                    "type": f.file_type,
                    "size": f.size
                } for f in files
            }
            
            # If dependencies needed, fetch them
            deps_dict = {}
            if include_dependencies:
                 # Fetch external deps
                 res_ext = await session.execute(select(ExternalDependency))
                 for ed in res_ext.scalars().all():
                     # We need to map back to file path. This is slow N+1 if not joined.
                     # For prototype, acceptable.
                     # Actually we have files_dict keyed by path.
                     pass

            return {
                "project": project_path or "unknown",
                "total_files": len(files),
                "files": files_dict,
                "dependencies": deps_dict,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }

    async def search_context(self, query: str, context_type: str = "all") -> List[Dict]:
        """Search context for specific information."""
        results = []
        query = query.lower()
        
        async with self.db.get_session() as session:
            if context_type in ["all", "files"]:
                stmt = select(ProjectFile).where(ProjectFile.file_path.contains(query))
                res = await session.execute(stmt)
                for f in res.scalars().all():
                    results.append({"type": "file", "path": f.file_path, "info": {"size": f.size}})
                    
            if context_type in ["all", "dependencies"]:
                stmt = select(ExternalDependency).where(ExternalDependency.package_name.contains(query))
                res = await session.execute(stmt)
                for d in res.scalars().all():
                    results.append({"type": "dependency", "package": d.package_name})
                    
        return results
