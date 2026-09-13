from fastapi.testclient import TestClient

from multimodal.live_voice import VoiceTurnStatus
from multimodal.resume_analyzer import ResumeProfile
from voice_demo import create_app


class FakeResult:
    def to_payload(self):
        return {"status": VoiceTurnStatus.ACCEPTED.value, "message": None}


class FakeProcessor:
    def __init__(self) -> None:
        self.received = None

    def process_bytes(self, audio: bytes, *, filename: str, language: str | None):
        self.received = (audio, filename, language)
        return FakeResult()


def test_voice_demo_serves_page_and_forwards_browser_upload():
    processor = FakeProcessor()
    client = TestClient(create_app(lambda: processor))
    assert client.get("/health").json()["status"] == "ok"
    assert "Start recording" in client.get("/").text
    response = client.post("/api/voice/analyze", files={"audio": ("answer.webm", b"audio", "audio/webm")})
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert processor.received == (b"audio", "answer.webm", None)


def test_coach_starts_with_domain_question():
    client = TestClient(create_app(lambda: FakeProcessor()))
    response = client.post("/api/coach/start", data={"domain": "Python"})
    assert response.status_code == 200
    body = response.json()
    assert body["question"]["difficulty"] == "easy"
    assert body["question"]["domain"] == "Python"


def test_domains_and_invalid_resume_are_available():
    client = TestClient(create_app(lambda: FakeProcessor()))
    domains = client.get("/api/domains").json()["domains"]
    assert "Backend" in domains and "Finance" in domains and "Other/Custom" in domains
    response = client.post("/api/resume/analyze", files={"resume": ("resume.txt", b"text", "text/plain")})
    assert response.status_code == 415


def test_final_report_contains_practice_record_and_graph_series():
    client = TestClient(create_app(lambda: FakeProcessor()))
    started = client.post("/api/coach/start", data={"domain": "Backend"}).json()
    report = client.get(f"/api/coach/{started['interview_id']}/report")
    assert report.status_code == 200
    body = report.json()
    assert body["practice_record"]["answers_reviewed"] == 0
    assert "speech_rate_wpm" in body["voice_graphs"]
    assert "candidate_report" in body
    assert "overall" in body["candidate_report"]
    assert "coach_feedback" in body["candidate_report"]
    assert "final-record" not in client.get("/").text


def test_resume_context_does_not_force_starting_question(monkeypatch):
    monkeypatch.setattr("voice_demo._coach.ai_assistant", None)
    client = TestClient(create_app(lambda: FakeProcessor()))
    from voice_demo import _resumes
    _resumes["resume-test"] = ResumeProfile(projects=("Notification API",), technologies=("FastAPI",))
    started = client.post(
        "/api/coach/start", data={"domain": "Backend", "resume_id": "resume-test"}
    ).json()
    assert "Notification API" not in started["question"]["question"]


def test_browser_focus_events_are_logged_as_neutral_technical_signals():
    from voice_demo import _sessions

    client = TestClient(create_app(lambda: FakeProcessor()))
    started = client.post("/api/coach/start", data={"domain": "Backend"}).json()
    state = _sessions[started["interview_id"]]
    state.focus_events.extend(["window_blur", "page_hidden"])
    report = client.get(f"/api/coach/{started['interview_id']}/report").json()
    assert report["practice_focus"]["browser_focus_events"] == 2
    assert "not evidence" in report["practice_focus"]["note"]
