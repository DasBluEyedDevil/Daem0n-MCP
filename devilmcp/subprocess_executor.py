# devilmcp/subprocess_executor.py
"""
Subprocess Executor
Executes CLI tools via subprocess with stateless and stateful modes.
"""

import asyncio
import logging
import uuid
from typing import Optional, Dict, List

from .executor import ToolExecutor, ExecutionResult
from .tool_registry import ToolConfig

logger = logging.getLogger(__name__)


class SubprocessExecutor(ToolExecutor):
    """Executes CLI tools via subprocess."""

    def __init__(self, tool_config: ToolConfig):
        self.config = tool_config
        self._is_stateful = bool(tool_config.prompt_patterns)
        self._process: Optional[asyncio.subprocess.Process] = None
        self._session_id: Optional[str] = None

    async def execute(
        self,
        command: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None
    ) -> ExecutionResult:
        """Execute command using appropriate mode."""
        if self._is_stateful:
            return await self._execute_stateful(command, args, env)
        else:
            return await self._execute_stateless(command, args, env)

    async def _execute_stateless(
        self,
        command: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None
    ) -> ExecutionResult:
        """Run once, capture output, exit. No prompt detection needed."""
        timeout_seconds = self.config.command_timeout / 1000

        try:
            proc = await asyncio.create_subprocess_exec(
                command, *args,
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
                timed_out=False,
                executor_type="subprocess-stateless"
            )

        except asyncio.TimeoutError:
            if proc:
                proc.kill()
                await proc.wait()
            return ExecutionResult(
                success=False,
                output="",
                error=f"Command timed out after {timeout_seconds}s",
                timed_out=True,
                executor_type="subprocess-stateless"
            )

        except Exception as e:
            logger.error(f"Stateless execution failed: {e}")
            return ExecutionResult(
                success=False,
                output="",
                error=str(e),
                executor_type="subprocess-stateless"
            )

    async def _execute_stateful(
        self,
        command: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None
    ) -> ExecutionResult:
        """Maintain session, use sentinel tokens to detect end of output."""

        # Spawn process if not already running
        if self._process is None or self._process.returncode is not None:
            await self._spawn_session(env)

        sentinel = f"__DEVILMCP_END_{uuid.uuid4().hex[:8]}__"
        sentinel_cmd = self._build_sentinel_command(command, sentinel)

        timeout_seconds = self.config.command_timeout / 1000

        try:
            # Send command + sentinel echo
            self._process.stdin.write(sentinel_cmd.encode())
            await self._process.stdin.drain()

            # Read until sentinel appears
            output_lines = []
            while True:
                line = await asyncio.wait_for(
                    self._process.stdout.readline(),
                    timeout=timeout_seconds
                )
                if not line:  # EOF - process died
                    break
                decoded = line.decode(errors='replace').rstrip()
                if sentinel in decoded:
                    break  # Found our marker - done

                # Strip prompt prefix if present and collect output
                stripped = decoded
                for pattern in self.config.prompt_patterns:
                    if stripped.startswith(pattern):
                        stripped = stripped[len(pattern):]
                        break

                # Keep non-empty output that's not the command echo or sentinel
                if stripped and stripped != command and sentinel not in stripped:
                    output_lines.append(stripped)

            return ExecutionResult(
                success=True,
                output="\n".join(output_lines),
                executor_type="subprocess-stateful"
            )

        except asyncio.TimeoutError:
            logger.warning(f"Stateful command timed out: {command[:50]}")
            return ExecutionResult(
                success=False,
                output="\n".join(output_lines) if 'output_lines' in locals() else "",
                error=f"Timeout after {timeout_seconds}s",
                timed_out=True,
                executor_type="subprocess-stateful"
            )

        except BrokenPipeError:
            await self._cleanup_dead_process()
            return ExecutionResult(
                success=False,
                output="",
                error="Process terminated unexpectedly",
                executor_type="subprocess-stateful"
            )

    async def _spawn_session(self, env: Optional[Dict[str, str]] = None) -> None:
        """Spawn a new interactive process session."""
        self._session_id = str(uuid.uuid4())

        full_command = [self.config.command] + self.config.args

        # For Python REPL, add unbuffered flag to ensure immediate output
        if self.config.command.lower() == "python" and "-u" not in full_command:
            full_command.insert(1, "-u")

        self._process = await asyncio.create_subprocess_exec(
            *full_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,  # Merge stderr into stdout
            env=env
        )

        # Wait for initial prompt
        init_timeout = self.config.init_timeout / 1000
        try:
            await asyncio.wait_for(
                self._wait_for_prompt(),
                timeout=init_timeout
            )
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for initial prompt, proceeding anyway")
            # Process may be ready anyway, especially if prompt patterns don't match

    async def _wait_for_prompt(self) -> None:
        """Wait for a prompt pattern to appear."""
        while True:
            line = await self._process.stdout.readline()
            if not line:
                break
            decoded = line.decode(errors='replace')
            for pattern in self.config.prompt_patterns:
                if pattern in decoded:
                    return

    def _build_sentinel_command(self, command: str, sentinel: str) -> str:
        """Inject sentinel echo after the command."""
        cmd_lower = self.config.command.lower()

        if "python" in cmd_lower:
            return f"{command}\nprint('{sentinel}')\n"
        elif "node" in cmd_lower:
            return f"{command}\nconsole.log('{sentinel}')\n"
        else:
            # Generic shell
            return f"{command}\necho {sentinel}\n"

    async def _cleanup_dead_process(self) -> None:
        """Reset state when process dies."""
        if self._process:
            try:
                self._process.kill()
                await self._process.wait()
            except ProcessLookupError:
                pass
        self._process = None
        self._session_id = None

    async def cleanup(self) -> None:
        """Clean up any running processes."""
        if self._process and self._process.returncode is None:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()
            except ProcessLookupError:
                pass  # Already dead
        self._process = None
        self._session_id = None
