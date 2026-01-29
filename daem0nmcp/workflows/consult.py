"""
Consult workflow - Pre-action intelligence.

Actions:
- preflight: Pre-flight check combining recall + check_rules
- recall: Semantic search for memories using TF-IDF
- recall_file: Get all memories associated with a specific file
- recall_entity: Get all memories mentioning a specific entity
- recall_hierarchical: GraphRAG-style layered recall
- search: Full-text search across all memories
- check_rules: Check if an action matches any rules
- compress: Compress context for token reduction
"""

from typing import Any, Dict, List, Optional

from .errors import InvalidActionError, MissingParamError

VALID_ACTIONS = frozenset({
    "preflight",
    "recall",
    "recall_file",
    "recall_entity",
    "recall_hierarchical",
    "search",
    "check_rules",
    "compress",
})


async def dispatch(
    action: str,
    project_path: str,
    *,
    # preflight params
    description: Optional[str] = None,
    # recall params
    topic: Optional[str] = None,
    categories: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    file_path: Optional[str] = None,
    offset: int = 0,
    limit: int = 10,
    since: Optional[str] = None,
    until: Optional[str] = None,
    include_linked: bool = False,
    visual: bool = False,
    condensed: bool = False,
    # recall_entity params
    entity_name: Optional[str] = None,
    entity_type: Optional[str] = None,
    # recall_hierarchical params
    include_members: bool = False,
    # search params
    query: Optional[str] = None,
    include_meta: bool = False,
    highlight: bool = False,
    highlight_start: str = "<b>",
    highlight_end: str = "</b>",
    # check_rules params
    action_desc: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    # compress params
    rate: Optional[float] = None,
    content_type: Optional[str] = None,
    preserve_code: bool = True,
    **kwargs,
) -> Any:
    """Dispatch action to appropriate handler."""
    if action not in VALID_ACTIONS:
        raise InvalidActionError(action, sorted(VALID_ACTIONS))

    if action == "preflight":
        if not description:
            raise MissingParamError("description", action)
        return await _do_preflight(project_path, description)

    elif action == "recall":
        if not topic:
            raise MissingParamError("topic", action)
        return await _do_recall(
            project_path, topic, categories, tags, file_path,
            offset, limit, since, until, include_linked, visual, condensed,
        )

    elif action == "recall_file":
        if not file_path:
            raise MissingParamError("file_path", action)
        return await _do_recall_file(project_path, file_path, limit)

    elif action == "recall_entity":
        if not entity_name:
            raise MissingParamError("entity_name", action)
        return await _do_recall_entity(
            project_path, entity_name, entity_type
        )

    elif action == "recall_hierarchical":
        if not topic:
            raise MissingParamError("topic", action)
        return await _do_recall_hierarchical(
            project_path, topic, include_members, limit
        )

    elif action == "search":
        if not query:
            raise MissingParamError("query", action)
        return await _do_search(
            project_path, query, limit, offset, include_meta,
            highlight, highlight_start, highlight_end,
        )

    elif action == "check_rules":
        if not action_desc:
            raise MissingParamError("action_desc", action)
        return await _do_check_rules(project_path, action_desc, context)

    elif action == "compress":
        # context param is used for check_rules; for compress we use kwargs
        compress_text = kwargs.get("context") if isinstance(kwargs.get("context"), str) else None
        # But since context is already captured as a Dict above, we need a
        # separate way to pass the text. Let's check kwargs first.
        if compress_text is None:
            raise MissingParamError("context", action)
        return await _do_compress(
            compress_text, rate, content_type, preserve_code
        )

    raise InvalidActionError(action, sorted(VALID_ACTIONS))


async def _do_preflight(
    project_path: str, description: str
) -> Dict[str, Any]:
    """Pre-flight check combining recall + check_rules."""
    from ..server import context_check

    return await context_check(
        description=description, project_path=project_path
    )


async def _do_recall(
    project_path: str,
    topic: str,
    categories: Optional[List[str]],
    tags: Optional[List[str]],
    file_path: Optional[str],
    offset: int,
    limit: int,
    since: Optional[str],
    until: Optional[str],
    include_linked: bool,
    visual: bool,
    condensed: bool,
) -> Any:
    """Semantic search for memories."""
    from ..server import recall, recall_visual

    if visual:
        return await recall_visual(
            topic=topic,
            categories=categories,
            tags=tags,
            file_path=file_path,
            offset=offset,
            limit=limit,
            include_linked=include_linked,
            project_path=project_path,
        )
    return await recall(
        topic=topic,
        categories=categories,
        tags=tags,
        file_path=file_path,
        offset=offset,
        limit=limit,
        since=since,
        until=until,
        project_path=project_path,
        include_linked=include_linked,
        condensed=condensed,
    )


async def _do_recall_file(
    project_path: str, file_path: str, limit: int
) -> Dict[str, Any]:
    """Get all memories for a specific file."""
    from ..server import recall_for_file

    return await recall_for_file(
        file_path=file_path, limit=limit, project_path=project_path
    )


async def _do_recall_entity(
    project_path: str,
    entity_name: str,
    entity_type: Optional[str],
) -> Dict[str, Any]:
    """Get all memories mentioning a specific entity."""
    from ..server import recall_by_entity

    return await recall_by_entity(
        entity_name=entity_name,
        entity_type=entity_type,
        project_path=project_path,
    )


async def _do_recall_hierarchical(
    project_path: str,
    topic: str,
    include_members: bool,
    limit: int,
) -> Dict[str, Any]:
    """GraphRAG-style layered recall."""
    from ..server import recall_hierarchical

    return await recall_hierarchical(
        topic=topic,
        include_members=include_members,
        limit=limit,
        project_path=project_path,
    )


async def _do_search(
    project_path: str,
    query: str,
    limit: int,
    offset: int,
    include_meta: bool,
    highlight: bool,
    highlight_start: str,
    highlight_end: str,
) -> Any:
    """Full-text search across all memories."""
    from ..server import search_memories

    return await search_memories(
        query=query,
        limit=limit,
        offset=offset,
        include_meta=include_meta,
        highlight=highlight,
        highlight_start=highlight_start,
        highlight_end=highlight_end,
        project_path=project_path,
    )


async def _do_check_rules(
    project_path: str,
    action_desc: str,
    context: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Check if an action matches any rules."""
    from ..server import check_rules

    return await check_rules(
        action=action_desc, context=context, project_path=project_path
    )


async def _do_compress(
    context: str,
    rate: Optional[float],
    content_type: Optional[str],
    preserve_code: bool,
) -> str:
    """Compress context for token reduction."""
    from ..server import compress_context

    return await compress_context(
        context=context,
        rate=rate,
        content_type=content_type,
        preserve_code=preserve_code,
    )
