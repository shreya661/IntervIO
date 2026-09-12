"""
Evaluation package for InterviewOne AI (Person 3).
Owns:
- Answer analysis and quote extraction
- Evidence management and live competency gap calculation
- Claims vs Evidence verification
- Contradiction detection
- Rubric scoring and confidence engine
- Final hiring assessment report generation
"""

from .schemas import (
    EvidenceStatus,
    DepthLevel,
    ActionRecommendation,
    Claim,
    EvidenceItem,
    Contradiction,
    CompetencyScore,
    CompetencyState,
    TurnAnalysisResult,
    EvaluationTurnResult,
    FinalAssessmentReport,
)
from .mocks import MockEvaluator, get_default_competencies
from .answer_analyzer import AnswerAnalyzer
from .evidence_manager import EvidenceManager
from .scoring import ScoringEngine
from .confidence import ConfidenceCalculator
from .contradiction_detector import ContradictionDetector
from .verifier import ClaimVerifier
from .report_generator import ReportGenerator
from .evaluator import Evaluator

__all__ = [
    "EvidenceStatus",
    "DepthLevel",
    "ActionRecommendation",
    "Claim",
    "EvidenceItem",
    "Contradiction",
    "CompetencyScore",
    "CompetencyState",
    "TurnAnalysisResult",
    "EvaluationTurnResult",
    "FinalAssessmentReport",
    "MockEvaluator",
    "get_default_competencies",
    "AnswerAnalyzer",
    "EvidenceManager",
    "ScoringEngine",
    "ConfidenceCalculator",
    "ContradictionDetector",
    "ClaimVerifier",
    "ReportGenerator",
    "Evaluator",
]
