"""
Confidence Engine for InterviewOne AI (Person 3).
Calculates mathematically grounded confidence scores (0.0 to 1.0)
for each competency and the overall assessment.

FIX (PM Audit): Removed unused imports (EvidenceItem, Claim).
"""

from typing import List, Optional
from .schemas import (
    CompetencyState,
    Contradiction,
    DepthLevel,
)


class ConfidenceCalculator:
    """
    Computes confidence level for a competency based on:
    - Volume of concrete evidence items
    - Depth of technical demonstration (Advanced > Intermediate > Fundamental)
    - Pending unverified claims (penalty)
    - Active unresolved contradictions (penalty)
    - Speech-to-Text transcription confidence (multiplier from Person 2)
    """

    @staticmethod
    def calculate_competency_confidence(
        state: CompetencyState,
        stt_confidence: float = 1.0,
        unresolved_contradictions: Optional[List[Contradiction]] = None,
    ) -> float:
        """
        Calculates confidence score in range [0.0, 1.0].
        """
        evidence_list = state.evidence_list
        if not evidence_list:
            return 0.0

        # 1. Evidence Volume & Depth Weighting
        depth_weights = {
            DepthLevel.SURFACE: 0.10,
            DepthLevel.FUNDAMENTAL: 0.25,
            DepthLevel.INTERMEDIATE: 0.45,
            DepthLevel.ADVANCED: 0.70,
        }

        weighted_evidence_sum = sum(
            depth_weights.get(e.depth_level, 0.25) * e.confidence_score
            for e in evidence_list
        )

        # Base confidence saturates as more high-depth evidence accumulates
        denominator = 0.8 + (0.35 * len(evidence_list))
        base_confidence = min(0.98, weighted_evidence_sum / denominator)

        # 2. Penalty for unverified claims in this competency
        pending_claims = [c for c in state.claims_pending if c.verification_needed and not c.verified]
        claim_penalty = len(pending_claims) * 0.10

        # 3. Penalty for active contradictions
        contradiction_penalty = 0.0
        if unresolved_contradictions:
            comp_contradictions = [c for c in unresolved_contradictions if not c.resolved]
            contradiction_penalty = len(comp_contradictions) * 0.20

        # 4. Apply penalties
        adjusted_conf = max(0.05, base_confidence - claim_penalty - contradiction_penalty)

        # 5. Multimodal Audio STT Confidence Discount (from Person 2)
        # If transcription was poor, we cannot be highly confident in text evaluation
        safe_stt = max(0.5, min(1.0, stt_confidence))
        final_conf = adjusted_conf * safe_stt

        return round(min(1.0, max(0.0, final_conf)), 2)

    @staticmethod
    def calculate_overall_confidence(competencies: List[CompetencyState]) -> float:
        """Computes weighted average confidence across tested competencies."""
        active = [c for c in competencies if c.evidence_list or c.confidence > 0]
        if not active:
            return 0.0

        total_weight = sum(c.priority for c in active)
        weighted_conf = sum(c.confidence * c.priority for c in active)
        return round(weighted_conf / total_weight, 2)
