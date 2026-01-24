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
]
