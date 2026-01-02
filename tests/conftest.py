# tests/conftest.py
"""
Pytest configuration for Daem0nMCP tests.
"""

import os
import shutil
import tempfile
import uuid
from pathlib import Path


# Register pytest-asyncio plugin
pytest_plugins = ('pytest_asyncio',)


SAFE_TMP_ROOT = Path(__file__).resolve().parent.parent / ".test_tmp"


def _safe_mkdtemp(suffix: str | None = None, prefix: str | None = None, dir: str | None = None) -> str:
    base = Path(dir) if dir else SAFE_TMP_ROOT
    base.mkdir(parents=True, exist_ok=True)
    name_prefix = "tmp" if prefix is None else prefix
    name_suffix = "" if suffix is None else suffix
    unique = uuid.uuid4().hex
    path = base / f"{name_prefix}{unique}{name_suffix}"
    path.mkdir(parents=True, exist_ok=False)
    return str(path)


class _SafeTemporaryDirectory:
    def __init__(self, suffix: str | None = None, prefix: str | None = None, dir: str | None = None):
        self.name = _safe_mkdtemp(suffix=suffix, prefix=prefix, dir=dir)

    def __enter__(self) -> str:
        return self.name

    def cleanup(self) -> None:
        shutil.rmtree(self.name, ignore_errors=True)

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cleanup()

    def __del__(self) -> None:
        self.cleanup()


# Override tempfile helpers to avoid restricted temp directories on Windows.
tempfile.tempdir = str(SAFE_TMP_ROOT)
tempfile.mkdtemp = _safe_mkdtemp  # type: ignore[assignment]
tempfile.TemporaryDirectory = _SafeTemporaryDirectory  # type: ignore[assignment]
os.environ["GIT_CEILING_DIRECTORIES"] = str(SAFE_TMP_ROOT)


def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as an asyncio test."
    )
