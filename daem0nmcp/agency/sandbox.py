"""
SandboxExecutor - Secure Python code execution via E2B Firecracker microVMs.

Provides isolated code execution with:
- Firecracker microVM isolation (hardware-level)
- No host filesystem access
- Network isolation by default
- Configurable timeout and resource limits
- Structured execution results with output, errors, timing

Security features:
- Layer 1: Firecracker microVM (hardware isolation)
- Layer 2: E2B's sandboxed environment
- Layer 3: Timeout enforcement
- Layer 4: Execution logging for anomaly detection
"""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of sandboxed code execution."""
    success: bool
    output: str
    error: Optional[str] = None
    execution_time_ms: int = 0
    logs: List[str] = field(default_factory=list)


class SandboxExecutor:
    """
    E2B-based sandboxed Python executor.

    Creates isolated Firecracker microVMs for each execution.
    The sandbox has no access to host filesystem or network.

    Usage:
        executor = SandboxExecutor(timeout_seconds=30)
        result = await executor.execute("print('Hello')")
        print(result.output)  # "Hello"

    Requires:
        - E2B_API_KEY environment variable
        - e2b-code-interpreter package installed

    Security:
        - Code runs in Firecracker microVM
        - No host filesystem access
        - Network isolated by default
        - Hard timeout enforced
    """

    def __init__(
        self,
        timeout_seconds: int = 30,
        api_key: Optional[str] = None,
    ):
        """
        Initialize SandboxExecutor.

        Args:
            timeout_seconds: Maximum execution time (default 30s)
            api_key: E2B API key (defaults to E2B_API_KEY env var)
        """
        self.timeout_seconds = timeout_seconds
        self._api_key = api_key or os.environ.get("E2B_API_KEY")
        self._sandbox_available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if E2B sandbox is available."""
        try:
            from e2b_code_interpreter import Sandbox  # noqa: F401 (import tests availability)
            if not self._api_key:
                logger.warning("E2B_API_KEY not set - sandbox unavailable")
                return False
            return True
        except ImportError:
            logger.warning("e2b-code-interpreter not installed - sandbox unavailable")
            return False

    @property
    def available(self) -> bool:
        """Check if sandbox execution is available."""
        return self._sandbox_available

    async def execute(self, code: str) -> ExecutionResult:
        """
        Execute Python code in isolated sandbox.

        Args:
            code: Python code to execute

        Returns:
            ExecutionResult with output, errors, and timing

        Note: Currently uses sync E2B SDK wrapped for async.
              E2B may add native async support in future versions.
        """
        if not self._sandbox_available:
            return ExecutionResult(
                success=False,
                output="",
                error="Sandbox not available. Check E2B_API_KEY and e2b-code-interpreter installation.",
            )

        start_time = time.time()

        try:
            # Import here to avoid import errors when E2B not installed
            from e2b_code_interpreter import Sandbox

            # Create sandbox and execute code
            # E2B handles VM lifecycle automatically with context manager
            with Sandbox(api_key=self._api_key) as sandbox:
                execution = sandbox.run_code(
                    code,
                    timeout=self.timeout_seconds,
                )

                # Collect results
                output = execution.text or ""
                logs = []
                if execution.logs:
                    logs = [
                        log.line if hasattr(log, 'line') else str(log)
                        for log in execution.logs
                    ]

                # Check for errors
                error = None
                if execution.error:
                    error = str(execution.error)
                    logger.warning(f"Sandbox execution error: {error}")

                elapsed_ms = int((time.time() - start_time) * 1000)

                logger.info(
                    f"Sandbox execution completed: success={error is None}, "
                    f"time={elapsed_ms}ms, output_len={len(output)}"
                )

                return ExecutionResult(
                    success=error is None,
                    output=output,
                    error=error,
                    execution_time_ms=elapsed_ms,
                    logs=logs,
                )

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Sandbox execution failed: {e}")
            return ExecutionResult(
                success=False,
                output="",
                error=str(e),
                execution_time_ms=elapsed_ms,
            )

    def __repr__(self) -> str:
        return (
            f"SandboxExecutor(timeout={self.timeout_seconds}s, "
            f"available={self._sandbox_available})"
        )
