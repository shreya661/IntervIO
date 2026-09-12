"""
Mock generators and deterministic MockEvaluator for offline testing and immediate
unblocking of Person 1 (Agent Controller) and Person 4 (FastAPI + UI).

FIX (PM Audit):
- Fixed datetime.utcnow() deprecation warning → uses timezone.utc
- MockEvaluator now exposes evidence_manager attribute so Person 1 can call
  mock.evidence_manager.get_largest_evidence_gap() without crash
"""

import uuid
from typing import Dict, List, Optional
from datetime import datetime, timezone
from .schemas import (
    EvidenceStatus,
    DepthLevel,
    ActionRecommendation,
    Claim,
    EvidenceItem,
    Contradiction,
    CompetencyState,
    TurnAnalysisResult,
    EvaluationTurnResult,
    FinalAssessmentReport,
)


def get_default_competencies() -> Dict[str, CompetencyState]:
    """Returns a realistic default competency map for a Senior Software Engineer role."""
    return {
        "System Design": CompetencyState(
            competency="System Design",
            priority=5.0,
            score=0.0,
            confidence=0.0,
            status=EvidenceStatus.UNTESTED,
            evidence_list=[],
            claims_pending=[],
            missing_evidence=["Horizontal scaling", "Database bottleneck strategy", "Caching architecture", "Disaster recovery"],
        ),
        "Python": CompetencyState(
            competency="Python",
            priority=4.5,
            score=0.0,
            confidence=0.0,
            status=EvidenceStatus.UNTESTED,
            evidence_list=[],
            claims_pending=[],
            missing_evidence=["Asyncio / Event Loop", "Memory management & GIL", "Generators & Iterators"],
        ),
        "Database & SQL": CompetencyState(
            competency="Database & SQL",
            priority=4.0,
            score=0.0,
            confidence=0.0,
            status=EvidenceStatus.UNTESTED,
            evidence_list=[],
            claims_pending=[],
            missing_evidence=["Index optimization", "ACID transactions & isolation levels", "Query execution plans"],
        ),
        "Debugging & Troubleshooting": CompetencyState(
            competency="Debugging & Troubleshooting",
            priority=4.0,
            score=0.0,
            confidence=0.0,
            status=EvidenceStatus.UNTESTED,
            evidence_list=[],
            claims_pending=[],
            missing_evidence=["Root cause analysis methodology", "Distributed tracing", "Race condition diagnosis"],
        ),
        "Communication & Ownership": CompetencyState(
            competency="Communication & Ownership",
            priority=3.5,
            score=0.0,
            confidence=0.0,
            status=EvidenceStatus.UNTESTED,
            evidence_list=[],
            claims_pending=[],
            missing_evidence=["Technical articulation", "Trade-off justification", "Handling conflicting requirements"],
        ),
    }


class _MockEvidenceManager:
    """Lightweight stand-in so MockEvaluator.evidence_manager works identically to real EvidenceManager."""

    def __init__(self, competency_map: Dict[str, CompetencyState]):
        self.competency_map = competency_map
        self.claims_ledger: Dict[str, Claim] = {}

    def get_largest_evidence_gap(self):
        gaps = [(name, comp.evidence_gap) for name, comp in self.competency_map.items()]
        if not gaps:
            return ("", 0.0)
        gaps.sort(key=lambda x: x[1], reverse=True)
        return gaps[0]

    def get_live_map(self):
        return self.competency_map

    def get_untested_competencies(self):
        return [n for n, c in self.competency_map.items() if c.status == EvidenceStatus.UNTESTED]

    def calculate_information_gain(self, competency_name: str) -> float:
        comp = self.competency_map.get(competency_name)
        if not comp or comp.status.value == "well_tested":
            return 0.15
        return round(1.0 - comp.confidence, 2)


