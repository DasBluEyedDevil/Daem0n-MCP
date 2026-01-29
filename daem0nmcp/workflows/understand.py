"""
Understand workflow - Code comprehension.

Actions:
- index: Index code structure using tree-sitter
- find: Semantic search across indexed code entities
- impact: Analyze blast radius of changing a code entity
- todos: Scan codebase for TODO/FIXME/HACK/XXX/BUG comments
- refactor: Generate refactor suggestions for a file
"""

from typing import Any, Dict, List, Optional

from .errors import InvalidActionError, MissingParamError

VALID_ACTIONS = frozenset({
    "index",
    "find",
    "impact",
    "todos",
    "refactor",
})


async def dispatch(
    action: str,
    project_path: str,
    *,
    # index params
    path: Optional[str] = None,
    patterns: Optional[List[str]] = None,
    # find params
    query: Optional[str] = None,
    limit: int = 20,
    # impact params
    entity_name: Optional[str] = None,
    # todos params
    auto_remember: bool = False,
    types: Optional[List[str]] = None,
    # refactor params
    file_path: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Dispatch action to appropriate handler."""
    if action not in VALID_ACTIONS:
        raise InvalidActionError(action, sorted(VALID_ACTIONS))

    if action == "index":
        return await _do_index(project_path, path, patterns)

    elif action == "find":
        if not query:
            raise MissingParamError("query", action)
        return await _do_find(project_path, query, limit)

    elif action == "impact":
        if not entity_name:
            raise MissingParamError("entity_name", action)
        return await _do_impact(project_path, entity_name)

    elif action == "todos":
        return await _do_todos(project_path, path, auto_remember, types)

    elif action == "refactor":
        if not file_path:
            raise MissingParamError("file_path", action)
        return await _do_refactor(project_path, file_path)

    raise InvalidActionError(action, sorted(VALID_ACTIONS))


async def _do_index(
    project_path: str,
    path: Optional[str],
    patterns: Optional[List[str]],
) -> Dict[str, Any]:
    """Index code structure using tree-sitter."""
    from ..server import index_project

    return await index_project(
        path=path, patterns=patterns, project_path=project_path
    )


async def _do_find(
    project_path: str, query: str, limit: int
) -> Dict[str, Any]:
    """Semantic search across indexed code entities."""
    from ..server import find_code

    return await find_code(
        query=query, project_path=project_path, limit=limit
    )


async def _do_impact(
    project_path: str, entity_name: str
) -> Dict[str, Any]:
    """Analyze blast radius of changing a code entity."""
    from ..server import analyze_impact

    return await analyze_impact(
        entity_name=entity_name, project_path=project_path
    )


async def _do_todos(
    project_path: str,
    path: Optional[str],
    auto_remember: bool,
    types: Optional[List[str]],
) -> Dict[str, Any]:
    """Scan codebase for TODO/FIXME/HACK/XXX/BUG comments."""
    from ..server import scan_todos

    return await scan_todos(
        path=path,
        auto_remember=auto_remember,
        types=types,
        project_path=project_path,
    )


async def _do_refactor(
    project_path: str, file_path: str
) -> Dict[str, Any]:
    """Generate refactor suggestions for a file."""
    from ..server import propose_refactor

    return await propose_refactor(
        file_path=file_path, project_path=project_path
    )
