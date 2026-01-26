"""
Agency module - Sandboxed execution and capability management.

Provides:
- SandboxExecutor: Secure Python execution via E2B Firecracker microVMs
- ExecutionResult: Structured result dataclass
- CapabilityScope: Enum of capability scopes for least-privilege access
- CapabilityManager: Manage per-project capabilities
- check_capability: Helper to verify capability access
"""

from .capabilities import CapabilityManager, CapabilityScope, check_capability
from .sandbox import ExecutionResult, SandboxExecutor

__all__ = [
    "SandboxExecutor",
    "ExecutionResult",
    "CapabilityScope",
    "CapabilityManager",
    "check_capability",
]
