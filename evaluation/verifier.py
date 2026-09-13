"""
Verifier Engine for InterviewOne AI (Person 3).
Enforces the 'Claims != Evidence' principle by generating surgical probe questions
for broad claims and assessing whether candidate responses validate them.
"""

from typing import Tuple, Optional
from .schemas import Claim, DepthLevel, EvidenceItem


class ClaimVerifier:
    """
    Guards assessment integrity by verifying candidate assertions.
    Ensures broad claims are proven before contributing to confidence or competency scores.
    """

    @staticmethod
    def generate_probe(claim: Claim) -> str:
        """
        Generates a surgical follow-up question tailored to the claim type.
        """
        claim_text_lower = claim.claim_text.lower()

        if any(w in claim_text_lower for w in ["entire", "whole", "architected", "designed", "from scratch"]):
            return (
                f"You mentioned designing that architecture. Which specific architectural decision or trade-off "
                f"did you personally make, and what alternative design did you reject?"
            )
        elif any(w in claim_text_lower for w in ["scale", "millions", "throughput", "100k", "50k"]):
            return (
                f"When operating at that scale, what was the primary bottleneck or failure mode you encountered, "
                f"and how did you measure the resolution?"
            )
        elif any(w in claim_text_lower for w in ["lead", "led", "managed", "spearheaded"]):
            return (
                f"When leading that implementation, what was a key technical challenge or disagreement that arose, "
                f"and how did you personally navigate it?"
            )
        else:
            return (
                f"Could you walk through the concrete implementation details of your personal contribution "
                f"to that, highlighting the key trade-offs involved?"
            )

    @staticmethod
    def evaluate_probe_response(claim: Claim, candidate_response: str) -> Tuple[bool, str]:
        """
        Evaluates whether the candidate demonstrated genuine personal contribution.
        Returns: (verified: bool, explanation: str)
        """
        response_clean = candidate_response.strip().lower()
        words = response_clean.split()

        # 1. Check for dodging or disclaiming personal ownership
        disclaimers = [
            "not really", "my lead", "tech lead chose", "someone else",
            "team decided", "i wasn't involved", "mostly looked at", "just monitored"
        ]
        for d in disclaimers:
            if d in response_clean:
                return (
                    False,
                    f"Candidate retracted or diluted direct ownership: '{d}' mentioned."
                )

        # 2. Check for sufficient technical depth and agency
        agency_words = ["i chose", "i designed", "i implemented", "i configured", "i tested", "i decided", "my approach"]
        technical_depth_indicators = ["latency", "redis", "sharding", "bottleneck", "async", "replica", "partition", "trade-off", "alternative", "cache", "index"]

        has_agency = any(aw in response_clean for aw in agency_words) or ("i" in words)
        tech_indicators_count = sum(1 for t in technical_depth_indicators if t in response_clean)

        if len(words) >= 15 and has_agency and tech_indicators_count >= 1:
            return (
                True,
                "Candidate provided specific technical choices and demonstrated personal agency."
            )
        elif len(words) >= 25 and tech_indicators_count >= 2:
            return (
                True,
                "Candidate articulated concrete technical trade-offs supporting the claim."
            )
        else:
            return (
                False,
                "Response remained vague or lacked concrete evidence of personal contribution."
            )
