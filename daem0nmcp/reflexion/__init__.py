"""
Reflexion Module - Actor-Evaluator-Reflector Loop for Metacognitive Architecture.

Implements self-critique and iterative improvement via LangGraph state machine.
Verifies claims against stored knowledge before returning outputs.
Persists reflections as memories for learning from past corrections.
Consolidates similar episodic reflections into semantic pattern memories.
"""

from .state import ReflexionState
from .state import VerificationResult as StateVerificationResult
from .claims import Claim, ClaimType, VerificationLevel, extract_claims, is_opinion, is_code_verifiable
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
from .persistence import (
    Reflection,
    compute_error_signature,
    persist_reflection,
    retrieve_similar_reflections,
    has_seen_error_before,
    create_reflection_from_evaluation,
)
from .code_gen import generate_verification_code
from .code_exec import (
    CodeFailureType,
    CodeExecutionResult,
    classify_failure,
    execute_verification_code,
    FIXABLE_FAILURES,
    INFRASTRUCTURE_FAILURES,
    VERIFICATION_FAILURES,
)
from .consolidation import (
    consolidate_reflections,
    check_and_consolidate,
    extract_common_elements,
    identify_pattern_type,
    DEFAULT_CONSOLIDATION_THRESHOLD,
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
    "is_code_verifiable",
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
    # Code generation
    "generate_verification_code",
    # Code execution
    "CodeFailureType",
    "CodeExecutionResult",
    "classify_failure",
    "execute_verification_code",
    "FIXABLE_FAILURES",
    "INFRASTRUCTURE_FAILURES",
    "VERIFICATION_FAILURES",
    # Persistence
    "Reflection",
    "compute_error_signature",
    "persist_reflection",
    "retrieve_similar_reflections",
    "has_seen_error_before",
    "create_reflection_from_evaluation",
    # Consolidation
    "consolidate_reflections",
    "check_and_consolidate",
    "extract_common_elements",
    "identify_pattern_type",
    "DEFAULT_CONSOLIDATION_THRESHOLD",
]
