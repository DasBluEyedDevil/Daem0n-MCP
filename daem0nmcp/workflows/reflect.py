"""
Reflect workflow - Outcomes & verification.

Actions:
- outcome: Record whether a decision worked
- verify: Verify factual claims in text against stored knowledge
- execute: Execute Python code in an isolated sandbox
"""

from typing import Any, Dict, List, Optional

from .errors import InvalidActionError, MissingParamError

VALID_ACTIONS = frozenset({
    "outcome",
    "verify",
    "execute",
})


async def dispatch(
    action: str,
    project_path: str,
    *,
    # outcome params
    memory_id: Optional[int] = None,
    outcome_text: Optional[str] = None,
    worked: Optional[bool] = None,
    # verify params
    text: Optional[str] = None,
    categories: Optional[List[str]] = None,
    as_of_time: Optional[str] = None,
    # execute params
    code: Optional[str] = None,
    timeout_seconds: Optional[int] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Dispatch action to appropriate handler."""
    if action not in VALID_ACTIONS:
        raise InvalidActionError(action, sorted(VALID_ACTIONS))

    if action == "outcome":
        if memory_id is None:
            raise MissingParamError("memory_id", action)
        if not outcome_text:
            raise MissingParamError("outcome_text", action)
        if worked is None:
            raise MissingParamError("worked", action)
        return await _do_outcome(project_path, memory_id, outcome_text, worked)

    elif action == "verify":
        if not text:
            raise MissingParamError("text", action)
        return await _do_verify(
            project_path, text, categories, as_of_time
        )

    elif action == "execute":
        if not code:
            raise MissingParamError("code", action)
        return await _do_execute(project_path, code, timeout_seconds)

    raise InvalidActionError(action, sorted(VALID_ACTIONS))


async def _do_outcome(
    project_path: str,
    memory_id: int,
    outcome_text: str,
    worked: bool,
) -> Dict[str, Any]:
    """Record whether a decision worked."""
    from ..server import record_outcome

    return await record_outcome(
        memory_id=memory_id,
        outcome=outcome_text,
        worked=worked,
        project_path=project_path,
    )


async def _do_verify(
    project_path: str,
    text: str,
    categories: Optional[List[str]],
    as_of_time: Optional[str],
) -> Dict[str, Any]:
    """Verify factual claims against stored knowledge."""
    from ..server import verify_facts

    return await verify_facts(
        text=text,
        categories=categories,
        as_of_time=as_of_time,
        project_path=project_path,
    )


async def _do_execute(
    project_path: str,
    code: str,
    timeout_seconds: Optional[int],
) -> Dict[str, Any]:
    """Execute Python code in an isolated sandbox."""
    from ..server import execute_python

    return await execute_python(
        code=code,
        project_path=project_path,
        timeout_seconds=timeout_seconds,
    )
