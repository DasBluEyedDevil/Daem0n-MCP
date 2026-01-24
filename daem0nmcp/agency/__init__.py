"""
Agency module - Dynamic tool visibility, phase tracking, and sandboxed execution.

Provides:
- RitualPhase: Enum of ritual phases (BRIEFING, EXPLORATION, ACTION, REFLECTION)
- RitualPhaseTracker: Track and transition phases per project
- PHASE_TOOL_VISIBILITY: Mapping of phases to visible tool sets
- SandboxExecutor: Secure Python execution via E2B Firecracker microVMs
- ExecutionResult: Structured result dataclass
"""

from .phase_tracker import (
    PHASE_TOOL_VISIBILITY,
    RitualPhase,
    RitualPhaseTracker,
)
from .sandbox import ExecutionResult, SandboxExecutor

__all__ = [
    "RitualPhase",
    "RitualPhaseTracker",
    "PHASE_TOOL_VISIBILITY",
    "SandboxExecutor",
    "ExecutionResult",
]
