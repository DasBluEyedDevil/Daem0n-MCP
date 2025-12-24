"""
Enforcement module for Daem0nMCP.

Provides session state tracking and pre-commit enforcement logic.
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from sqlalchemy import select

from .database import DatabaseManager
from .models import SessionState, EnforcementBypassLog

logger = logging.getLogger(__name__)


def get_session_id(project_path: str) -> str:
    """
    Generate a session ID based on project path and current hour.

    Sessions are bucketed by hour to group related work together.
    """
    repo_hash = hashlib.md5(project_path.encode()).hexdigest()[:8]
    hour_bucket = datetime.now().strftime("%Y%m%d%H")
    return f"{repo_hash}-{hour_bucket}"


class SessionManager:
    """
    Manages session state for enforcement tracking.

    Tracks:
    - Whether get_briefing was called
    - What context checks were performed
    - What decisions are pending outcomes
    """

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    async def get_session_state(self, project_path: str) -> Optional[Dict[str, Any]]:
        """Get current session state as a dictionary."""
        session_id = get_session_id(project_path)

        async with self.db.get_session() as session:
            result = await session.execute(
                select(SessionState).where(SessionState.session_id == session_id)
            )
            state = result.scalar_one_or_none()

            if state is None:
                return None

            return {
                "session_id": state.session_id,
                "project_path": state.project_path,
                "briefed": state.briefed,
                "context_checks": state.context_checks or [],  # JSON column returns list
                "pending_decisions": state.pending_decisions or [],
                "last_activity": state.last_activity.isoformat() if state.last_activity else None,
            }

    async def mark_briefed(self, project_path: str) -> None:
        """Mark the session as briefed (get_briefing was called)."""
        session_id = get_session_id(project_path)

        async with self.db.get_session() as session:
            result = await session.execute(
                select(SessionState).where(SessionState.session_id == session_id)
            )
            state = result.scalar_one_or_none()

            if state is None:
                state = SessionState(
                    session_id=session_id,
                    project_path=project_path,
                    briefed=True,
                    context_checks=[],
                    pending_decisions=[],
                )
                session.add(state)
            else:
                state.briefed = True
                state.last_activity = datetime.now(timezone.utc)

    async def add_context_check(self, project_path: str, topic_or_file: str) -> None:
        """Record that a context check was performed."""
        session_id = get_session_id(project_path)

        async with self.db.get_session() as session:
            result = await session.execute(
                select(SessionState).where(SessionState.session_id == session_id)
            )
            state = result.scalar_one_or_none()

            if state is None:
                state = SessionState(
                    session_id=session_id,
                    project_path=project_path,
                    context_checks=[topic_or_file],
                    pending_decisions=[],
                )
                session.add(state)
            else:
                checks = list(state.context_checks or [])
                if topic_or_file not in checks:
                    checks.append(topic_or_file)
                    state.context_checks = checks
                state.last_activity = datetime.now(timezone.utc)

    async def add_pending_decision(self, project_path: str, memory_id: int) -> None:
        """Record that a decision was made but not yet outcome-recorded."""
        session_id = get_session_id(project_path)

        async with self.db.get_session() as session:
            result = await session.execute(
                select(SessionState).where(SessionState.session_id == session_id)
            )
            state = result.scalar_one_or_none()

            if state is None:
                state = SessionState(
                    session_id=session_id,
                    project_path=project_path,
                    pending_decisions=[memory_id],
                    context_checks=[],
                )
                session.add(state)
            else:
                pending = list(state.pending_decisions or [])
                if memory_id not in pending:
                    pending.append(memory_id)
                    state.pending_decisions = pending
                state.last_activity = datetime.now(timezone.utc)

    async def remove_pending_decision(self, project_path: str, memory_id: int) -> None:
        """Remove a decision from pending (outcome was recorded)."""
        session_id = get_session_id(project_path)

        async with self.db.get_session() as session:
            result = await session.execute(
                select(SessionState).where(SessionState.session_id == session_id)
            )
            state = result.scalar_one_or_none()

            if state is not None:
                pending = list(state.pending_decisions or [])
                if memory_id in pending:
                    pending.remove(memory_id)
                    state.pending_decisions = pending
                state.last_activity = datetime.now(timezone.utc)
