"""
Agency module - Dynamic tool visibility and phase tracking.

This module implements Phase 5's tool visibility system, which dynamically
filters available tools based on the agent's current ritual phase.

Exports:
    RitualPhase: Enum of ritual phases (BRIEFING, EXPLORATION, ACTION, REFLECTION)
    RitualPhaseTracker: Track and transition phases per project
    PHASE_TOOL_VISIBILITY: Mapping of phases to visible tool sets
"""

from daem0nmcp.agency.phase_tracker import (
    PHASE_TOOL_VISIBILITY,
    RitualPhase,
    RitualPhaseTracker,
)

__all__ = [
    "RitualPhase",
    "RitualPhaseTracker",
    "PHASE_TOOL_VISIBILITY",
]
