"""
Maintain workflow - Housekeeping & federation.

Actions:
- prune: Prune old low-value memories
- archive: Archive/unarchive a memory
- cleanup: Merge duplicate memories
- compact: Consolidate recent episodic memories into a summary
- rebuild_index: Force rebuild of TF-IDF/vector indexes
- export: Export all memories and rules as JSON
- import_data: Import memories/rules from exported JSON
- link_project: Link to another project for cross-project reading
- unlink_project: Remove project link
- list_projects: List all linked projects
- consolidate: Merge memories from all linked projects
"""

from typing import Any, Dict, List, Optional

from .errors import InvalidActionError, MissingParamError

VALID_ACTIONS = frozenset({
    "prune",
    "archive",
    "cleanup",
    "compact",
    "rebuild_index",
    "export",
    "import_data",
    "link_project",
    "unlink_project",
    "list_projects",
    "consolidate",
})


async def dispatch(
    action: str,
    project_path: str,
    *,
    # prune params
    older_than_days: int = 90,
    categories: Optional[List[str]] = None,
    min_recall_count: int = 5,
    protect_successful: bool = True,
    dry_run: bool = True,
    # archive params
    memory_id: Optional[int] = None,
    archived: bool = True,
    # cleanup params
    merge_duplicates: bool = True,
    # compact params
    summary: Optional[str] = None,
    limit: int = 10,
    topic: Optional[str] = None,
    # export params
    include_vectors: bool = False,
    # import_data params
    data: Optional[Dict[str, Any]] = None,
    merge: bool = True,
    # link_project params
    linked_path: Optional[str] = None,
    relationship: str = "related",
    label: Optional[str] = None,
    # consolidate params
    archive_sources: bool = False,
    **kwargs,
) -> Dict[str, Any]:
    """Dispatch action to appropriate handler."""
    if action not in VALID_ACTIONS:
        raise InvalidActionError(action, sorted(VALID_ACTIONS))

    if action == "prune":
        return await _do_prune(
            project_path, older_than_days, categories,
            min_recall_count, protect_successful, dry_run,
        )

    elif action == "archive":
        if memory_id is None:
            raise MissingParamError("memory_id", action)
        return await _do_archive(project_path, memory_id, archived)

    elif action == "cleanup":
        return await _do_cleanup(project_path, dry_run, merge_duplicates)

    elif action == "compact":
        if not summary:
            raise MissingParamError("summary", action)
        return await _do_compact(
            project_path, summary, limit, topic, dry_run
        )

    elif action == "rebuild_index":
        return await _do_rebuild_index(project_path)

    elif action == "export":
        return await _do_export(project_path, include_vectors)

    elif action == "import_data":
        if data is None:
            raise MissingParamError("data", action)
        return await _do_import(project_path, data, merge)

    elif action == "link_project":
        if not linked_path:
            raise MissingParamError("linked_path", action)
        return await _do_link_project(
            project_path, linked_path, relationship, label
        )

    elif action == "unlink_project":
        if not linked_path:
            raise MissingParamError("linked_path", action)
        return await _do_unlink_project(project_path, linked_path)

    elif action == "list_projects":
        return await _do_list_projects(project_path)

    elif action == "consolidate":
        return await _do_consolidate(project_path, archive_sources)

    raise InvalidActionError(action, sorted(VALID_ACTIONS))


async def _do_prune(
    project_path: str,
    older_than_days: int,
    categories: Optional[List[str]],
    min_recall_count: int,
    protect_successful: bool,
    dry_run: bool,
) -> Dict[str, Any]:
    """Prune old low-value memories."""
    from ..server import prune_memories

    return await prune_memories(
        older_than_days=older_than_days,
        categories=categories,
        min_recall_count=min_recall_count,
        protect_successful=protect_successful,
        dry_run=dry_run,
        project_path=project_path,
    )


async def _do_archive(
    project_path: str, memory_id: int, archived: bool
) -> Dict[str, Any]:
    """Archive/unarchive a memory."""
    from ..server import archive_memory

    return await archive_memory(
        memory_id=memory_id, archived=archived, project_path=project_path
    )


async def _do_cleanup(
    project_path: str, dry_run: bool, merge_duplicates: bool
) -> Dict[str, Any]:
    """Merge duplicate memories."""
    from ..server import cleanup_memories

    return await cleanup_memories(
        dry_run=dry_run,
        merge_duplicates=merge_duplicates,
        project_path=project_path,
    )


async def _do_compact(
    project_path: str,
    summary: str,
    limit: int,
    topic: Optional[str],
    dry_run: bool,
) -> Dict[str, Any]:
    """Consolidate recent episodic memories into a summary."""
    from ..server import compact_memories

    return await compact_memories(
        summary=summary,
        limit=limit,
        topic=topic,
        dry_run=dry_run,
        project_path=project_path,
    )


async def _do_rebuild_index(project_path: str) -> Dict[str, Any]:
    """Force rebuild of TF-IDF/vector indexes."""
    from ..server import rebuild_index

    return await rebuild_index(project_path=project_path)


async def _do_export(
    project_path: str, include_vectors: bool
) -> Dict[str, Any]:
    """Export all memories and rules as JSON."""
    from ..server import export_data

    return await export_data(
        project_path=project_path, include_vectors=include_vectors
    )


async def _do_import(
    project_path: str, data: Dict[str, Any], merge: bool
) -> Dict[str, Any]:
    """Import memories/rules from exported JSON."""
    from ..server import import_data

    return await import_data(
        data=data, project_path=project_path, merge=merge
    )


async def _do_link_project(
    project_path: str,
    linked_path: str,
    relationship: str,
    label: Optional[str],
) -> Dict[str, Any]:
    """Link to another project."""
    from ..server import link_projects

    return await link_projects(
        linked_path=linked_path,
        relationship=relationship,
        label=label,
        project_path=project_path,
    )


async def _do_unlink_project(
    project_path: str, linked_path: str
) -> Dict[str, Any]:
    """Remove project link."""
    from ..server import unlink_projects

    return await unlink_projects(
        linked_path=linked_path, project_path=project_path
    )


async def _do_list_projects(project_path: str) -> Dict[str, Any]:
    """List all linked projects."""
    from ..server import list_linked_projects

    return await list_linked_projects(project_path=project_path)


async def _do_consolidate(
    project_path: str, archive_sources: bool
) -> Dict[str, Any]:
    """Merge memories from all linked projects."""
    from ..server import consolidate_linked_databases

    return await consolidate_linked_databases(
        archive_sources=archive_sources, project_path=project_path
    )
