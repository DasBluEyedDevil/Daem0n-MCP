"""Tests for pre-compiled regex patterns."""

import pytest
import re


class TestPrecompiledRegex:
    """Verify regex patterns are compiled at module load, not per-call."""

    def test_todo_pattern_is_compiled(self):
        """TODO scanning should use pre-compiled pattern."""
        from daem0nmcp.server import TODO_PATTERN
        assert isinstance(TODO_PATTERN, re.Pattern)

    def test_entity_patterns_are_compiled(self):
        """Entity extraction should use pre-compiled patterns."""
        from daem0nmcp.entity_manager import ENTITY_PATTERNS
        assert isinstance(ENTITY_PATTERNS, dict)
        for name, pattern in ENTITY_PATTERNS.items():
            assert isinstance(pattern, re.Pattern), f"{name} should be compiled"
