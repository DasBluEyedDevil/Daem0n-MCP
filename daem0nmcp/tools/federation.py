"""Multi-project federation tools: link_projects, unlink_projects, etc."""

import logging
from typing import Dict, Optional, Any

try:
    from ..mcp_instance import mcp
    from .. import __version__
    from ..context_manager import (
        get_project_context, _default_project_path,
        _missing_project_path_error,
    )
    from ..logging_config import with_request_id
except ImportError:
    from daem0nmcp.mcp_instance import mcp
    from daem0nmcp import __version__
    from daem0nmcp.context_manager import (
        get_project_context, _default_project_path,
        _missing_project_path_error,
    )
    from daem0nmcp.logging_config import with_request_id

logger = logging.getLogger(__name__)


@mcp.tool(version=__version__)
@with_request_id
async def link_projects(
    linked_path: str,
    relationship: str = "related",
    label: Optional[str] = None,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Link to another project for cross-project memory reading (write isolation preserved).

    Args:
        linked_path: Path to link
        relationship: same-project/upstream/downstream/related
        label: Optional human-readable label
        project_path: Project root
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    try:
        from ..links import LinkManager
    except ImportError:
        from daem0nmcp.links import LinkManager

    link_mgr = LinkManager(ctx.db_manager)
    return await link_mgr.link_projects(
        source_path=ctx.project_path,
        linked_path=linked_path,
        relationship=relationship,
        label=label
    )


@mcp.tool(version=__version__)
@with_request_id
async def unlink_projects(
    linked_path: str,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Remove project link.

    Args:
        linked_path: Path to unlink
        project_path: Project root
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    try:
        from ..links import LinkManager
    except ImportError:
        from daem0nmcp.links import LinkManager

    link_mgr = LinkManager(ctx.db_manager)
    return await link_mgr.unlink_projects(
        source_path=ctx.project_path,
        linked_path=linked_path
    )


@mcp.tool(version=__version__)
@with_request_id
async def list_linked_projects(
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    List all linked projects.

    Args:
        project_path: Project root
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    try:
        from ..links import LinkManager
    except ImportError:
        from daem0nmcp.links import LinkManager

    link_mgr = LinkManager(ctx.db_manager)
    links = await link_mgr.list_linked_projects(source_path=ctx.project_path)
    return {"links": links}


@mcp.tool(version=__version__)
@with_request_id
async def consolidate_linked_databases(
    archive_sources: bool = False,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Merge memories from all linked projects into this one. For monorepo transitions.

    Args:
        archive_sources: Rename source .daem0nmcp to .daem0nmcp.archived
        project_path: Project root
    """
    if not project_path and not _default_project_path:
        return _missing_project_path_error()

    ctx = await get_project_context(project_path)

    try:
        from ..links import LinkManager
    except ImportError:
        from daem0nmcp.links import LinkManager

    link_mgr = LinkManager(ctx.db_manager)
    return await link_mgr.consolidate_linked_databases(
        target_path=ctx.project_path,
        archive_sources=archive_sources
    )
