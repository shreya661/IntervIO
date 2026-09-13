from types import SimpleNamespace

from interview_coach import AdaptiveInterviewCoach
from multimodal.gemini_assistant import GeminiAssistant
from multimodal.resume_analyzer import ResumeProfile
from multimodal.voice_analyzer import CandidateVoiceFeedback


class FakeModels:
    def __init__(self, responses):
        self.responses = iter(responses)

    def generate_content(self, **_kwargs):
        return SimpleNamespace(text=next(self.responses))


class FakeClient:
    def __init__(self, responses):
        self.models = FakeModels(responses)


def generated(question, topic, reason="Useful now"):
    return f'{{"question":"{question}","topic":"{topic}","competency":"{topic}","question_type":"adaptive","reason":"{reason}","expected_evidence":["{topic}"]}}'


ANALYSIS = '{"demonstrated":["relevant evidence"],"missing":[],"feedback":"Useful answer.","needs_follow_up":false}'


def test_same_context_can_produce_different_starting_questions():
    first = AdaptiveInterviewCoach(ai_assistant=GeminiAssistant(client=FakeClient([
        generated("How would you validate a pipeline's output?", "validation")
    ])))
    second = AdaptiveInterviewCoach(ai_assistant=GeminiAssistant(client=FakeClient([
        generated("Which Python behavior has mattered most in your work?", "runtime behavior")
    ])))
    _, first_question = first.start("Python", goal="backend interview")
    _, second_question = second.start("Python", goal="backend interview")
    assert first_question.question != second_question.question


def test_different_answers_produce_different_next_questions():
    responses = [
        generated("How would you test a cache invalidation decision?", "testing"),
        ANALYSIS,
        generated("What would you test next?", "testing"),
        generated("How would you investigate a latency regression?", "diagnostics"),
        ANALYSIS,
        generated("What signal would you inspect next?", "observability"),
    ]
    first = AdaptiveInterviewCoach(ai_assistant=GeminiAssistant(client=FakeClient(responses[:3])))
    second = AdaptiveInterviewCoach(ai_assistant=GeminiAssistant(client=FakeClient(responses[3:])))
    state, _ = first.start("Backend")
    _, testing_question = first.answer(state, "I would write tests around stale values.")
    state, _ = second.start("Backend")
    _, latency_question = second.answer(state, "I would inspect traces and compare timings.")
    assert testing_question.question != latency_question.question


def test_next_question_is_generated_from_state_not_a_first_question_mapping():
    coach = AdaptiveInterviewCoach(ai_assistant=GeminiAssistant(client=FakeClient([
        generated("How do you decide where validation belongs?", "validation"),
        ANALYSIS,
        generated("What evidence would change your conclusion?", "evidence"),
    ])))
    state, _ = coach.start("Backend")
    _, next_question = coach.answer(state, "I would compare observed behavior with the contract.")
    assert next_question.topic == "evidence"


def test_previous_question_is_not_repeated_when_agent_repeats_it():
    repeated = generated("Explain an API boundary you designed.", "API boundary")
    coach = AdaptiveInterviewCoach(ai_assistant=GeminiAssistant(client=FakeClient([
        repeated, repeated,
    ])))
    state, first = coach.start("Backend")
    _, next_question = coach.answer(state, "I separated transport from domain logic.")
    assert next_question.question != first.question
    assert "what should we examine" not in next_question.question.lower()
    assert next_question.question.endswith("?")


def test_planning_text_from_agent_is_never_exposed_to_candidate():
    coach = AdaptiveInterviewCoach(ai_assistant=GeminiAssistant(client=FakeClient([
        generated("What should we examine next about the concept based on your answer?", "concept"),
        ANALYSIS,
        generated("What should we examine next about the concept based on your answer?", "concept"),
    ])))
    state, question = coach.start("Backend")
    assert "what should we examine" not in question.question.lower()
    _, next_question = coach.answer(state, "I separated transport from domain logic.")
    assert "what should we examine" not in next_question.question.lower()
    assert next_question.question.endswith("?")
    assert next_question.topic not in {"the concept", "candidate-selected focus"}


def test_agent_can_change_topic_when_answer_warrants_it():
    coach = AdaptiveInterviewCoach(ai_assistant=GeminiAssistant(client=FakeClient([
        generated("Describe a deployment decision you made.", "deployment"),
        ANALYSIS,
        generated("How did you protect customer data?", "security"),
    ])))
    state, _ = coach.start("Backend")
    _, question = coach.answer(state, "The important issue was access control and data exposure.")
    assert question.topic == "security"


def test_offline_mode_has_no_hardcoded_question_sequence():
    coach = AdaptiveInterviewCoach()
    state, first = coach.start("Python", goal="practice")
    _, second = coach.answer(state, "I would inspect the failing request and its inputs.")
    assert "trade-off" not in second.question.lower()
    assert "scaling issue" not in second.question.lower()
    assert first.question != second.question


def test_low_stt_is_recorded_without_generating_a_question():
    coach = AdaptiveInterviewCoach()
    state, _ = coach.start("Python")
    review, question = coach.answer(state, "audio", transcription_reliable=False)
    assert question is None
    assert review.needs_follow_up
    assert coach.final_report(state).answers_reviewed == 1


def test_candidate_report_keeps_voice_feedback():
    coach = AdaptiveInterviewCoach()
    state, _ = coach.start("Python")
    review, next_question = coach.answer(
        state, "I would inspect the failing request.",
        voice_feedback=CandidateVoiceFeedback("Your audio level varied.", "Keep the microphone distance consistent."),
    )
    report = coach.report(review, next_question, voice_feedback=CandidateVoiceFeedback("Your audio level varied.", "Keep the microphone distance consistent."))
    assert report.voice_delivery == "Your audio level varied."
    assert "microphone" in report.coaching_suggestions[-1]


def test_resume_is_context_not_a_mandatory_first_topic():
    coach = AdaptiveInterviewCoach()
    _, question = coach.start("Backend", resume=ResumeProfile(projects=("Payments API",)))
    assert question.topic != "resume experience"
