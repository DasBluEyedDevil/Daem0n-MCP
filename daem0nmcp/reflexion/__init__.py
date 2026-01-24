"""
Reflexion Module - Actor-Evaluator-Reflector Loop for Metacognitive Architecture.

Implements self-critique and iterative improvement via LangGraph state machine.
Verifies claims against stored knowledge before returning outputs.
"""

from .state import ReflexionState, VerificationResult
from .claims import Claim, ClaimType, VerificationLevel, extract_claims, is_opinion

__all__ = [
    "ReflexionState",
    "VerificationResult",
    "Claim",
    "ClaimType",
    "VerificationLevel",
    "extract_claims",
    "is_opinion",
]
