"""
Node Functions for Reflexion Loop.

Implements the Actor-Evaluator-Reflector pattern:
- Actor: Generates or revises draft responses
- Evaluator: Extracts claims, verifies them, scores quality
- Reflector: Synthesizes critique into revision instructions

Per CONTEXT.md:
- Hard cap: 3 iterations
- Quality threshold: >= 0.8 for early exit
- Warning at iteration 2 (diminishing returns)

Note: Evaluator output (critique, quality_score, verification_results) is
designed to be consumed by persist_reflection() via create_reflection_from_evaluation()
in the persistence module (03-05). The integration happens there.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from .state import ReflexionState
from .claims import extract_claims
from .verification import verify_claims, summarize_verification

if TYPE_CHECKING:
    from ..memory import MemoryManager
    from ..graph import KnowledgeGraph

logger = logging.getLogger(__name__)

# Quality thresholds per CONTEXT.md
QUALITY_THRESHOLD_EXIT = 0.8  # Early exit if quality >= this
MAX_ITERATIONS = 3  # Hard cap on iterations
WARNING_ITERATION = 2  # Log warning at this iteration


def create_actor_node(
    llm_func: Optional[Callable[[str], str]] = None,
) -> Callable[[ReflexionState], Dict[str, Any]]:
    """
    Create an Actor node function.

    The Actor generates or revises draft responses.
    - First iteration: Generate initial draft from query
    - Subsequent iterations: Revise based on critique

    Args:
        llm_func: Optional function that takes prompt and returns response.
                  If None, returns a placeholder for testing.

    Returns:
        Node function that updates draft in state
    """

    def actor_node(state: ReflexionState) -> Dict[str, Any]:
        """Generate or revise draft based on current state."""
        query = state.get("query", "")
        iteration = state.get("iteration", 0) + 1  # Increment at start
        critique = state.get("critique", "")

        if iteration == 1:
            # First iteration: generate from query
            prompt = f"Respond to: {query}"
        else:
            # Subsequent iterations: incorporate critique
            previous_draft = state.get("draft", "")
            prompt = f"""Revise this response based on the critique.

Original query: {query}

Previous draft:
{previous_draft}

Critique:
{critique}

