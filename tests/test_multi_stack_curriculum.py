import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.schemas.interview import ResumeProfile, InterviewState
from backend.api.interviews import (
    _generate_interview_plan,
    _build_context_questions,
    select_next_question,
    interviews,
)


client = TestClient(app)


def test_generate_interview_plan_multi_stack():
    """Verify the agent plans a 3-stage, 20-question interview derived from Resume and JD."""
    resume_prof = ResumeProfile(
        skills=["React", "TypeScript", "Next.js", "Redux"],
        technologies=["React", "TypeScript", "Node.js", "PostgreSQL"],
        projects=["Built high-throughput real-time collaboration canvas in React & WebSockets"],
        experience=["Senior Frontend Engineer at FinTech Corp"],
    )
    state = InterviewState(
        interview_id="test-plan-1",
        candidate_name="Alice Smith",
        company_name="Stripe",
        company_needs="High-throughput financial checkout UI and resilient state management",
        job_title="Staff Frontend Engineer",
        job_description="Architect scalable Next.js and TypeScript web applications with strict latency SLAs.",
        resume_profile=resume_prof,
        resume_available=True,
    )

    plan = _generate_interview_plan(state)
    assert plan.role_title == "Staff Frontend Engineer"
    assert "TypeScript" in plan.tech_stack or "React" in plan.tech_stack
    assert "Core Mechanics" in plan.stages[0].stage_name
    assert plan.stages[0].question_count == 10
    assert plan.stages[0].difficulty == "easy"

    assert "Architecture" in plan.stages[1].stage_name
    assert plan.stages[1].question_count == 5
    assert plan.stages[1].difficulty == "moderate"

    assert "Tricky Edge Cases" in plan.stages[2].stage_name
    assert plan.stages[2].question_count == 5
    assert plan.stages[2].difficulty == "tricky"
    assert plan.total_questions == 20


def test_build_context_questions_not_only_python():
    """Verify that candidate with React/TypeScript/Go gets non-Python questions matching their stack."""
    resume_prof = ResumeProfile(
        skills=["React", "Go", "Docker"],
        technologies=["React", "Go", "Docker"],
    )
    pool = _build_context_questions(
        resume_profile=resume_prof,
        job_description="Looking for Golang backend microservices engineer",
        company_needs="High concurrency microservices",
    )
    skills = [q["skill"] for q in pool]
    assert "React" in skills or "Go" in skills or "Docker" in skills
    # Check that it generated specific technical questions
    assert any("goroutine" in q["question"].lower() or "channel" in q["question"].lower() or "go" in q["question"].lower() for q in pool) or any("react" in q["question"].lower() for q in pool)


def test_interview_lifecycle_with_plan_and_job_description():
    """Verify full end-to-end API lifecycle with custom JD, company needs, and planning."""
    # 1. Create interview
    res = client.post("/interviews/?candidate_name=Bob&company_name=Uber&job_title=Distributed%20Systems%20Engineer")
    assert res.status_code == 200
    data = res.json()
    interview_id = data["interview_id"]
    assert data["company_name"] == "Uber"
    assert data["job_title"] == "Distributed Systems Engineer"

    # 2. Attach job description
    res_jd = client.post(
        f"/interviews/{interview_id}/job-description",
        data={
            "text": "Design high-throughput distributed systems in Java / Go with Kafka and Kubernetes.",
            "company_needs": "99.999% availability ride-hailing backend",
        },
    )
    assert res_jd.status_code == 200
    assert res_jd.json()["has_job_description"] is True

    # 3. Simulate resume upload via state directly
    state = interviews[interview_id]
    state.resume_available = True
    state.resume_profile = ResumeProfile(
        skills=["Java", "Spring Boot", "Kafka"],
        technologies=["Java", "Kafka", "PostgreSQL"],
        projects=["Order streaming pipeline in Apache Kafka"],
    )
    interviews[interview_id] = state

    # 4. Start interview
    res_start = client.post(f"/interviews/{interview_id}/start")
    assert res_start.status_code == 200
    started_data = res_start.json()
    assert started_data["status"] == "in_progress"
    assert started_data["question_number"] == 1
    assert started_data["interview_plan"] is not None
    assert started_data["interview_plan"]["total_questions"] == 20
    assert "STAGE 1/3" in started_data["next_action"]

    # 5. Submit answer
    res_ans = client.post(
        f"/interviews/{interview_id}/answer",
        json={"answer": "We used Kafka partition keys to ensure strict ordering of events per ride, and consumer groups to horizontally scale processing."},
    )
    assert res_ans.status_code == 200
    ans_data = res_ans.json()
    assert ans_data["question_number"] == 2
    assert len(ans_data["answers"]) == 1

    # 6. Check final assessment contains interview plan, company details, and HR scorecard
    res_report = client.get(f"/interviews/{interview_id}/assessment")
    assert res_report.status_code == 200
    report_data = res_report.json()
    assert report_data["company_name"] == "Uber"
    assert report_data["interview_plan"] is not None
    assert report_data["interview_plan"]["stages"][0]["question_count"] == 10
    assert report_data["hr_evaluation"] is not None
    assert report_data["hr_evaluation"]["overall_grade"] in ("A+", "A", "B+", "B", "C", "D")
    assert "competencies" in report_data["hr_evaluation"]
    assert len(report_data["hr_evaluation"]["competencies"]) >= 5
