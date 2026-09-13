"""
Evidence Manager for InterviewOne AI (Person 3).
Maintains the Live Competency/Evidence Map, manages claim resolution,
and calculates dynamic Evidence Gaps for Person 1's Question Selection Formula.

FIX (PM Audit): Removed dependency on mocks.py — evidence_manager is production
code and must NOT depend on mock data. Initial competencies must be passed in explicitly.
"""

from typing import Dict, List, Optional, Tuple
from .schemas import (
    CompetencyState,
    EvidenceStatus,
    EvidenceItem,
    Claim,
    Contradiction,
    DepthLevel,
)
from .confidence import ConfidenceCalculator
from .scoring import ScoringEngine


def build_competency_map(job_competencies: Dict[str, float], missing_evidence_hints: Optional[Dict[str, List[str]]] = None) -> Dict[str, CompetencyState]:
    """
    Builds a fresh competency map from job requirements.
    Args:
        job_competencies: { "System Design": 5.0, "Python": 4.5, ... }
        missing_evidence_hints: Optional per-competency sub-skill lists to track
    Returns:
        Dict of competency name -> CompetencyState
    """
    hints = missing_evidence_hints or {}
    result = {}
    for comp_name, priority in job_competencies.items():
        result[comp_name] = CompetencyState(
            competency=comp_name,
            priority=max(1.0, min(5.0, priority)),
            score=0.0,
            confidence=0.0,
            status=EvidenceStatus.UNTESTED,
            evidence_list=[],
            claims_pending=[],
            missing_evidence=hints.get(comp_name, ["Core principles", "Architectural trade-offs", "Failure modes"]),
        )
    return result


class EvidenceManager:
    """
    Manages the global evidence state across the interview lifecycle.
    Provides Person 1 (Agent Controller) with real-time gap analysis and information gain metrics.
    """

    def __init__(self, initial_competencies: Dict[str, CompetencyState]):
        if not initial_competencies:
            raise ValueError("EvidenceManager requires a non-empty competency map. Use build_competency_map() or get_default_competencies() from mocks.")
        self.competency_map: Dict[str, CompetencyState] = initial_competencies
        self.claims_ledger: Dict[str, Claim] = {}
        self.contradictions_ledger: List[Contradiction] = []
        self.guardrail_interventions_count: int = 0

    def get_competency(self, competency_name: str) -> CompetencyState:
        """Retrieves or auto-creates a competency state for unexpected competencies."""
        if competency_name not in self.competency_map:
            self.competency_map[competency_name] = CompetencyState(
                competency=competency_name,
                priority=3.0,
                status=EvidenceStatus.UNTESTED,
                missing_evidence=["Fundamental knowledge"],
            )
        return self.competency_map[competency_name]

    def add_turn_evidence(
        self,
        competency_name: str,
        new_evidence: List[EvidenceItem],
        technical_accuracy: float = 3.5,
        stt_confidence: float = 1.0,
        unresolved_contradictions: Optional[List[Contradiction]] = None,
    ) -> CompetencyState:
        """
        Ingests newly extracted evidence, runs scoring and confidence engines,
        and dynamically updates competency status.
        """
        comp = self.get_competency(competency_name)

        # 1. Append validated evidence items
        for ev in new_evidence:
            comp.evidence_list.append(ev)

        # 2. Recalculate Rubric Score
        score_obj, guardrail_applied = ScoringEngine.evaluate_competency(
            state=comp,
            latest_technical_accuracy=technical_accuracy,
        )
        comp.score = score_obj.overall_score
        if guardrail_applied:
            self.guardrail_interventions_count += 1

        # 3. Recalculate Confidence Score
        comp.confidence = ConfidenceCalculator.calculate_competency_confidence(
            state=comp,
            stt_confidence=stt_confidence,
            unresolved_contradictions=unresolved_contradictions,
        )

        # 4. Update Status Lifecycle
        if not comp.evidence_list:
            comp.status = EvidenceStatus.UNTESTED
        elif comp.confidence >= 0.75 and len(comp.evidence_list) >= 2:
            comp.status = EvidenceStatus.WELL_TESTED
        elif comp.priority >= 4.0 and comp.confidence < 0.50:
            comp.status = EvidenceStatus.EVIDENCE_GAP
        else:
            comp.status = EvidenceStatus.PARTIALLY_TESTED

        return comp

    def register_claim(self, claim: Claim):
        """Registers a broad or unverified claim for verification."""
        self.claims_ledger[claim.claim_id] = claim
        comp = self.get_competency(claim.target_competency)
        comp.claims_pending.append(claim)

    def resolve_claim(
        self,
        claim_id: str,
        verified: bool,
        verification_response: str,
        candidate_turn_index: int = 1,
    ) -> Optional[Claim]:
        """
        Resolves a pending claim. If verified, upgrades it to an evidence item.
        If unverified, preserves it as an unproven claim.
        """
        claim = self.claims_ledger.get(claim_id)
        if not claim:
            return None

        claim.verified = verified
        claim.verification_response = verification_response

        if verified:
            evidence = EvidenceItem(
                id=f"ev_claim_{claim.claim_id}",
                competency=claim.target_competency,
                demonstrated_fact=f"Verified candidate direct contribution to: {claim.claim_text[:60]}",
                quote=verification_response[:100],
                depth_level=DepthLevel.INTERMEDIATE,
                confidence_score=0.85,
                turn_index=candidate_turn_index,
            )
            self.add_turn_evidence(claim.target_competency, [evidence])

        return claim

    def get_largest_evidence_gap(self) -> Tuple[str, float]:
        """
        Returns (competency_name, gap_value) for the skill with the greatest evidence gap.
        Used by Person 1 to select what competency to test next.
        """
        gaps = [(name, comp.evidence_gap) for name, comp in self.competency_map.items()]
        if not gaps:
            return ("", 0.0)
        gaps.sort(key=lambda x: x[1], reverse=True)
        return gaps[0]

    def get_untested_competencies(self) -> List[str]:
        """Returns names of competencies that have zero evidence."""
        return [
            name for name, comp in self.competency_map.items()
            if comp.status == EvidenceStatus.UNTESTED or len(comp.evidence_list) == 0
        ]

    def calculate_information_gain(self, competency_name: str) -> float:
        """
        Estimates the potential information gain from asking a question about this competency.
        High when confidence is low; low when confidence is already saturated.
        """
        comp = self.get_competency(competency_name)
        if comp.status == EvidenceStatus.WELL_TESTED:
            return 0.15
        return round(1.0 - comp.confidence, 2)

    def get_live_map(self) -> Dict[str, CompetencyState]:
        """Returns the full live competency dictionary."""
        return self.competency_map
