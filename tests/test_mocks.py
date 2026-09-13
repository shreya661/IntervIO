"""
Unit tests verifying the MockEvaluator contract for Person 1 and Person 4.
"""

from evaluation.mocks import MockEvaluator
from evaluation.schemas import ActionRecommendation, EvidenceStatus


def test_mock_evaluator_initialization():
    evaluator = MockEvaluator()
    assert len(evaluator.competency_map) >= 4
    assert "System Design" in evaluator.competency_map
    assert evaluator.competency_map["System Design"].status == EvidenceStatus.UNTESTED


def test_mock_evaluator_strong_answer(sample_strong_answer):
    evaluator = MockEvaluator()
    result = evaluator.process_turn(
        turn_index=1,
        question="How did you scale your notification system?",
        answer=sample_strong_answer,
        current_competency="System Design",
        stt_confidence=0.95,
    )

    assert result.turn_index == 1
    assert len(result.new_evidence) > 0
    assert result.analysis.technical_correctness >= 4.0
    assert result.analysis.vagueness_score <= 0.3
    assert result.competency_tested == "System Design"
    assert result.live_competency_map["System Design"].score > 0.0


def test_mock_evaluator_claim_detection(sample_ownership_claim_answer):
    evaluator = MockEvaluator()
    result = evaluator.process_turn(
        turn_index=1,
        question="What was your role on the backend?",
        answer=sample_ownership_claim_answer,
        current_competency="System Design",
    )

    assert len(result.claims_flagged) > 0
    assert result.claims_flagged[0].verification_needed is True
    assert result.recommended_action == ActionRecommendation.VERIFY_CLAIM
    assert "Which specific architectural decision" in result.suggested_followup_question


def test_mock_evaluator_vague_answer(sample_vague_answer):
    evaluator = MockEvaluator()
    result = evaluator.process_turn(
        turn_index=1,
        question="Can you explain your cloud design?",
        answer=sample_vague_answer,
        current_competency="System Design",
    )

    assert result.analysis.vagueness_score >= 0.7
    assert result.recommended_action == ActionRecommendation.PROBE_VAGUE


def test_mock_evaluator_final_report():
    evaluator = MockEvaluator()
    evaluator.process_turn(
        turn_index=1,
        question="Tell me about Redis",
        answer="Redis is an in-memory key-value store with sharding and TTL caching.",
        current_competency="System Design",
    )

    report = evaluator.generate_final_report(
        interview_id="int_12345",
        candidate_name="Alice Smith",
        job_title="Senior Backend Engineer",
    )

    assert report.interview_id == "int_12345"
    assert report.candidate_name == "Alice Smith"
    assert report.overall_recommendation in ["Hire", "Lean Hire", "Reject", "Strong Hire"]
    assert len(report.competency_breakdown) > 0
