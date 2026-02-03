"""
Inscribe workflow - Memory writing & linking.

Actions:
- remember: Store a single memory
- remember_batch: Store multiple memories atomically
- link: Create relationship between memories
- unlink: Remove relationship between memories
- pin: Pin/unpin a memory (pinned = never pruned, boosted)
- activate: Add memory to always-hot working context
- deactivate: Remove memory from active context
- clear_active: Clear all active context memories
- ingest: Fetch external docs from URL and store as learnings
"""

from typing import Any, Dict, List, Optional

from .errors import InvalidActionError, MissingParamError

VALID_ACTIONS = frozenset({
    "remember",
    "remember_batch",
    "link",
    "unlink",
    "pin",
    "activate",
    "deactivate",
    "clear_active",
    "ingest",
})


async def dispatch(
    action: str,
    project_path: str,
    *,
    # remember params
    category: Optional[str] = None,
    content: Optional[str] = None,
    rationale: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
    file_path: Optional[str] = None,
    happened_at: Optional[str] = None,
    # remember_batch params
    memories: Optional[List[Dict[str, Any]]] = None,
    # link/unlink params
    source_id: Optional[int] = None,
    target_id: Optional[int] = None,
    relationship: Optional[str] = None,
    description: Optional[str] = None,
    # pin/activate/deactivate params
    memory_id: Optional[int] = None,
    pinned: bool = True,
    # activate params
    reason: Optional[str] = None,
    priority: int = 0,
    expires_in_hours: Optional[int] = None,
    # ingest params
    url: Optional[str] = None,
    topic: Optional[str] = None,
    chunk_size: int = 2000,
) -> Dict[str, Any]:
    """Dispatch action to appropriate handler."""
    if action not in VALID_ACTIONS:
        raise InvalidActionError(action, sorted(VALID_ACTIONS))

    # Read client metadata from ContextVar (set by CovenantMiddleware).
    # The middleware strips _client_meta from tool args before Pydantic
    # validation and stashes the parsed dict in client_meta_var.
    from ..transforms.covenant import client_meta_var

    source_client = None
    source_model = None
    meta = client_meta_var.get()
    if meta:
        try:
            source_client = meta.get("client")
            source_model = f"{meta.get('providerID', 'unknown')}/{meta.get('modelID', 'unknown')}"
        except (AttributeError, TypeError):
            pass  # Malformed metadata is silently ignored

    if action == "remember":
        if not category:
            raise MissingParamError("category", action)
        if not content:
            raise MissingParamError("content", action)
        return await _do_remember(
            project_path, category, content, rationale,
            context, tags, file_path, happened_at,
            source_client=source_client, source_model=source_model,
        )

    elif action == "remember_batch":
        if not memories:
            raise MissingParamError("memories", action)
        return await _do_remember_batch(project_path, memories)

    elif action == "link":
        if source_id is None:
            raise MissingParamError("source_id", action)
        if target_id is None:
            raise MissingParamError("target_id", action)
        if not relationship:
            raise MissingParamError("relationship", action)
        return await _do_link(
            project_path, source_id, target_id, relationship, description
        )

    elif action == "unlink":
        if source_id is None:
            raise MissingParamError("source_id", action)
        if target_id is None:
            raise MissingParamError("target_id", action)
        return await _do_unlink(
            project_path, source_id, target_id, relationship
        )

    elif action == "pin":
        if memory_id is None:
            raise MissingParamError("memory_id", action)
        return await _do_pin(project_path, memory_id, pinned)

    elif action == "activate":
        if memory_id is None:
            raise MissingParamError("memory_id", action)
        return await _do_activate(
            project_path, memory_id, reason, priority, expires_in_hours
        )

    elif action == "deactivate":
        if memory_id is None:
            raise MissingParamError("memory_id", action)
        return await _do_deactivate(project_path, memory_id)

    elif action == "clear_active":
        return await _do_clear_active(project_path)

    elif action == "ingest":
        if not url:
            raise MissingParamError("url", action)
        if not topic:
            raise MissingParamError("topic", action)
        return await _do_ingest(project_path, url, topic, chunk_size)

    raise InvalidActionError(action, sorted(VALID_ACTIONS))


