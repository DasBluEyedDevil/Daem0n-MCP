"""Reflexion loop components for metacognitive architecture.

This module implements the Actor-Evaluator-Reflector pattern for
self-critiquing and verifying claims before returning outputs.
"""

from .claims import Claim, ClaimType, VerificationLevel, extract_claims, is_opinion

__all__ = ["Claim", "ClaimType", "VerificationLevel", "extract_claims", "is_opinion"]
