"""
Data contracts and shared Pydantic schemas for the InterviewOne AI Evaluation Module.
Shared between Person 1 (Agent Controller), Person 3 (Evaluation), and Person 4 (UI/API).
"""

from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid


class EvidenceStatus(str, Enum):
    UNTESTED = "untested"
    EVIDENCE_GAP = "evidence_gap"
    PARTIALLY_TESTED = "partially_tested"
    WELL_TESTED = "well_tested"


class DepthLevel(str, Enum):
    SURFACE = "surface"
    FUNDAMENTAL = "fundamental"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ActionRecommendation(str, Enum):
    PROBE_DEEPER = "PROBE_DEEPER"               # Candidate gave a strong answer, increase difficulty
    INVESTIGATE_FUNDAMENTALS = "INVESTIGATE_FUNDAMENTALS"  # Weak answer, check basic concepts
    PROBE_VAGUE = "PROBE_VAGUE"                 # Vague answer, ask for concrete examples/metrics
    VERIFY_CLAIM = "VERIFY_CLAIM"               # Broad claim detected, probe for direct contribution
    VERIFY_CONTRADICTION = "VERIFY_CONTRADICTION"  # Contradiction detected vs resume/past answers
    SWITCH_COMPETENCY = "SWITCH_COMPETENCY"     # Competency sufficiently tested, move to largest gap
    PRIORITIZE_HIGH_VALUE = "PRIORITIZE_HIGH_VALUE"  # Time pressure, focus on critical missing skills
    SUPPORT_INTERVENTION = "SUPPORT_INTERVENTION"    # Signal from Person 2 indicates pacing/clarity support needed


class Claim(BaseModel):
    """Represents an unverified assertion made by the candidate."""
    claim_id: str = Field(..., description="Unique ID of the claim")
    claim_text: str = Field(..., description="Exact claim, e.g., 'I built the entire backend architecture'")
    target_competency: str = Field(..., description="Competency this claim relates to")
    verification_needed: bool = Field(default=True, description="Whether this claim requires probe verification")
    verification_question: Optional[str] = Field(None, description="Targeted question to verify true ownership")
    verified: bool = Field(default=False, description="Whether the claim has been validated with demonstrated proof")
    verification_response: Optional[str] = Field(None, description="Candidate response to the verification question")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EvidenceItem(BaseModel):
    """Concrete proof of candidate knowledge or skill extracted from an answer."""
    id: str = Field(..., description="Unique ID of the evidence snippet")
    competency: str = Field(..., description="Target competency (e.g. 'System Design', 'Python')")
    demonstrated_fact: str = Field(..., description="Fact proven (e.g., 'Explained horizontal scaling and database read-replicas')")
    quote: str = Field(..., description="Direct verbatim quote snippet from candidate answer")
    depth_level: DepthLevel = Field(default=DepthLevel.INTERMEDIATE, description="Technical depth level demonstrated")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in this evidence extraction")
    turn_index: int = Field(default=0, description="Interview turn number where evidence was gathered")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Contradiction(BaseModel):
    """Inconsistency identified between current response and resume/prior responses."""
    id: str = Field(default_factory=lambda: f"contra_{uuid.uuid4().hex[:6]}", description="Unique contradiction ID")
    source_a: str = Field(..., description="Prior statement (from resume or earlier turn)")
    source_b: str = Field(..., description="Conflicting statement in current answer")
    description: str = Field(..., description="Explanation of why these two statements conflict")
    severity: str = Field(default="Medium", description="Low, Medium, or High")
    clarification_question: str = Field(..., description="Question to ask candidate to resolve the discrepancy")
    resolved: bool = Field(default=False, description="Whether candidate resolved the conflict")


class CompetencyScore(BaseModel):
    """Multi-dimensional rubric scoring for a single competency."""
    technical_accuracy: float = Field(default=0.0, ge=0.0, le=5.0)
    architectural_depth: float = Field(default=0.0, ge=0.0, le=5.0)
    practical_tradeoffs: float = Field(default=0.0, ge=0.0, le=5.0)
    communication_clarity: float = Field(default=0.0, ge=0.0, le=5.0)
    overall_score: float = Field(default=0.0, ge=0.0, le=5.0)
    rationale: str = Field(default="", description="Explainable justification citing evidence")


