"""
Hierarchical Context Manager - Leverage Leiden communities for pre-compressed context.

Implements CONTEXT-04: Hierarchical compression leverages Phase 1 community structure.

For simple queries, community summaries ARE the compressed context (no LLMLingua needed).
For complex queries, retrieves raw memories and applies adaptive compression.
"""
import logging
from typing import Dict, Any, Optional, List

from .adaptive import AdaptiveCompressor, ContentType
from .compressor import ContextCompressor
from ..recall_planner import RecallPlanner, RecallPlan, QueryComplexity

logger = logging.getLogger(__name__)


class HierarchicalContextManager:
    """
    Manages context retrieval with hierarchical compression.

    Strategy by query complexity:
    - SIMPLE: Return community summaries only (already compressed by design)
    - MEDIUM: Community summaries + selective raw memories, moderate compression
    - COMPLEX: Full raw memories, adaptive compression

    This leverages Phase 1's Leiden community summaries as the "first tier"
    of compression - they're human-readable summaries that don't need
    LLMLingua processing.

    Usage:
        manager = HierarchicalContextManager(
            compressor=AdaptiveCompressor(),
            recall_planner=RecallPlanner(),
        )
        context = manager.get_context(
            query="what is the auth flow?",
            memories=retrieved_memories,
            community_summaries=summaries,
        )
    """

    def __init__(
        self,
        compressor: Optional[AdaptiveCompressor] = None,
        recall_planner: Optional[RecallPlanner] = None,
    ):
        """
        Initialize with compressor and planner.

        Args:
            compressor: AdaptiveCompressor for content-aware compression.
            recall_planner: RecallPlanner for query classification.
        """
        self.compressor = compressor or AdaptiveCompressor()
        self.recall_planner = recall_planner or RecallPlanner()

    def get_context(
        self,
        query: str,
        memories: List[Dict[str, Any]],
        community_summaries: Optional[List[str]] = None,
        plan: Optional[RecallPlan] = None,
    ) -> Dict[str, Any]:
        """
        Get optimized context for the query.

        Chooses between community summaries and compressed raw memories
        based on query complexity.

        Args:
            query: The search query
            memories: Retrieved memory dicts (with 'content' field)
            community_summaries: Pre-computed Leiden community summaries
            plan: Optional RecallPlan. Computes from query if None.

        Returns:
            Dict with:
                - context: The optimized context string
                - strategy: "summaries", "compressed", or "hybrid"
                - compression_applied: Whether LLMLingua was used
                - token_count: Approximate token count
        """
        # Get or compute plan
        if plan is None:
            plan = self.recall_planner.plan_recall(query)

        # Format raw memories
        raw_context = self._format_memories(memories)

        # Strategy based on complexity
        if plan.complexity == QueryComplexity.SIMPLE:
            return self._simple_strategy(community_summaries, raw_context)

        elif plan.complexity == QueryComplexity.MEDIUM:
            return self._medium_strategy(community_summaries, raw_context, plan)

        else:  # COMPLEX
            return self._complex_strategy(raw_context, plan)

    def _format_memories(self, memories: List[Dict[str, Any]]) -> str:
        """Format memory list into context string."""
        if not memories:
            return ""

        lines = []
        for mem in memories:
            content = mem.get("content", "")
            category = mem.get("category", "memory")
            lines.append(f"[{category}] {content}")

        return "\n\n".join(lines)

    def _format_summaries(self, summaries: Optional[List[str]]) -> str:
        """Format community summaries into context string."""
        if not summaries:
            return ""
        return "\n\n".join(summaries)

    def _simple_strategy(
        self,
        community_summaries: Optional[List[str]],
        raw_context: str,
    ) -> Dict[str, Any]:
        """
        Simple query strategy: Use community summaries (pre-compressed).

        Falls back to raw context if no summaries available.
        """
        if community_summaries:
            context = self._format_summaries(community_summaries)
            return {
                "context": context,
                "strategy": "summaries",
                "compression_applied": False,
                "token_count": self.compressor.compressor.count_tokens(context),
            }
        else:
            # No summaries, return raw (simple queries are short anyway)
            return {
                "context": raw_context,
                "strategy": "raw_fallback",
                "compression_applied": False,
                "token_count": self.compressor.compressor.count_tokens(raw_context),
            }

    def _medium_strategy(
        self,
        community_summaries: Optional[List[str]],
        raw_context: str,
        plan: RecallPlan,
    ) -> Dict[str, Any]:
        """
        Medium query strategy: Hybrid summaries + compressed raw.

        Combines community context with selective raw memories,
        applies moderate compression if over threshold.
        """
        # Combine summaries with raw
        summary_context = self._format_summaries(community_summaries) if community_summaries else ""
        combined = f"{summary_context}\n\n---\n\n{raw_context}" if summary_context else raw_context

        # Check if compression needed
        if plan.compress and self.compressor.compressor.should_compress(combined):
            result = self.compressor.compress(combined, rate_override=plan.compression_rate)
            return {
                "context": result["compressed_prompt"],
                "strategy": "hybrid_compressed",
                "compression_applied": True,
                "token_count": result["compressed_tokens"],
                "original_tokens": result["original_tokens"],
                "compression_ratio": result["ratio"],
            }
        else:
            return {
                "context": combined,
                "strategy": "hybrid",
                "compression_applied": False,
                "token_count": self.compressor.compressor.count_tokens(combined),
            }

    def _complex_strategy(
        self,
        raw_context: str,
        plan: RecallPlan,
    ) -> Dict[str, Any]:
        """
        Complex query strategy: Full raw with adaptive compression.

        Uses content-aware compression for maximum detail retention.
        """
        if plan.compress and self.compressor.compressor.should_compress(raw_context):
            # Let AdaptiveCompressor detect content type
            result = self.compressor.compress(raw_context)
            return {
                "context": result["compressed_prompt"],
                "strategy": "compressed",
                "compression_applied": True,
                "content_type": result.get("content_type"),
                "token_count": result["compressed_tokens"],
                "original_tokens": result["original_tokens"],
                "compression_ratio": result["ratio"],
            }
        else:
            return {
                "context": raw_context,
                "strategy": "raw",
                "compression_applied": False,
                "token_count": self.compressor.compressor.count_tokens(raw_context),
            }
