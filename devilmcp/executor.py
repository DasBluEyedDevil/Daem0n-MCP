# devilmcp/executor.py
"""
Execution Result dataclass.

Simplified from abstract base class to just a result container.
We removed the ToolExecutor ABC because:
1. We only have one executor (SubprocessExecutor)
2. The "native executor" pattern was YAGNI vaporware
3. Simple is better than complex
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ExecutionResult:
    """Result of executing a tool command."""
    success: bool
    output: str
    error: Optional[str] = None
    return_code: Optional[int] = None
    timed_out: bool = False