class CompetencyState(BaseModel):
    """Live state for a specific competency in the interview."""
    competency: str
    priority: float = Field(default=3.0, ge=1.0, le=5.0, description="Importance for the job (1 to 5)")
    score: float = Field(default=0.0, ge=0.0, le=5.0, description="Current score grounded in evidence")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence level (0 to 1)")
    status: EvidenceStatus = Field(default=EvidenceStatus.UNTESTED)
    evidence_list: List[EvidenceItem] = Field(default_factory=list)
    claims_pending: List[Claim] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list, description="Specific sub-skills still unproven")

    @property
    def evidence_gap(self) -> float:
        """Dynamic gap score used by Person 1's question selection formula."""
        return max(0.0, 1.0 - self.confidence) * self.priority


class TurnAnalysisResult(BaseModel):
    """Raw analytical output extracted from a single candidate answer."""
    demonstrated_evidence: List[EvidenceItem] = Field(default_factory=list)
    claims_detected: List[Claim] = Field(default_factory=list)
    contradictions_detected: List[Contradiction] = Field(default_factory=list)
    technical_correctness: float = Field(default=3.0, ge=0.0, le=5.0)
    depth_level: DepthLevel = Field(default=DepthLevel.FUNDAMENTAL)
    vagueness_score: float = Field(default=0.0, ge=0.0, le=1.0, description="1.0 is pure buzzwords, 0.0 is highly concrete")
    vagueness_reason: Optional[str] = None
    gaps_identified: List[str] = Field(default_factory=list)
    needs_followup: bool = Field(default=False)
    followup_angle: Optional[str] = None


class EvaluationTurnResult(BaseModel):
    """Complete update package emitted by Person 3 at the end of each turn."""
    turn_index: int
    competency_tested: str
    analysis: TurnAnalysisResult
    new_evidence: List[EvidenceItem]
    claims_flagged: List[Claim]
    contradictions: List[Contradiction]
    live_competency_map: Dict[str, CompetencyState]
    recommended_action: ActionRecommendation
    action_reason: str
    suggested_followup_question: Optional[str] = None


class InterviewMode(str, Enum):
    ASSESSMENT = "assessment"          # §13.1 — pure evaluation, no coaching
    PRACTICE = "practice"              # §13.2 — hints and feedback allowed
    CONFIDENCE_COACH = "confidence_coach"  # §13.3 — pacing support provided


class FinalAssessmentReport(BaseModel):
    """Complete post-interview evaluation dossier for recruiters and hiring managers."""
    interview_id: str
    candidate_name: str
    job_title: str
    interview_mode: InterviewMode = Field(
        default=InterviewMode.ASSESSMENT,
        description="Mode in which the interview was conducted (impacts report interpretation)"
    )
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    interview_duration_seconds: Optional[int] = Field(None, description="Total interview duration in seconds")
    overall_recommendation: str = Field(..., description="Strong Hire | Hire | Lean Hire | Lean Reject | Reject")
    overall_score: float = Field(..., ge=0.0, le=5.0)
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    summary_rationale: str
    competency_breakdown: Dict[str, CompetencyState]
    verified_claims_count: int
    unverified_claims_count: int
    contradictions_found: List[Contradiction]
    key_strengths: List[str]
    critical_gaps: List[str]
    unsupported_score_prevention_applied: bool = Field(
        default=False,
        description="Whether any inflated score was capped due to lack of verified evidence"
    )
    support_interventions_count: int = Field(
        default=0,
        description="Number of SUPPORT_INTERVENTION actions taken. Coached answers should not be interpreted as raw performance."
    )
    answer_changes_detected: int = Field(
        default=0,
        description="Number of times the candidate changed or retracted a prior statement."
    )
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list)
