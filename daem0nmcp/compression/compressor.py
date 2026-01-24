"""
Context Compressor - LLMLingua-2 integration for intelligent prompt compression.

Implements lazy initialization to avoid blocking startup and memory waste
when compression isn't needed. Uses tiktoken for accurate token counting.
"""
import logging
from typing import Optional, List, Dict, Any

from .config import CompressionConfig

logger = logging.getLogger(__name__)


class ContextCompressor:
    """
    Compresses context using LLMLingua-2 token classification.

    Key features:
    - Lazy initialization: Model loads on first compress() call
    - Threshold-based: Only compresses when over 4K tokens
    - Configurable: Rates, force_tokens, model selection

    Usage:
        compressor = ContextCompressor()
        if compressor.should_compress(context):
            compressed = compressor.compress(context)
    """

    def __init__(self, config: Optional[CompressionConfig] = None):
        self.config = config or CompressionConfig()
        self._compressor = None  # Lazy loaded
        self._tokenizer = None   # Lazy loaded

    def _ensure_initialized(self) -> None:
        """Lazy-load the compressor and tokenizer on first use."""
        if self._compressor is None:
            try:
                import torch
                from llmlingua import PromptCompressor
                import tiktoken

                # Determine device
                if self.config.device == "auto":
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                else:
                    device = self.config.device

                logger.info(f"Initializing LLMLingua-2 on {device}...")
                self._compressor = PromptCompressor(
                    model_name=self.config.model_name,
                    use_llmlingua2=True,
                    device_map=device,
                )
                self._tokenizer = tiktoken.get_encoding("cl100k_base")
                logger.info("LLMLingua-2 initialized successfully")

            except ImportError as e:
                logger.error(f"LLMLingua dependencies not installed: {e}")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize LLMLingua-2: {e}")
                raise

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken."""
        if self._tokenizer is None:
            import tiktoken
            self._tokenizer = tiktoken.get_encoding("cl100k_base")
        return len(self._tokenizer.encode(text))

    def should_compress(self, context: str) -> bool:
        """
        Check if context should be compressed (exceeds threshold).

        CONTEXT-03 requirement: Compression only triggers when
        context exceeds 4K tokens (cost-benefit threshold).
        """
        token_count = self.count_tokens(context)
        return token_count > self.config.compression_threshold

    def compress(
        self,
        context: str,
        rate: Optional[float] = None,
        force_tokens: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Compress context using LLMLingua-2.

        Args:
            context: Text to compress
            rate: Compression rate (0.33 = 3x compression). Uses config default if None.
            force_tokens: Additional tokens to preserve. Merged with config base tokens.

        Returns:
            Dict with:
                - compressed_prompt: The compressed text
                - original_tokens: Token count before compression
                - compressed_tokens: Token count after compression
                - ratio: Compression ratio achieved
                - skipped: True if compression was skipped (under threshold)
        """
        # Check threshold
        original_tokens = self.count_tokens(context)
        if original_tokens <= self.config.compression_threshold:
            return {
                "compressed_prompt": context,
                "original_tokens": original_tokens,
                "compressed_tokens": original_tokens,
                "ratio": 1.0,
                "skipped": True,
            }

        # Ensure compressor is loaded
        self._ensure_initialized()

        # Merge force tokens
        all_force_tokens = list(self.config.base_force_tokens)
        if force_tokens:
            all_force_tokens.extend(force_tokens)

        # Compress
        result = self._compressor.compress_prompt(
            context,
            rate=rate or self.config.default_rate,
            force_tokens=all_force_tokens,
            drop_consecutive=self.config.drop_consecutive,
        )

        compressed_tokens = self.count_tokens(result["compressed_prompt"])

        return {
            "compressed_prompt": result["compressed_prompt"],
            "original_tokens": original_tokens,
            "compressed_tokens": compressed_tokens,
            "ratio": original_tokens / max(compressed_tokens, 1),
            "skipped": False,
        }

    def compress_simple(
        self,
        context: str,
        rate: Optional[float] = None,
        force_tokens: Optional[List[str]] = None,
    ) -> str:
        """
        Simple compress that returns just the compressed text.

        Convenience wrapper for compress() when you don't need metrics.
        """
        result = self.compress(context, rate=rate, force_tokens=force_tokens)
        return result["compressed_prompt"]
