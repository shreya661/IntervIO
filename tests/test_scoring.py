"""
Unit tests for ScoringEngine, ConfidenceCalculator, and Zero-Unsupported-Score Guardrail.
"""

from evaluation.scoring import ScoringEngine
from evaluation.confidence import ConfidenceCalculator
from evaluation.schemas import CompetencyState, EvidenceItem, DepthLevel, Claim, Contradiction


def test_zero_unsupported_score_guardrail_applied():
    """
    Candidate gave a seemingly strong answer (technical_accuracy=5.0),
    but only demonstrated SURFACE evidence.
    Guardrail MUST cap score to <= 3.5.
    """
    state = CompetencyState(
        competency="System Design",
        priority=5.0,
        evidence_list=[
            EvidenceItem(
                id="ev_surface_1",
                competency="System Design",
                demonstrated_fact="Mentioned microservices",
                quote="We used microservices",
                depth_level=DepthLevel.SURFACE,
                confidence_score=0.7,
            )
        ],
    )

    score_obj, guardrail_applied = ScoringEngine.evaluate_competency(
        state=state,
        latest_technical_accuracy=5.0,
    )

    assert guardrail_applied is True
    assert score_obj.overall_score <= 3.5
    assert "Guardrail applied" in score_obj.rationale


def test_high_score_permitted_with_advanced_evidence():
    """
    Candidate demonstrated ADVANCED evidence, so high score (>= 4.0) IS permitted.
    """
    state = CompetencyState(
        competency="System Design",
        priority=5.0,
        evidence_list=[
            EvidenceItem(
                id="ev_adv_1",
                competency="System Design",
                demonstrated_fact="Designed write-through cache with distributed locks",
                quote="Implemented Redlock algorithm with Redis",
                depth_level=DepthLevel.ADVANCED,
                confidence_score=0.9,
            )
        ],
    )

    score_obj, guardrail_applied = ScoringEngine.evaluate_competency(
        state=state,
        latest_technical_accuracy=4.5,
    )

    assert guardrail_applied is False
    assert score_obj.overall_score >= 4.0


def test_confidence_penalized_by_unverified_claim():
    """
    An unverified claim should lower confidence.
    """
    state_no_claims = CompetencyState(
        competency="Python",
        priority=4.0,
        evidence_list=[
            EvidenceItem(
                id="ev_py_1",
                competency="Python",
                demonstrated_fact="Asyncio event loop",
                quote="Used asyncio.gather",
                depth_level=DepthLevel.INTERMEDIATE,
                confidence_score=0.8,
            )
        ],
    )
    conf_clean = ConfidenceCalculator.calculate_competency_confidence(state_no_claims)

    state_with_claim = CompetencyState(
        competency="Python",
        priority=4.0,
        evidence_list=state_no_claims.evidence_list.copy(),
        claims_pending=[
            Claim(
                claim_id="cl_1",
                claim_text="I rewrote CPython compiler",
                target_competency="Python",
                verification_needed=True,
                verified=False,
            )
        ],
    )
    conf_with_claim = ConfidenceCalculator.calculate_competency_confidence(state_with_claim)

    assert conf_with_claim < conf_clean


def test_confidence_adjusted_by_stt():
    """
    Low STT confidence from Person 2 (e.g. 0.60) should proportionally lower confidence.
    """
    state = CompetencyState(
        competency="Python",
        priority=4.0,
        evidence_list=[
            EvidenceItem(
                id="ev_py_1",
                competency="Python",
                demonstrated_fact="Asyncio event loop",
                quote="Used asyncio.gather",
                depth_level=DepthLevel.INTERMEDIATE,
                confidence_score=0.8,
            )
        ],
    )
    conf_clear_audio = ConfidenceCalculator.calculate_competency_confidence(state, stt_confidence=1.0)
    conf_noisy_audio = ConfidenceCalculator.calculate_competency_confidence(state, stt_confidence=0.6)

    assert conf_noisy_audio < conf_clear_audio
