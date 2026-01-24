"""
State definitions for the Reflexion loop.

Uses TypedDict for LangGraph state schema. Annotated fields with operator.add
cause list accumulation; scalar fields overwrite.
"""

from typing import List, Optional
from typing_extensions import TypedDict, Annotated
import operator


class VerificationResult(TypedDict):
    """Result of verifying a single claim."""
    claim_text: str
    claim_type: str  # "memory_reference", "factual_assertion"
    status: str  # "verified", "unverified", "conflict"
    evidence: Optional[dict]  # Supporting/contradicting evidence


class ReflexionState(TypedDict):
    """
    State for Actor-Evaluator-Reflector loop.

    Scalar fields (query, draft, critique, quality_score, iteration) overwrite.
    List fields with Annotated[..., operator.add] accumulate across iterations.
    """
    # Input - the original query to respond to
    query: str

    # Actor output - the current draft response
    draft: str

    # Evaluator output
    critique: str  # Verbal gradient describing issues
    quality_score: float  # 0.0-1.0, early exit if >= 0.8

    # Claim verification
    claims: Annotated[List[dict], operator.add]  # Extracted claims
    verification_results: Annotated[List[VerificationResult], operator.add]

    # Loop control
    iteration: int  # Current iteration (1, 2, 3), hard cap at 3
    should_continue: bool  # Set by evaluator based on score + iteration

    # Optional context for claim verification
    context_filter: Optional[dict]  # Categories, tags to filter verification queries
