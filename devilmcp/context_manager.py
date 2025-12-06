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
from .models import ProjectFile, FileDependency, ExternalDependency, Task, Decision

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

    async def analyze_project_structure(
        self,
        project_path: str,
        force_rescan: bool = False
    ) -> Dict:
        """
        Analyze project structure with incremental scanning.

        Only re-scans files that have changed (based on mtime) unless force_rescan=True.
        Uses git to respect .gitignore if available.
        """
        project_path = os.path.abspath(project_path)

        structure = {
            "root": project_path,
            "files": [],
            "directories": [],
            "languages": {},
            "total_files": 0,
            "files_updated": 0,
            "files_added": 0,
            "files_removed": 0
        }

        file_list = []

        # Try using git first
        if GIT_AVAILABLE:
            try:
                repo = git.Repo(project_path, search_parent_directories=True)
                git_files = repo.git.ls_files().split('\n')
                file_list = [os.path.join(repo.working_dir, f) for f in git_files if f]
                logger.info(f"Used git to find {len(file_list)} tracked files")
            except (git.InvalidGitRepositoryError, Exception) as e:
                logger.warning(f"Git lookup failed ({e}), falling back to os.walk")
                file_list = self._walk_directory(project_path)
        else:
            file_list = self._walk_directory(project_path)

        async with self.db.get_session() as session:
            # Get existing files map with their last_modified timestamps
            result = await session.execute(select(ProjectFile))
            existing_files = {f.file_path: f for f in result.scalars().all()}
            found_paths = set()

            for full_path in file_list:
                rel_path = os.path.relpath(full_path, project_path)
                found_paths.add(rel_path)

                if ".git" + os.sep in full_path:
                    continue

                ext = os.path.splitext(full_path)[1].lower()
                if ext:
                    structure["languages"][ext] = structure["languages"].get(ext, 0) + 1

                # Get file mtime for incremental scanning
                try:
                    stat = os.stat(full_path)
                    file_mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                    size = stat.st_size
                except OSError:
                    continue  # File disappeared

                file_info = {
                    "path": rel_path,
                    "full_path": full_path,
                    "extension": ext,
                    "size": size
                }
                structure["files"].append(file_info)

                # Incremental update: only update if file is new or changed
                if rel_path in existing_files:
                    pf = existing_files[rel_path]
                    db_mtime = pf.last_modified

                    # Compare mtimes - update if file is newer or force_rescan
                    if force_rescan or db_mtime is None or file_mtime > db_mtime:
                        pf.size = size
                        pf.last_modified = file_mtime
                        session.add(pf)
                        structure["files_updated"] += 1
                else:
                    # New file
                    pf = ProjectFile(
                        file_path=rel_path,
                        file_type=ext,
                        size=size,
                        last_modified=file_mtime
                    )
                    session.add(pf)
                    structure["files_added"] += 1

                dirname = os.path.dirname(rel_path)
                if dirname and dirname not in structure["directories"]:
                    structure["directories"].append(dirname)

            # Remove files that no longer exist
            for path, pf in existing_files.items():
                if path not in found_paths:
                    await session.delete(pf)
                    structure["files_removed"] += 1

            await session.commit()

        structure["total_files"] = len(structure["files"])
        logger.info(
            f"Project scan: {structure['total_files']} files, "
            f"{structure['files_added']} added, {structure['files_updated']} updated, "
            f"{structure['files_removed']} removed"
        )
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
                # Resolve internal dependency to a potential file path
                # This is a heuristic: try to find a file that ends with the import path
                # e.g., 'utils.helper' -> 'helper.py' or 'helper/__init__.py'
                
                # Normalize module path to file path components
                # Python: . -> /
                # JS: keep as is if relative
                
                possible_suffixes = []
                if ext == '.py':
                    base_mod = int_dep.replace('.', '/')
                    possible_suffixes = [f"{base_mod}.py", f"{base_mod}/__init__.py"]
                else:
                    # JS/TS: remove ./ or ../
                    clean_path = int_dep.lstrip('./')
                    possible_suffixes = [
                        f"{clean_path}.js", f"{clean_path}.ts", 
                        f"{clean_path}.jsx", f"{clean_path}.tsx",
                        f"{clean_path}/index.js", f"{clean_path}/index.ts"
                    ]

                # Try to find a matching file in the project
                # We search for files ending with one of the suffixes
                target_file = None
                for suffix in possible_suffixes:
                    # We use a LIKE query to find files ending with the suffix
                    # This is not perfect (could match src/foo/bar.py for import bar) but better than nothing
                    stmt = select(ProjectFile).where(ProjectFile.file_path.endswith(suffix))
                    res = await session.execute(stmt)
                    matches = res.scalars().all()
                    
                    # If multiple matches, we might pick the one closest in directory depth or just the first
                    # For now, picking the first exact match or just the first one found
                    if matches:
                        target_file = matches[0]
                        break
                
                if target_file and target_file.id != source_file.id:
                    # Check if dependency already exists to avoid duplicates
                    existing = await session.execute(
                        select(FileDependency).where(
                            (FileDependency.source_file_id == source_file.id) &
                            (FileDependency.target_file_id == target_file.id)
                        )
                    )
                    if not existing.scalar_one_or_none():
                        fd = FileDependency(
                            source_file_id=source_file.id, 
                            target_file_id=target_file.id,
                            dependency_type="import"
                        )
                        session.add(fd)

            for ext_dep in deps["external_deps"]:
                ed = ExternalDependency(source_file_id=source_file.id, package_name=ext_dep)
                session.add(ed)
                
            await session.commit()
        
        return deps

    async def get_focused_context(self, file_path: str) -> Dict:
        """
        Retrieve focused context for a specific file:
        - The file itself
        - Files it imports (outgoing)
        - Files that import it (incoming)
        - External dependencies
        """
        async with self.db.get_session() as session:
            # Find the file
            stmt = select(ProjectFile).where(ProjectFile.file_path.endswith(file_path))
            res = await session.execute(stmt)
            target = res.scalars().first()
            
            if not target:
                return {"error": f"File not found: {file_path}"}
            
            context = {
                "file": {"path": target.file_path, "type": target.file_type, "size": target.size},
                "imports": [],
                "imported_by": [],
                "dependencies": []
            }
            
            # Get outgoing imports (files this file depends on)
            stmt_out = select(ProjectFile).join(
                FileDependency, FileDependency.target_file_id == ProjectFile.id
            ).where(FileDependency.source_file_id == target.id)
            
            res_out = await session.execute(stmt_out)
            for f in res_out.scalars().all():
                context["imports"].append(f.file_path)
                
            # Get incoming imports (files that depend on this file)
            stmt_in = select(ProjectFile).join(
                FileDependency, FileDependency.source_file_id == ProjectFile.id
            ).where(FileDependency.target_file_id == target.id)
            
            res_in = await session.execute(stmt_in)
            for f in res_in.scalars().all():
                context["imported_by"].append(f.file_path)
                
            # Get external dependencies
            stmt_ext = select(ExternalDependency).where(ExternalDependency.source_file_id == target.id)
            res_ext = await session.execute(stmt_ext)
            for d in res_ext.scalars().all():
                context["dependencies"].append(d.package_name)
                
            return context

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
                            
        except SyntaxError as e:
            logger.debug(f"Skipping file with invalid Python syntax: {e}")
            
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
        include_dependencies: bool = True,
        summary_only: bool = False
    ) -> Dict:
        """Retrieve comprehensive project context from DB."""
        if project_path:
            await self.analyze_project_structure(project_path)
            
        async with self.db.get_session() as session:
            result = await session.execute(select(ProjectFile))
            files = result.scalars().all()
            
            files_dict = {}
            if not summary_only:
                files_dict = {
                    f.file_path: {
                        "path": f.file_path,
                        "type": f.file_type,
                        "size": f.size
                    } for f in files
                }
            
            # If dependencies needed, fetch them
            deps_dict = {}
            if include_dependencies and not summary_only:
                 # Fetch external deps
                 res_ext = await session.execute(select(ExternalDependency))
                 # Simplification for prototype: just list unique packages
                 pkgs = set(d.package_name for d in res_ext.scalars().all())
                 deps_dict["external_packages"] = list(pkgs)

            return {
                "project": project_path or "unknown",
                "total_files": len(files),
                "files": files_dict if not summary_only else "omitted_summary_mode",
                "dependencies": deps_dict if not summary_only else "omitted_summary_mode",
                "last_updated": datetime.now(timezone.utc).isoformat()
            }

    async def search_context(self, query: str, context_type: str = "all") -> List[Dict]:
        """Search context for specific information."""
        results = []
        query_pattern = f"%{query.lower()}%"
        
        async with self.db.get_session() as session:
            if context_type in ["all", "files"]:
                stmt = select(ProjectFile).where(ProjectFile.file_path.ilike(query_pattern))
                res = await session.execute(stmt)
                for f in res.scalars().all():
                    results.append({"type": "file", "path": f.file_path, "info": {"size": f.size}})
                    
            if context_type in ["all", "dependencies"]:
                stmt = select(ExternalDependency).where(ExternalDependency.package_name.ilike(query_pattern))
                res = await session.execute(stmt)
                for d in res.scalars().all():
                    results.append({"type": "dependency", "package": d.package_name})

            if context_type in ["all", "tasks"]:
                stmt = select(Task).where(Task.title.ilike(query_pattern) | Task.description.ilike(query_pattern))
                res = await session.execute(stmt)
                for t in res.scalars().all():
                    results.append({"type": "task", "title": t.title, "status": t.status, "id": t.id})

            if context_type in ["all", "decisions"]:
                stmt = select(Decision).where(Decision.decision.ilike(query_pattern) | Decision.rationale.ilike(query_pattern))
                res = await session.execute(stmt)
                for d in res.scalars().all():
                    results.append({"type": "decision", "decision": d.decision, "id": d.id})
                    
        return results