class MockEvaluator:
    """
    Drop-in mock engine for Person 1 and Person 4.
    Simulates the full Person 3 pipeline without requiring active LLM API keys.
    Exposes .evidence_manager so Person 1 can call gap queries identically to production.
    """

    def __init__(self, initial_competencies: Optional[Dict[str, CompetencyState]] = None):
        self.competency_map: Dict[str, CompetencyState] = initial_competencies or get_default_competencies()
        self.evidence_manager = _MockEvidenceManager(self.competency_map)
        self.turn_history: List[EvaluationTurnResult] = []

    def process_turn(
        self,
        turn_index: int,
        question: str,
        answer: str,
        current_competency: str,
        stt_confidence: float = 1.0,
        resume_context: Optional[str] = None,
        job_context: Optional[str] = None,
        candidate_resume_context: Optional[str] = None,
    ) -> EvaluationTurnResult:
        """
        Simulates evaluating a single candidate turn.
        Detects keywords to simulate strong, vague, or claim-heavy answers.
        """
        answer_lower = answer.lower()
        new_evidence: List[EvidenceItem] = []
        new_claims: List[Claim] = []
        contradictions: List[Contradiction] = []
        comp = self.competency_map.get(current_competency)

        if not comp:
            comp = CompetencyState(
                competency=current_competency,
                priority=3.5,
                status=EvidenceStatus.UNTESTED,
                missing_evidence=["Core fundamentals"],
            )
            self.competency_map[current_competency] = comp
            self.evidence_manager.competency_map = self.competency_map

        # 1. Broad Ownership Claim detection
        if "i designed the entire" in answer_lower or "i built everything" in answer_lower or "led the complete" in answer_lower:
            claim = Claim(
                claim_id=f"claim_{uuid.uuid4().hex[:6]}",
                claim_text=answer[:100],
                target_competency=current_competency,
                verification_needed=True,
                verification_question="Which specific architectural decision in that project did you personally make, and what alternative did you reject?",
                verified=False,
            )
            new_claims.append(claim)
            comp.claims_pending.append(claim)
            self.evidence_manager.claims_ledger[claim.claim_id] = claim
            recommended_action = ActionRecommendation.VERIFY_CLAIM
            action_reason = "Unverified broad ownership claim detected. Need to verify personal contributions."
            suggested_q = claim.verification_question
            vagueness_score = 0.5
            tech_score = 3.0

        # 2. Vague / Buzzwordy answer
        elif (
            len(answer.split()) < 20
            or any(b in answer_lower for b in ["nice and clean", "very scalable", "best practices", "good practices"])
            and not any(t in answer_lower for t in ["redis", "postgres", "latency", "sharding", "bottleneck", "thread", "queue"])
        ):
            recommended_action = ActionRecommendation.PROBE_VAGUE
            action_reason = "Answer lacked concrete technical metrics or trade-offs."
            suggested_q = "Could you provide a concrete example or walk through the specific failure scenario you handled?"
            vagueness_score = 0.85
            tech_score = 2.0

        # 3. Strong Technical Answer
        else:
            evidence = EvidenceItem(
                id=f"ev_{uuid.uuid4().hex[:6]}",
                competency=current_competency,
                demonstrated_fact=f"Demonstrated clear understanding of {current_competency} concepts and trade-offs",
                quote=answer[:120] + ("..." if len(answer) > 120 else ""),
                depth_level=DepthLevel.INTERMEDIATE if len(answer.split()) < 40 else DepthLevel.ADVANCED,
                confidence_score=min(1.0, 0.75 * stt_confidence),
                turn_index=turn_index,
            )
            new_evidence.append(evidence)
            comp.evidence_list.append(evidence)

            comp.score = min(5.0, max(comp.score, 4.0 if evidence.depth_level == DepthLevel.ADVANCED else 3.5))
            comp.confidence = min(1.0, comp.confidence + (0.35 * stt_confidence))
            comp.status = EvidenceStatus.WELL_TESTED if comp.confidence >= 0.75 else EvidenceStatus.PARTIALLY_TESTED

            if comp.status == EvidenceStatus.WELL_TESTED:
                recommended_action = ActionRecommendation.SWITCH_COMPETENCY
                action_reason = f"{current_competency} is now sufficiently tested (confidence {comp.confidence:.2f}). Move to largest remaining gap."
                suggested_q = None
            else:
                recommended_action = ActionRecommendation.PROBE_DEEPER
                action_reason = "Answer was strong. Probe deeper scenario to verify advanced boundary conditions."
                suggested_q = "How would that architecture behave if traffic spiked 10x while the primary database encountered high write-latency?"

            vagueness_score = 0.15
            tech_score = 4.2

        analysis = TurnAnalysisResult(
            demonstrated_evidence=new_evidence,
            claims_detected=new_claims,
            contradictions_detected=contradictions,
            technical_correctness=tech_score,
            depth_level=DepthLevel.ADVANCED if tech_score >= 4.0 else DepthLevel.FUNDAMENTAL,
            vagueness_score=vagueness_score,
            vagueness_reason="Lacks concrete metrics" if vagueness_score > 0.6 else None,
            needs_followup=(recommended_action in [ActionRecommendation.PROBE_VAGUE, ActionRecommendation.VERIFY_CLAIM]),
            followup_angle=action_reason,
        )

        result = EvaluationTurnResult(
            turn_index=turn_index,
            competency_tested=current_competency,
            analysis=analysis,
            new_evidence=new_evidence,
            claims_flagged=new_claims,
            contradictions=contradictions,
            live_competency_map=self.competency_map,
            recommended_action=recommended_action,
            action_reason=action_reason,
            suggested_followup_question=suggested_q,
        )
        self.turn_history.append(result)
        return result

    def generate_final_report(self, interview_id: str, candidate_name: str, job_title: str) -> FinalAssessmentReport:
        """Generates a complete simulated final hiring report."""
        total_score = 0.0
        total_conf = 0.0
        active_comps = [c for c in self.competency_map.values() if c.status != EvidenceStatus.UNTESTED]

        if active_comps:
            total_score = sum(c.score for c in active_comps) / len(active_comps)
            total_conf = sum(c.confidence for c in active_comps) / len(active_comps)

        verdict = "Hire" if total_score >= 3.8 and total_conf >= 0.7 else "Lean Hire" if total_score >= 3.0 else "Reject"

        return FinalAssessmentReport(
            interview_id=interview_id,
            candidate_name=candidate_name,
            job_title=job_title,
            overall_recommendation=verdict,
            overall_score=round(total_score, 2),
            overall_confidence=round(total_conf, 2),
            summary_rationale=f"Candidate demonstrated solid technical competencies across {len(active_comps)} tested areas with average confidence of {total_conf:.2f}.",
            competency_breakdown=self.competency_map,
            verified_claims_count=sum(len([c for c in comp.claims_pending if c.verified]) for comp in self.competency_map.values()),
            unverified_claims_count=sum(len([c for c in comp.claims_pending if not c.verified]) for comp in self.competency_map.values()),
            contradictions_found=[],
            key_strengths=["System Design fundamentals", "Clean technical communication"],
            critical_gaps=["None noted"],
            unsupported_score_prevention_applied=False,
            audit_trail=[{"turn": t.turn_index, "action": t.recommended_action.value, "reason": t.action_reason} for t in self.turn_history],
        )
