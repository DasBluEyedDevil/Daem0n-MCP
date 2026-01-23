"""
Bi-Temporal Operations - Track what was true and when we learned it.

This module provides helpers for:
- Creating memory versions with valid_time
- Point-in-time queries (what did we know at time T?)
- Temporal filtering for recall operations

Time dimensions:
- transaction_time (changed_at): When we recorded this in the system
- valid_time (valid_from/valid_to): When this was true in reality
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import select, or_

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from ..models import MemoryVersion

logger = logging.getLogger(__name__)


async def create_temporal_version(
    session: "AsyncSession",
    memory_id: int,
    version_number: int,
    content: str,
    rationale: Optional[str],
    context: dict,
    tags: list,
    outcome: Optional[str],
    worked: Optional[bool],
    change_type: str,
    change_description: Optional[str] = None,
    valid_from: Optional[datetime] = None,
) -> "MemoryVersion":
    """
    Create a MemoryVersion with proper bi-temporal timestamps.

    Args:
        session: Database session
        memory_id: Parent memory ID
        version_number: Sequential version number
        content: Version content snapshot
        rationale: Version rationale snapshot
        context: Version context snapshot
        tags: Version tags snapshot
        outcome: Outcome state at this version
        worked: Worked state at this version
        change_type: What triggered this version
        change_description: Optional description
        valid_from: When this fact became true (default: now)

    Returns:
        Created MemoryVersion with both time dimensions set
    """
    from ..models import MemoryVersion

    now = datetime.now(timezone.utc)

    # If valid_from not specified, fact is true as of now
    if valid_from is None:
        valid_from = now

    # Ensure timezone awareness
    if valid_from.tzinfo is None:
        valid_from = valid_from.replace(tzinfo=timezone.utc)

    version = MemoryVersion(
        memory_id=memory_id,
        version_number=version_number,
        content=content,
        rationale=rationale,
        context=context,
        tags=tags,
        outcome=outcome,
        worked=worked,
        change_type=change_type,
        change_description=change_description,
        changed_at=now,  # transaction_time: when we learned this
        valid_from=valid_from,  # valid_time: when this was true
        valid_to=None,  # NULL = currently valid
    )

    session.add(version)
    return version


async def get_versions_at_time(
    session: "AsyncSession",
    memory_id: int,
    as_of_valid_time: datetime,
    as_of_transaction_time: Optional[datetime] = None,
) -> List["MemoryVersion"]:
    """
    Get memory versions valid at a specific point in time.

    This implements the core bi-temporal query pattern:
    - valid_time filter: fact was true at query time
    - transaction_time filter: we knew about it at query time

    Args:
        session: Database session
        memory_id: Memory to query
        as_of_valid_time: Return facts true at this time
        as_of_transaction_time: Return knowledge as of this time (default: now)

    Returns:
        List of MemoryVersion objects valid at the specified time
    """
    from ..models import MemoryVersion

    if as_of_transaction_time is None:
        as_of_transaction_time = datetime.now(timezone.utc)

    # Ensure timezone awareness
    if as_of_valid_time.tzinfo is None:
        as_of_valid_time = as_of_valid_time.replace(tzinfo=timezone.utc)
    if as_of_transaction_time.tzinfo is None:
        as_of_transaction_time = as_of_transaction_time.replace(tzinfo=timezone.utc)

    result = await session.execute(
        select(MemoryVersion)
        .where(MemoryVersion.memory_id == memory_id)
        # Valid time filter: fact was true at query time
        # Handle NULL valid_from as "same as changed_at" (backwards compatibility)
        .where(
            or_(
                MemoryVersion.valid_from <= as_of_valid_time,
                MemoryVersion.valid_from.is_(None),  # NULL means valid since changed_at
            )
        )
        .where(
            or_(
                MemoryVersion.valid_to.is_(None),
                MemoryVersion.valid_to > as_of_valid_time,
            )
        )
        # Transaction time filter: we knew about it at query time
        .where(MemoryVersion.changed_at <= as_of_transaction_time)
        .order_by(MemoryVersion.version_number.desc())
    )

    return list(result.scalars().all())


async def invalidate_version(
    session: "AsyncSession",
    version_id: int,
    invalidated_by_version_id: int,
    invalidation_time: Optional[datetime] = None,
) -> bool:
    """
    Mark a version as invalidated (set valid_to).

    Used when new information contradicts existing knowledge.
    Does NOT delete - preserves audit trail.

    Args:
        session: Database session
        version_id: Version to invalidate
        invalidated_by_version_id: Version that caused invalidation
        invalidation_time: When invalidation occurred (default: now)

    Returns:
        True if version was invalidated, False if already invalid
    """
    from sqlalchemy import update
    from ..models import MemoryVersion

    if invalidation_time is None:
        invalidation_time = datetime.now(timezone.utc)

    if invalidation_time.tzinfo is None:
        invalidation_time = invalidation_time.replace(tzinfo=timezone.utc)

    result = await session.execute(
        update(MemoryVersion)
        .where(MemoryVersion.id == version_id)
        .where(MemoryVersion.valid_to.is_(None))  # Only invalidate current versions
        .values(
            valid_to=invalidation_time,
            invalidated_by_version_id=invalidated_by_version_id,
        )
    )

    return result.rowcount > 0
