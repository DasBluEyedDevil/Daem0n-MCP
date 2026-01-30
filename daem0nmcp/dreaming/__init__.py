"""Background dreaming -- autonomous reasoning during idle periods."""

from .scheduler import IdleDreamScheduler
from .persistence import DreamSession, DreamResult, persist_dream_result, persist_session_summary
from .strategies import DreamStrategy, FailedDecisionReview

__all__ = [
    "IdleDreamScheduler",
    "DreamSession",
    "DreamResult",
    "persist_dream_result",
    "persist_session_summary",
    "DreamStrategy",
    "FailedDecisionReview",
]
