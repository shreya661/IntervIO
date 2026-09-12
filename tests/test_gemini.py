from types import SimpleNamespace

from interview_coach import AdaptiveInterviewCoach, Difficulty
from multimodal.gemini_assistant import GeminiAssistant


class FakeModels:
    def __init__(self, responses):
        self.responses = iter(responses)

    def generate_content(self, **_kwargs):
        return SimpleNamespace(text=next(self.responses))


class FakeClient:
    def __init__(self, responses):
        self.models = FakeModels(responses)


def test_gemini_answer_analysis_drives_question_without_voice_input():
    client = FakeClient([
        '{"question":"What part of Python have you used most?","topic":"Python usage","competency":"experience","question_type":"open_start","reason":"Relevant opening","expected_evidence":["Python"]}',
        '{"demonstrated":["list ordering"],"missing":["dictionary lookup"],"feedback":"Good comparison; explain lookup next.","needs_follow_up":true}',
        '{"question":"How would you explain dictionary lookup complexity?","topic":"dictionary lookup","competency":"data structures","question_type":"targeted_follow_up","reason":"The answer left lookup complexity unclear.","expected_evidence":["lookup"]}',
    ])
    coach = AdaptiveInterviewCoach(ai_assistant=GeminiAssistant(client=client))
    state, _ = coach.start("Python")
    review, question = coach.answer(state, "A list keeps order.")
    assert review.missing == ("dictionary lookup",)
    assert question.question == "How would you explain dictionary lookup complexity?"
    assert question.difficulty is Difficulty.EASY


def test_gemini_malformed_response_falls_back_to_deterministic_coach():
    client = FakeClient(["not json"])
    coach = AdaptiveInterviewCoach(ai_assistant=GeminiAssistant(client=client))
    state, _ = coach.start("Python")
    review, question = coach.answer(state, "A list stores ordered values.")
    assert review.demonstrated == ()
    assert question is not None