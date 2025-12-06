# devilmcp/subprocess_executor.py
"""
Subprocess Executor
Executes CLI tools via subprocess with stateless execution only.

Stateful REPL mode was removed because:
1. It adds massive complexity (timeouts, stuck processes, memory leaks)
2. Most agentic tasks are stateless: "read file", "run test", "commit code"
3. Simple stateless execution is 100x more robust
"""

import asyncio
import logging
from typing import Optional, Dict, List

from .executor import ExecutionResult
from .tool_registry import ToolConfig

logger = logging.getLogger(__name__)


class SubprocessExecutor:
    """Executes CLI tools via subprocess - stateless only."""

    def __init__(self, tool_config: ToolConfig):
        self.config = tool_config

    async def execute(
        self,
        command: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None
    ) -> ExecutionResult:
        """Execute command and return result."""
        timeout_seconds = self.config.command_timeout / 1000
        proc = None

        # Build the full command
        full_args = [command] + args if args else [command]

        try:
            proc = await asyncio.create_subprocess_exec(
                self.config.command,
                *self.config.args,
                *full_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_seconds
            )

            return ExecutionResult(
                success=(proc.returncode == 0),
                output=stdout.decode(errors='replace').strip(),
                error=stderr.decode(errors='replace').strip() if stderr else None,
                return_code=proc.returncode,
                timed_out=False
            )

        except asyncio.TimeoutError:
            if proc:
                proc.kill()
                await proc.wait()
            return ExecutionResult(
                success=False,
                output="",
                error=f"Command timed out after {timeout_seconds}s",
                timed_out=True
            )

        except FileNotFoundError:
            return ExecutionResult(
                success=False,
                output="",
                error=f"Command not found: {self.config.command}"
            )

        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return ExecutionResult(
                success=False,
                output="",
                error=str(e)
            )

    async def cleanup(self) -> None:
        """No cleanup needed for stateless execution."""
        pass
