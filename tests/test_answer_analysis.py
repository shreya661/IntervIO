"""
Unit tests for AnswerAnalyzer (Person 3).
"""

from evaluation.answer_analyzer import AnswerAnalyzer
from evaluation.schemas import DepthLevel


def test_answer_analyzer_strong_answer(sample_strong_answer):
    analyzer = AnswerAnalyzer()
    result = analyzer.analyze(
        question="How did you scale your notification system?",
        answer=sample_strong_answer,
        target_competency="System Design",
        turn_index=1,
    )

    assert result.technical_correctness >= 4.0
    assert result.depth_level in [DepthLevel.INTERMEDIATE, DepthLevel.ADVANCED]
    assert result.vagueness_score <= 0.3
    assert len(result.demonstrated_evidence) > 0
    # Verbatim quote test
    quote = result.demonstrated_evidence[0].quote
    assert quote in sample_strong_answer


def test_answer_analyzer_vague_answer(sample_vague_answer):
    analyzer = AnswerAnalyzer()
    result = analyzer.analyze(
        question="Describe your cloud architecture.",
        answer=sample_vague_answer,
        target_competency="System Design",
        turn_index=1,
    )

    assert result.vagueness_score >= 0.6
    assert result.needs_followup is True
    assert result.technical_correctness <= 3.0


def test_answer_analyzer_claim_detection(sample_ownership_claim_answer):
    analyzer = AnswerAnalyzer()
    result = analyzer.analyze(
        question="What was your contribution?",
        answer=sample_ownership_claim_answer,
        target_competency="System Design",
        turn_index=1,
    )

    assert len(result.claims_detected) > 0
    claim = result.claims_detected[0]
    assert claim.verification_needed is True
    assert "decisions did you personally make" in claim.verification_question
    assert result.needs_followup is True
