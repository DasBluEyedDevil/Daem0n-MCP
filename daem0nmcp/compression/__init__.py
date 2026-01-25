"""
Compression module for intelligent context compression.

Uses LLMLingua-2 for token classification-based compression,
achieving 3x-6x reduction while preserving critical information.
"""

from .config import CompressionConfig
from .compressor import ContextCompressor
from .entity_preserver import CodeEntityPreserver
from .adaptive import AdaptiveCompressor, ContentType, COMPRESSION_RATES
from .hierarchical import HierarchicalContextManager

__all__ = [
    "CompressionConfig",
    "ContextCompressor",
    "CodeEntityPreserver",
    "AdaptiveCompressor",
    "ContentType",
    "COMPRESSION_RATES",
    "HierarchicalContextManager",
]
