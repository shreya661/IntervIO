"""
Unit and integration tests for InterviewOne AI PDF Evaluation Report generator.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.pdf_report import generate_assessment_pdf
from backend.schemas.interview import InterviewState, ResumeProfile

client = TestClient(app)


def test_generate_assessment_pdf_structure():
    """Verify that generate_assessment_pdf produces valid PDF binary output."""
    sample_data = {
        "candidate_name": "Jordan Lee",
        "job_title": "Principal Systems Engineer",
        "company_name": "CloudScale Inc.",
        "overall_score": 8.7,
        "evidence_coverage": 90,
        "confidence": 85,
        "recommendation": "Strong candidate — recommend advancing",
        "questions_answered": 20,
        "hr_evaluation": {
            "overall_grade": "A",
            "overall_score": 8.7,
            "hiring_recommendation": "Strong Hire",
            "candidate_summary": "Exhibited outstanding mastery of distributed systems and calm poise under questioning.",
            "intro_grade": "A",
            "skills_grade": "A-",
            "behavioral_grade": "A",
            "competencies": [
                {
                    "category": "Distributed Consensus",
                    "grade": "A",
                    "score": 9.2,
                    "feedback": "Deep understanding of Raft log replication trade-offs.",
                },
                {
                    "category": "System Resiliency",
                    "grade": "A-",
                    "score": 8.5,
                    "feedback": "Articulated clean circuit breaker patterns.",
                },
            ],
            "composure_evaluation": {
                "overall_composure": "Composed & Confident",
                "poise_score": 9.0,
                "gaze_stability_pct": 94,
                "fidget_index": "Low / Grounded",
                "hr_observations": "Maintained direct eye-contact throughout technical architecture questions.",
            },
        },
        "competency_scores": [
            {"skill": "Raft", "score": 9.2},
            {"skill": "Kafka", "score": 8.5},
        ],
        "strengths": [
            "Demonstrated exceptional understanding of consensus algorithms",
            "Clear technical communication with architectural diagrams in mind",
        ],
        "gaps": [
            "Could expand further on dynamic quorum reconfiguration edge cases",
        ],
    }

    pdf_bytes = generate_assessment_pdf(sample_data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")


def test_get_assessment_pdf_endpoint():
    """Verify the GET /interviews/{id}/assessment/pdf endpoint returns the downloadable PDF."""
    resume_prof = ResumeProfile(
        skills=["Python", "FastAPI", "PostgreSQL"],
        technologies=["Python", "Docker", "Kubernetes"],
    )
    test_id = "test-pdf-interview-1"
    from backend.api.interviews import interviews

    interviews[test_id] = InterviewState(
        interview_id=test_id,
        candidate_name="Sarah Connor",
        company_name="Cyberdyne Systems",
        job_title="DevOps Engineer",
        resume_profile=resume_prof,
        resume_available=True,
    )

    # 1. Answer a question to ensure assessment data is present
    client.post(
        f"/interviews/{test_id}/answer",
        json={"answer": "We configured Prometheus alerting rules and multi-region Kubernetes deployments."},
    )

    # 2. Request PDF download
    res = client.get(f"/interviews/{test_id}/assessment/pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert "attachment" in res.headers["content-disposition"]
    assert "Technical_Evaluation_Report_Sarah_Connor.pdf" in res.headers["content-disposition"]
    assert res.content.startswith(b"%PDF-")
    assert len(res.content) > 1000
