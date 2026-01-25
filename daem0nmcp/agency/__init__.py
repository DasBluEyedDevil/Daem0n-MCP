"""
Agency module - Dynamic tool visibility, phase tracking, and sandboxed execution.

Provides:
- RitualPhase: Enum of ritual phases (BRIEFING, EXPLORATION, ACTION, REFLECTION)
- RitualPhaseTracker: Track and transition phases per project
- PHASE_TOOL_VISIBILITY: Mapping of phases to visible tool sets
- AgencyMiddleware: FastMCP middleware for phase-based tool filtering
- SandboxExecutor: Secure Python execution via E2B Firecracker microVMs
- ExecutionResult: Structured result dataclass
- CapabilityScope: Enum of capability scopes for least-privilege access
- CapabilityManager: Manage per-project capabilities
- check_capability: Helper to verify capability access
"""

from .capabilities import CapabilityManager, CapabilityScope, check_capability
from .middleware import AgencyMiddleware
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
    "AgencyMiddleware",
    "SandboxExecutor",
    "ExecutionResult",
    "CapabilityScope",
    "CapabilityManager",
    "check_capability",
]
