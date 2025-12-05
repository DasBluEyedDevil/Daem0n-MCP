"""
Git Native Executor
Uses gitpython library instead of spawning git CLI.
"""

import logging
from typing import Optional, Dict, List

try:
    import git
    from git import Repo, GitCommandError
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False

from ..executor import ToolExecutor, ExecutionResult

logger = logging.getLogger(__name__)


class GitNativeExecutor(ToolExecutor):
    """Git operations via gitpython - no subprocess."""

    SUPPORTED_COMMANDS = [
        "status", "diff", "log", "add", "commit",
        "branch", "checkout", "fetch", "pull", "push"
    ]

    def __init__(self, repo_path: str):
        if not GIT_AVAILABLE:
            raise ImportError("gitpython is required for GitNativeExecutor. Install with: pip install gitpython")
        self.repo_path = repo_path
        self.repo = Repo(repo_path)

    def get_supported_commands(self) -> List[str]:
        """Return list of commands this executor handles."""
        return self.SUPPORTED_COMMANDS.copy()

    async def execute(
        self,
        command: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None
    ) -> ExecutionResult:
        """Execute git command using gitpython."""
        if command not in self.SUPPORTED_COMMANDS:
            return ExecutionResult(
                success=False,
                output="",
                error=f"Command '{command}' not supported. Supported: {', '.join(self.SUPPORTED_COMMANDS)}",
                executor_type="native-git"
            )

        try:
            output = self._run_command(command, args)
            return ExecutionResult(
                success=True,
                output=output,
                executor_type="native-git"
            )
        except GitCommandError as e:
            return ExecutionResult(
                success=False,
                output=e.stdout or "",
                error=e.stderr or str(e),
                return_code=e.status,
                executor_type="native-git"
            )
        except Exception as e:
            logger.error(f"Git command failed: {e}")
            return ExecutionResult(
                success=False,
                output="",
                error=str(e),
                executor_type="native-git"
            )

    def _run_command(self, command: str, args: List[str]) -> str:
        """Run git command and return output."""
        git_cmd = self.repo.git

        if command == "status":
            return git_cmd.status(*args)
        elif command == "diff":
            return git_cmd.diff(*args)
        elif command == "log":
            return git_cmd.log(*args)
        elif command == "add":
            return git_cmd.add(*args)
        elif command == "commit":
            return git_cmd.commit(*args)
        elif command == "branch":
            return git_cmd.branch(*args)
        elif command == "checkout":
            return git_cmd.checkout(*args)
        elif command == "fetch":
            return git_cmd.fetch(*args)
        elif command == "pull":
            return git_cmd.pull(*args)
        elif command == "push":
            return git_cmd.push(*args)
        else:
            raise ValueError(f"Unhandled command: {command}")

    async def cleanup(self) -> None:
        """Clean up repository handle."""
        if hasattr(self, 'repo') and self.repo:
            self.repo.close()
