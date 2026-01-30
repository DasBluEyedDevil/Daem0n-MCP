"""Deprecation warning utilities for legacy tools."""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def add_deprecation(
    result: Dict[str, Any],
    tool_name: str,
    replacement: str,
) -> Dict[str, Any]:
    """
    Add structured deprecation warning to tool output.

    The _deprecation field is structured so LLM clients can detect
    and surface the deprecation to users.
    """
    result["_deprecation"] = {
        "deprecated": True,
        "tool": tool_name,
        "replacement": replacement,
        "message": f"'{tool_name}' is deprecated. Use '{replacement}' instead.",
    }
    logger.warning(f"Deprecated tool '{tool_name}' invoked. Use '{replacement}' instead.")
    return result