async def _do_remember(
    project_path: str,
    category: str,
    content: str,
    rationale: Optional[str],
    context: Optional[Dict[str, Any]],
    tags: Optional[List[str]],
    file_path: Optional[str],
    happened_at: Optional[str],
    source_client: Optional[str] = None,
    source_model: Optional[str] = None,
) -> Dict[str, Any]:
    """Store a single memory with optional provenance tracking."""
    from datetime import datetime
    from ..context_manager import get_project_context

    ctx = await get_project_context(project_path)

    # Parse happened_at datetime if provided as string
    happened_at_dt = None
    if happened_at:
        try:
            happened_at_dt = datetime.fromisoformat(happened_at.replace('Z', '+00:00'))
        except ValueError:
            return {"error": f"Invalid 'happened_at' date format: {happened_at}. Use ISO format (e.g., '2025-01-01T00:00:00Z')"}

    return await ctx.memory_manager.remember(
        category=category,
        content=content,
        rationale=rationale,
        context=context,
        tags=tags,
        file_path=file_path,
        project_path=ctx.project_path,
        happened_at=happened_at_dt,
        source_client=source_client,
        source_model=source_model,
    )


async def _do_remember_batch(
    project_path: str, memories: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Store multiple memories atomically."""
    from ..server import remember_batch

    return await remember_batch(
        memories=memories, project_path=project_path
    )


async def _do_link(
    project_path: str,
    source_id: int,
    target_id: int,
    relationship: str,
    description: Optional[str],
) -> Dict[str, Any]:
    """Create relationship between memories."""
    from ..server import link_memories

    return await link_memories(
        source_id=source_id,
        target_id=target_id,
        relationship=relationship,
        description=description,
        project_path=project_path,
    )


async def _do_unlink(
    project_path: str,
    source_id: int,
    target_id: int,
    relationship: Optional[str],
) -> Dict[str, Any]:
    """Remove relationship between memories."""
    from ..server import unlink_memories

    return await unlink_memories(
        source_id=source_id,
        target_id=target_id,
        relationship=relationship,
        project_path=project_path,
    )


async def _do_pin(
    project_path: str, memory_id: int, pinned: bool
) -> Dict[str, Any]:
    """Pin/unpin a memory."""
    from ..server import pin_memory

    return await pin_memory(
        memory_id=memory_id, pinned=pinned, project_path=project_path
    )


async def _do_activate(
    project_path: str,
    memory_id: int,
    reason: Optional[str],
    priority: int,
    expires_in_hours: Optional[int],
) -> Dict[str, Any]:
    """Add memory to always-hot working context."""
    from ..server import set_active_context

    return await set_active_context(
        memory_id=memory_id,
        reason=reason,
        priority=priority,
        expires_in_hours=expires_in_hours,
        project_path=project_path,
    )


async def _do_deactivate(
    project_path: str, memory_id: int
) -> Dict[str, Any]:
    """Remove memory from active context."""
    from ..server import remove_from_active_context

    return await remove_from_active_context(
        memory_id=memory_id, project_path=project_path
    )


async def _do_clear_active(project_path: str) -> Dict[str, Any]:
    """Clear all active context memories."""
    from ..server import clear_active_context

    return await clear_active_context(project_path=project_path)


async def _do_ingest(
    project_path: str, url: str, topic: str, chunk_size: int
) -> Dict[str, Any]:
    """Fetch external docs from URL and store as learnings."""
    from ..server import ingest_doc

    return await ingest_doc(
        url=url, topic=topic, chunk_size=chunk_size,
        project_path=project_path,
    )
