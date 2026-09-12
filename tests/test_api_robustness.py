import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.schemas.interview import InterviewState
from backend.api.interviews import interviews

client = TestClient(app)


def test_root_endpoint():
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert data["service"] == "InterviewOne AI Backend"
    assert "docs" in data
    assert "health" in data


def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_create_interview_with_json_body():
    payload = {
        "candidate_name": "Marcus Aurelius",
        "job_title": "Principal Reliability Engineer",
        "company_name": "Google Cloud",
        "company_needs": "High-scale distributed systems reliability",
    }
    res = client.post("/interviews/", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["candidate_name"] == "Marcus Aurelius"
    assert data["job_title"] == "Principal Reliability Engineer"
    assert data["company_name"] == "Google Cloud"
    assert "interview_id" in data


def test_create_interview_with_query_params():
    res = client.post("/interviews/?candidate_name=Ada%20Lovelace&job_title=Algorithms%20Engineer")
    assert res.status_code == 200
    data = res.json()
    assert data["candidate_name"] == "Ada Lovelace"
    assert data["job_title"] == "Algorithms Engineer"


def test_create_interview_missing_name_returns_422():
    res = client.post("/interviews/", json={})
    assert res.status_code == 422


def test_end_interview_idempotency():
    # Setup interview state directly
    test_id = "test-idempotent-end"
    interviews[test_id] = InterviewState(
        interview_id=test_id,
        candidate_name="Grace Hopper",
        status="in_progress",
    )

    # First call to /end
    res1 = client.post(f"/interviews/{test_id}/end")
    assert res1.status_code == 200
    assert res1.json()["status"] == "completed"

    # Second call to /end should also succeed (idempotent)
    res2 = client.post(f"/interviews/{test_id}/end")
    assert res2.status_code == 200
    assert res2.json()["status"] == "completed"
