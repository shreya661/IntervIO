"""
Unit tests for ClaimVerifier and ReportGenerator.
"""

from evaluation.verifier import ClaimVerifier
from evaluation.schemas import Claim, FinalAssessmentReport, EvidenceStatus, CompetencyState
from evaluation.report_generator import ReportGenerator


def test_claim_verifier_probe_generation():
    claim = Claim(
        claim_id="cl_arch_01",
        claim_text="I designed the entire backend architecture from scratch.",
        target_competency="System Design",
    )
    probe = ClaimVerifier.generate_probe(claim)
    assert "architectural decision" in probe.lower() or "trade-off" in probe.lower()


def test_claim_verifier_evaluation_success():
    claim = Claim(
        claim_id="cl_arch_01",
        claim_text="I designed the entire backend architecture.",
        target_competency="System Design",
    )
    response = (
        "I chose PostgreSQL with B-tree indices and placed Redis cache in front to reduce read latency. "
        "I also added Celery workers with a partitioned message queue to decouple HTTP requests."
    )
    verified, rationale = ClaimVerifier.evaluate_probe_response(claim, response)
    assert verified is True
    assert "agency" in rationale.lower() or "trade-offs" in rationale.lower()


def test_claim_verifier_evaluation_failure_on_disclaimer():
    claim = Claim(
        claim_id="cl_arch_01",
        claim_text="I designed the entire backend architecture.",
        target_competency="System Design",
    )
    response = "Well, not really me. My tech lead chose the architecture and I mostly looked at the logs."
    verified, rationale = ClaimVerifier.evaluate_probe_response(claim, response)
    assert verified is False
    assert "retracted" in rationale.lower() or "ownership" in rationale.lower()


def test_report_generator_markdown():
    report = FinalAssessmentReport(
        interview_id="int_test_123",
        candidate_name="Charlie Test",
        job_title="Lead Architect",
        overall_recommendation="Strong Hire",
        overall_score=4.5,
        overall_confidence=0.88,
        summary_rationale="Exceptional technical answers with verified high-scale architecture experience.",
        competency_breakdown={
            "System Design": CompetencyState(
                competency="System Design",
                priority=5.0,
                score=4.5,
                confidence=0.88,
                status=EvidenceStatus.WELL_TESTED,
            )
        },
        verified_claims_count=2,
        unverified_claims_count=0,
        contradictions_found=[],
        key_strengths=["Distributed systems depth"],
        critical_gaps=[],
        unsupported_score_prevention_applied=False,
        audit_trail=[{"turn": 1, "action": "PROBE_DEEPER", "reason": "Strong answer"}],
    )

    md = ReportGenerator.generate_markdown(report)
    assert "# InterviewOne AI — Candidate Assessment Dossier" in md
    assert "STRONG HIRE" in md
    assert "Charlie Test" in md
    assert "System Design" in md
