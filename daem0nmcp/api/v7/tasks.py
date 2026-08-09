"""Cancellation-safe bounded fallback for optional MCP task tools."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import TypeVar


T = TypeVar("T")


task_admission_only_var: ContextVar[bool] = ContextVar(
    "v7_task_admission_only",
    default=False,
)


class TaskExecutionError(RuntimeError):
    """Owned task/fallback failure with a stable v7 error code."""

    def __init__(self, code: str) -> None:
        if code not in {
            "TASK_REQUIRED",
            "TASKS_UNAVAILABLE",
            "DEADLINE_EXCEEDED",
            "CANCELLED",
        }:
            raise ValueError("task execution code is invalid")
        self.code = code
        super().__init__(code)


async def await_task_terminal(task: asyncio.Future[T]) -> T:
    """Drain one admitted task despite repeated caller cancellation."""

    while not task.done():
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            continue
    return task.result()


def _timeout_seconds(value: object, *, allow_subsecond: bool) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("timeout_seconds must be between 1 and 60")
    try:
        timeout = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError("timeout_seconds must be between 1 and 60") from exc
    minimum = 0.001 if allow_subsecond else 1.0
    if not math.isfinite(timeout) or not minimum <= timeout <= 60.0:
        raise ValueError("timeout_seconds must be between 1 and 60")
    return timeout


def validate_sync_timeout_seconds(value: object) -> float:
    """Validate the public 1..60 second synchronous fallback bound."""

    return _timeout_seconds(value, allow_subsecond=False)


async def run_sync_fallback(
    operation: Callable[[], Awaitable[T]],
    *,
    estimated_to_fit: bool,
    timeout_seconds: int | float = 15,
    _test_allow_subsecond: bool = False,
) -> T:
    """Run one optional operation without leaving detached work behind."""
    if not callable(operation):
        raise ValueError("operation must be an awaitable factory")
    if type(estimated_to_fit) is not bool:
        raise ValueError("estimated_to_fit must be boolean")
    timeout = _timeout_seconds(
        timeout_seconds, allow_subsecond=_test_allow_subsecond
    )
    if not estimated_to_fit:
        raise TaskExecutionError("TASK_REQUIRED")

    child = asyncio.create_task(operation())
    try:
        return await asyncio.wait_for(child, timeout=timeout)
    except asyncio.TimeoutError as exc:
        if not child.done():
            child.cancel()
        try:
            await await_task_terminal(child)
        except (asyncio.CancelledError, Exception):
            pass
        raise TaskExecutionError("DEADLINE_EXCEEDED") from exc
    except asyncio.CancelledError:
        if not child.done():
            child.cancel()
        try:
            await await_task_terminal(child)
        except (asyncio.CancelledError, Exception):
            pass
        raise


__all__ = [
    "TaskExecutionError",
    "await_task_terminal",
    "run_sync_fallback",
    "task_admission_only_var",
    "validate_sync_timeout_seconds",
]
