"""
Native Executors Package
Python SDK integrations that bypass subprocess entirely.
"""

from .git import GitNativeExecutor

__all__ = ["GitNativeExecutor"]