Provide an improved response addressing the critique."""

        if llm_func is not None:
            draft = llm_func(prompt)
        else:
            # Placeholder for testing without LLM
            draft = f"[Draft iteration {iteration}] Response to: {query}"
            if critique:
                draft += f" (Addressing: {critique[:50]}...)"

        logger.debug(f"Actor generated draft, iteration {iteration}")

        return {
            "draft": draft,
            "iteration": iteration,
        }

    return actor_node


def create_evaluator_node(
    memory_manager: "MemoryManager",
    knowledge_graph: Optional["KnowledgeGraph"] = None,
) -> Callable[[ReflexionState], Dict[str, Any]]:
    """
    Create an Evaluator node function.

    The Evaluator:
    1. Extracts claims from draft
    2. Verifies claims against stored knowledge
    3. Generates critique (verbal gradient)
    4. Scores quality and decides whether to continue

    Output fields (critique, quality_score, verification_results) are designed
    to be consumed by persist_reflection() via create_reflection_from_evaluation()
    in the persistence module.

    Args:
        memory_manager: MemoryManager for claim verification
        knowledge_graph: Optional KnowledgeGraph for entity verification

    Returns:
        Node function that updates critique, quality_score, claims, verification_results, should_continue
    """

    async def evaluator_node(state: ReflexionState) -> Dict[str, Any]:
        """Critique the draft and score quality."""
        draft = state.get("draft", "")
        iteration = state.get("iteration", 1)

        # Log warning at iteration 2 (per CONTEXT.md: diminishing returns)
        if iteration >= WARNING_ITERATION:
            logger.warning(
                f"Reflexion loop at iteration {iteration} - diminishing returns likely"
            )

        # Extract claims from draft
        claims = extract_claims(draft)
        logger.debug(f"Extracted {len(claims)} claims from draft")

        # Verify claims against stored knowledge
        verification_results = await verify_claims(
            claims=claims,
            memory_manager=memory_manager,
            knowledge_graph=knowledge_graph,
        )

        # Summarize verification for quality scoring
        summary = summarize_verification(verification_results)

        # Build critique from verification results
        critique_parts = []

        if summary["conflict_count"] > 0:
            critique_parts.append(
                f"CONFLICTS DETECTED ({summary['conflict_count']}): "
                + "; ".join(c["reason"] for c in summary["conflicts"])
            )

        if summary["unverified_count"] > 0:
            unverified_claims = [
                r.claim_text for r in verification_results if r.status == "unverified"
            ]
            critique_parts.append(
                f"UNVERIFIED CLAIMS ({summary['unverified_count']}): "
                + "; ".join(unverified_claims[:3])  # Limit to 3 for brevity
            )

        if not critique_parts:
            critique = "No issues found. Response appears well-grounded."
        else:
            critique = " | ".join(critique_parts)

        # Calculate quality score
        # Base score from verification confidence
        base_score = summary["overall_confidence"]

        # Penalty for conflicts (major issue)
        conflict_penalty = summary["conflict_count"] * 0.2

        # Minor penalty for unverified (not as bad)
        unverified_penalty = summary["unverified_count"] * 0.05

        quality_score = max(
            0.0, min(1.0, base_score - conflict_penalty - unverified_penalty)
        )

        # Decide whether to continue
        should_continue = (
            quality_score < QUALITY_THRESHOLD_EXIT and iteration < MAX_ITERATIONS
        )

        if quality_score >= QUALITY_THRESHOLD_EXIT:
            logger.info(
                f"Quality threshold met ({quality_score:.2f} >= {QUALITY_THRESHOLD_EXIT}), exiting early"
            )
        elif iteration >= MAX_ITERATIONS:
            logger.info(f"Max iterations reached ({iteration}), exiting")

        # Convert verification results to dicts for state
        verification_dicts = [
            {
                "claim_text": r.claim_text,
                "claim_type": r.claim_type,
                "status": r.status,
                "confidence": r.confidence,
                "conflict_reason": r.conflict_reason,
            }
            for r in verification_results
        ]

        # Convert claims to dicts for state
        claim_dicts = [
            {
                "text": c.text,
                "claim_type": c.claim_type.value,
                "subject": c.subject,
                "verification_level": c.verification_level.value,
            }
            for c in claims
        ]

        return {
            "critique": critique,
            "quality_score": quality_score,
            "claims": claim_dicts,
            "verification_results": verification_dicts,
            "should_continue": should_continue,
        }

    return evaluator_node


def create_reflector_node() -> Callable[[ReflexionState], Dict[str, Any]]:
    """
    Create a Reflector node function.

    The Reflector synthesizes the critique into actionable revision instructions.
    This node prepares the state for the next Actor iteration.

    Returns:
        Node function that refines critique into revision instructions
    """

    def reflector_node(state: ReflexionState) -> Dict[str, Any]:
        """Synthesize critique into revision instructions."""
        critique = state.get("critique", "")
        iteration = state.get("iteration", 1)

        # Extract actionable items from critique
        revision_instructions = []

        if "CONFLICTS DETECTED" in critique:
            revision_instructions.append("Remove or correct conflicting statements")

        if "UNVERIFIED CLAIMS" in critique:
            revision_instructions.append(
                "Add hedging language or remove unsupported claims"
            )

        if not revision_instructions:
            revision_instructions.append("Minor refinements for clarity")

        # Build refined critique with clear instructions
        # Using concatenation to avoid f-string issues with newlines
        instructions_text = "\n".join(f"- {inst}" for inst in revision_instructions)
        refined_critique = f"""Iteration {iteration} Review:
{critique}

Revision Instructions:
{instructions_text}

Focus on addressing the most critical issues first."""

        logger.debug(
            f"Reflector synthesized {len(revision_instructions)} revision instructions"
        )

        return {
            "critique": refined_critique.strip(),
        }

    return reflector_node


# Convenience exports for node functions
def actor_node(state: ReflexionState) -> Dict[str, Any]:
    """Default actor node without LLM (for testing)."""
    return create_actor_node()(state)


def reflector_node(state: ReflexionState) -> Dict[str, Any]:
    """Default reflector node."""
    return create_reflector_node()(state)


__all__ = [
    "create_actor_node",
    "create_evaluator_node",
    "create_reflector_node",
    "actor_node",
    "reflector_node",
    "QUALITY_THRESHOLD_EXIT",
    "MAX_ITERATIONS",
    "WARNING_ITERATION",
]
