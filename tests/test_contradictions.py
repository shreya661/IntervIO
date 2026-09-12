"""
Unit tests for ContradictionDetector.
"""

from evaluation.contradiction_detector import ContradictionDetector


def test_resume_contradiction_detection():
    detector = ContradictionDetector()
    resume = "Senior Cloud Engineer with 4 years experience leading Kubernetes cluster deployments and Helm charts."
    answer = "I have never worked with Kubernetes before. I only deployed simple scripts to a single VM."

    contradictions = detector.detect_contradictions(
        current_answer=answer,
        resume_context=resume,
    )

    assert len(contradictions) > 0
    c = contradictions[0]
    assert c.severity == "High"
    assert "Kubernetes" in c.description or "kubernetes" in c.description
    assert "clarify" in c.clarification_question.lower()


def test_prior_turn_contradiction_detection():
    detector = ContradictionDetector()
    prior_answers = [
        {"turn": 1, "answer": "In our initial design we had no cache and only communicated directly with MySQL."}
    ]
    current_answer = "As mentioned earlier, we used Redis cache in front of every service to handle the peak reads."

    contradictions = detector.detect_contradictions(
        current_answer=current_answer,
        prior_answers=prior_answers,
    )

    assert len(contradictions) > 0
    c = contradictions[0]
    assert "Turn 1" in c.source_a
    assert "caching" in c.description.lower() or "cache" in c.description.lower()


def test_no_false_positive_contradiction():
    detector = ContradictionDetector()
    resume = "Python backend developer experienced with FastAPI and PostgreSQL."
    answer = "In my last role I built REST APIs using FastAPI and wrote queries against PostgreSQL."

    contradictions = detector.detect_contradictions(
        current_answer=answer,
        resume_context=resume,
    )

    assert len(contradictions) == 0
