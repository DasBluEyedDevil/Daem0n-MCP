"""
Reflexion Module - Actor-Evaluator-Reflector Loop for Metacognitive Architecture.

Implements self-critique and iterative improvement via LangGraph state machine.
Verifies claims against stored knowledge before returning outputs.
"""

from .state import ReflexionState
from .state import VerificationResult as StateVerificationResult
from .claims import Claim, ClaimType, VerificationLevel, extract_claims, is_opinion
from .verification import (
    verify_claim,
    verify_claims,
    summarize_verification,
    VerificationResult,
    VerificationEvidence,
)
from .nodes import (
    create_actor_node,
    create_evaluator_node,
    create_reflector_node,
    actor_node,
    reflector_node,
    QUALITY_THRESHOLD_EXIT,
    MAX_ITERATIONS,
    WARNING_ITERATION,
)
from .graph import (
    build_reflexion_graph,
    create_reflexion_app,
    run_reflexion,
    should_continue,
)

__all__ = [
    # State definitions
    "ReflexionState",
    "StateVerificationResult",
    # Claim extraction
    "Claim",
    "ClaimType",
    "VerificationLevel",
    "extract_claims",
    "is_opinion",
    # Claim verification
    "verify_claim",
    "verify_claims",
    "summarize_verification",
    "VerificationResult",
    "VerificationEvidence",
    # Node functions
    "create_actor_node",
    "create_evaluator_node",
    "create_reflector_node",
    "actor_node",
    "reflector_node",
    "QUALITY_THRESHOLD_EXIT",
    "MAX_ITERATIONS",
    "WARNING_ITERATION",
    # Graph construction
    "build_reflexion_graph",
    "create_reflexion_app",
    "run_reflexion",
    "should_continue",
]
