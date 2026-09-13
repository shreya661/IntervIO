"""
End-to-end integration tests for Master Evaluator pipeline.
"""

from evaluation.evaluator import Evaluator
from evaluation.schemas import ActionRecommendation, EvidenceStatus


def test_evaluator_claim_probe_and_resolution_flow():
    evaluator = Evaluator()

    # Turn 1: Candidate makes a broad claim
    turn1 = evaluator.process_turn(
        turn_index=1,
        question="What did you build in your previous role?",
        answer="I designed the entire backend architecture for the real-time notification system myself.",
        current_competency="System Design",
    )

    assert turn1.recommended_action == ActionRecommendation.VERIFY_CLAIM
    assert len(turn1.claims_flagged) == 1
    assert "personally make" in turn1.suggested_followup_question.lower()

    # Turn 2: Candidate answers the probe with concrete technical trade-offs
    turn2 = evaluator.process_turn(
        turn_index=2,
        question=turn1.suggested_followup_question,
        answer=(
            "I chose Redis Pub/Sub for low latency fan-out and configured Celery workers "
            "with Redis read replicas to prevent database connection bottlenecks."
        ),
        current_competency="System Design",
    )

    # Claim should be resolved and converted into formal evidence
    claim = list(evaluator.evidence_manager.claims_ledger.values())[0]
    assert claim.verified is True

    # The competency score and evidence should be updated
    comp = turn2.live_competency_map["System Design"]
    assert len(comp.evidence_list) >= 1
    assert comp.score > 0.0


def test_evaluator_vague_answer_flow():
    evaluator = Evaluator()

    result = evaluator.process_turn(
        turn_index=1,
        question="How does your cache handle eviction?",
        answer="It is very scalable, clean, and uses best practices.",
        current_competency="System Design",
    )

    assert result.recommended_action == ActionRecommendation.PROBE_VAGUE
    assert result.suggested_followup_question is not None


def test_evaluator_final_report_generation():
    evaluator = Evaluator()

    # Simulate 2 turns
    evaluator.process_turn(
        turn_index=1,
        question="Explain Python GIL and multiprocessing",
        answer="The Global Interpreter Lock prevents multiple native threads from executing Python bytecodes simultaneously. We used multiprocessing to bypass GIL for CPU-bound tasks.",
        current_competency="Python",
    )
    evaluator.process_turn(
        turn_index=2,
        question="How do you handle indexing in PostgreSQL?",
        answer="We used B-tree composite indices on user_id and created_at to support range queries with EXPLAIN ANALYZE verification.",
        current_competency="Database & SQL",
    )

    report = evaluator.generate_final_report(
        interview_id="int_demo_99",
        candidate_name="Bob Developer",
        job_title="Senior Fullstack Engineer",
    )

    assert report.interview_id == "int_demo_99"
    assert report.candidate_name == "Bob Developer"
    assert report.overall_score > 0.0
    assert report.overall_confidence > 0.0
    assert len(report.audit_trail) == 2
