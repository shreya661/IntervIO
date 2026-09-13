"""Deterministic practice-interview coach; not a recruiting decision system."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import StrEnum
import re
from multimodal.voice_analyzer import CandidateVoiceFeedback, VoiceObservation, VoiceObservationPresenter
from multimodal.resume_analyzer import ResumeProfile
from multimodal.visual_analyzer import VisualObservation
from multimodal.gemini_assistant import GeminiAnswerAnalysis, GeminiAssistant

class Difficulty(StrEnum): EASY="easy"; MODERATE="moderate"; CHALLENGING="challenging"
@dataclass(frozen=True)
class CoachQuestion:
    question: str; domain: str; topic: str; competency: str; difficulty: Difficulty; question_type: str; reason: str; expected_evidence: tuple[str,...]
@dataclass(frozen=True)
class AnswerReview:
    demonstrated: tuple[str,...]; missing: tuple[str,...]; supportive_feedback: str; needs_follow_up: bool


@dataclass(frozen=True)
class PracticePerformanceRecord:
    """Cumulative coaching record, never a hiring or screening decision."""

    strengths: tuple[str, ...] = ()
    knowledge_gaps: tuple[str, ...] = ()
    communication_observations: tuple[str, ...] = ()
    areas_to_improve: tuple[str, ...] = ()
    recommendations: tuple[str, ...] = ()
    answers_reviewed: int = 0
@dataclass(frozen=True)
class InterviewPerformanceReport:
    overall: str
    answer_content: str
    technical_understanding: str
    answer_structure: str
    voice_delivery: str | None
    speaking_pace: str | None = None
    pitch: str | None = None
    volume: str | None = None
    pauses: str | None = None
    filler_words: str | None = None
    fluency: str | None = None
    transcription_reliability: str | None = None
    baseline_comparison: str | None = None
    coaching_suggestions: tuple[str, ...] = ()
    next_practice: str = "Continue with the next practice question."
    next_question: CoachQuestion | None = None
@dataclass
class PracticeInterviewState:
    domain: str; goal: str; job_description: str|None=None; remaining_seconds: int=900; resume: ResumeProfile|None=None; questions: list[CoachQuestion]=field(default_factory=list); answers: list[str]=field(default_factory=list); answer_reviews: list[AnswerReview]=field(default_factory=list); demonstrated: set[str]=field(default_factory=set); voice_observations: list[VoiceObservation]=field(default_factory=list); visual_observations: list[VisualObservation]=field(default_factory=list); focus_events: list[str]=field(default_factory=list); performance: PracticePerformanceRecord=field(default_factory=PracticePerformanceRecord)

QuestionProvider = object


class AdaptiveInterviewCoach:
    def __init__(self, question_provider: QuestionProvider | None = None, ai_assistant: GeminiAssistant | None = None) -> None:
        self.question_provider = question_provider
        self.ai_assistant = ai_assistant
    def start(self, domain:str, goal:str="practice", *, job_description:str|None=None, remaining_seconds:int=900, resume:ResumeProfile|None=None)->tuple[PracticeInterviewState,CoachQuestion]:
        state=PracticeInterviewState(domain.strip() or "general",goal,job_description,remaining_seconds,resume)
        question=self._starter_question(state); state.questions.append(question); return state,question
    def answer(self,state:PracticeInterviewState,answer:str,*,transcription_reliable:bool=True,voice_feedback:CandidateVoiceFeedback|None=None)->tuple[AnswerReview,CoachQuestion|None]:
        if not transcription_reliable:
            review=AnswerReview((),(),"Some audio could not be transcribed reliably. Please repeat your answer.",True)
            state.performance=_update_performance(state.performance,review,voice_feedback)
            state.answer_reviews.append(review)
            return review,None
        current=state.questions[-1]; words=set(re.findall(r"[a-z]+",answer.lower())); shown=tuple(x for x in current.expected_evidence if all(part in words for part in x.split())); missing=tuple(x for x in current.expected_evidence if x not in shown)
        if self.ai_assistant and self.ai_assistant.enabled:
            try:
                return self._answer_with_ai(state, current, answer, voice_feedback)
            except (RuntimeError, ValueError, TypeError, KeyError, StopIteration):
                pass
        if not current.expected_evidence:
            shown=()
            missing=()
        state.demonstrated.update(shown); state.answers.append(answer)
        if not missing:
            review=AnswerReview(shown,(),"You demonstrated relevant concepts in this response.",False)
        elif shown:
            review=AnswerReview(shown,missing,"You were on the right track; let’s explore the missing part together.",True)
        else:
            review=AnswerReview((),missing,"That is a useful start. Let’s build on it.",True)
        question=self._offline_next_question(state, current, answer, review)
        state.performance=_update_performance(state.performance,review,voice_feedback)
        state.answer_reviews.append(review)
        state.questions.append(question); return review,question

    def _answer_with_ai(self, state: PracticeInterviewState, current: CoachQuestion, answer: str, voice_feedback: CandidateVoiceFeedback | None) -> tuple[AnswerReview, CoachQuestion]:
        try:
            analysis = self.ai_assistant.analyze_answer(
                question=current.question, answer=answer, domain=state.domain, goal=state.goal,
                resume=state.resume.to_dict() if state.resume else None,
            )
            review = AnswerReview(
                analysis.demonstrated, analysis.missing, analysis.feedback, analysis.needs_follow_up
            )
            levels = (Difficulty.EASY, Difficulty.MODERATE, Difficulty.CHALLENGING)
            next_difficulty = current.difficulty
            if not analysis.needs_follow_up and not analysis.missing:
                next_difficulty = levels[min(levels.index(current.difficulty) + 1, 2)]
            generation_state = self._state_for_generation(state)
            generation_state["answers"] = [*state.answers, answer]
            generation_state["demonstrated"] = sorted({*state.demonstrated, *analysis.demonstrated})
            generation_state["reviews"] = [
                *generation_state["reviews"],
                {"demonstrated": analysis.demonstrated, "missing": analysis.missing, "needs_follow_up": analysis.needs_follow_up},
            ]
            raw = self.ai_assistant.generate_question(
                question=current.question, answer=answer, analysis=analysis,
                domain=state.domain, goal=state.goal, difficulty=next_difficulty.value,
                previous_questions=tuple(item.question for item in state.questions),
                interview_state=generation_state,
            )
            question = self._question_from_raw(state, raw, next_difficulty)
            state.answers.append(answer)
            state.demonstrated.update(analysis.demonstrated)
            state.performance = _update_performance(state.performance, review, voice_feedback)
            state.answer_reviews.append(review)
            state.questions.append(question)
            return review, question
        except Exception:
            return self.answer(state, answer, voice_feedback=voice_feedback)

    def final_report(self, state: PracticeInterviewState) -> PracticePerformanceRecord:
        """Return the candidate's cumulative practice record.

        The record describes evidence and next practice steps. It intentionally
        contains no hiring recommendation, ranking, or rejection decision.
        """
        return state.performance
    def report(self, review:AnswerReview, next_question:CoachQuestion|None, *, voice_feedback:CandidateVoiceFeedback|None=None, observation:VoiceObservation|None=None, baseline:VoiceObservation|None=None)->InterviewPerformanceReport:
        """Candidate-facing practice report; content evidence remains primary."""
        content=("The response demonstrated " + _join(review.demonstrated) + ".") if review.demonstrated else "The response did not yet demonstrate the target concepts."
        if review.missing: content += " Practice " + _join(review.missing) + "."
        technical = "Relevant technical or domain evidence was demonstrated." if review.demonstrated else "The response needs more specific technical or domain evidence."
        structure = "The answer was relevant and included target evidence." if review.demonstrated else "Use a simple point, example, and result structure to keep the answer relevant."
        voice = self._voice_report(observation, baseline)
        suggestions=[]
        if review.missing: suggestions.append("Include a concrete example that addresses the missing concepts.")
        if voice_feedback and voice_feedback.suggestion: suggestions.append(voice_feedback.suggestion)
        if not suggestions: suggestions.append(review.supportive_feedback)
        overall = "The response covered the target concepts." if review.demonstrated else "The response is a useful starting point; add more specific evidence next time."
        return InterviewPerformanceReport(overall,content,technical,structure,voice_feedback.observation if voice_feedback else (voice[0] if voice else None),*(voice[1:] if voice else (None,)*8),tuple(suggestions[:3]),next_question.reason if next_question else "Repeat the response so the coach can continue.",next_question)

    def _voice_report(self, observation: VoiceObservation|None, baseline: VoiceObservation|None) -> tuple[str,...] | None:
        if observation is None: return None
        dashboard=VoiceObservationPresenter().present(observation, baseline=baseline)
        pace_text = {"Slow": "Your speaking pace was slow.", "Moderate": "Your speaking pace was moderate.", "Fast": "Your speaking pace was fast."}[dashboard.speaking_pace.label]
        pitch = "Pitch data was unavailable." if observation.pitch_mean_hz is None else ("Your pitch had limited variation." if (observation.pitch_variation or 0) < .08 else "Your pitch had noticeable variation.")
        volume = {"Stable": "Your audio volume was consistent.", "Variable": "Your audio volume varied during the response.", "Unavailable": "Audio volume data was unavailable."}[dashboard.volume.label]
        pauses = {"Minimal": "You used few meaningful pauses.", "Occasional": "You used occasional meaningful pauses.", "Frequent": "You used frequent meaningful pauses."}[dashboard.pauses.label]
        fillers = {"Low": "Your filler-word usage was low.", "Moderate": "Your filler-word usage was moderate.", "High": "Your filler-word usage was fairly frequent."}[dashboard.filler_words.label]
        fluency = "Your delivery was consistent." if dashboard.volume.label in {"Stable", "Unavailable"} and dashboard.pauses.label != "Frequent" else "Your delivery consistency could improve."
        baseline_text = dashboard.baseline_change.description if dashboard.baseline_change.available else "No personal baseline was available for comparison."
        overall = f"Your delivery had a {dashboard.speaking_pace.label.lower()} pace with {dashboard.volume.label.lower()} audio volume."
        reliability = {"Reliable": "The response was transcribed reliably.", "Needs Review": "The transcription should be reviewed before relying on delivery observations.", "Low Confidence": "The transcription was not reliable enough for strong delivery observations."}[dashboard.transcription.label]
        return (overall, pace_text, pitch, volume, pauses, fillers, fluency, reliability, baseline_text)
    def _starter_question(self, state: PracticeInterviewState) -> CoachQuestion:
        fallback = CoachQuestion(
            f"What is one {state.domain} problem you have solved, and how did you approach it?",
            state.domain, state.domain, "practical problem solving", Difficulty.EASY,
            "open_start", "The opening asks for concrete evidence relevant to the selected domain.", (state.domain,),
        )
        if self.ai_assistant and self.ai_assistant.enabled:
            try:
                raw = self.ai_assistant.generate_question(
                    question="", answer="", analysis=GeminiAnswerAnalysis((), (), "", False),
                    domain=state.domain, goal=state.goal, difficulty=Difficulty.EASY.value,
                    previous_questions=(), interview_state=self._state_for_generation(state),
                )
                return self._question_from_raw(state, raw, Difficulty.EASY)
            except Exception:
                pass
        return self._provided_question(state, fallback) if self.question_provider is not None else fallback

    def _offline_next_question(self, state: PracticeInterviewState, current: CoachQuestion, answer: str, review: AnswerReview) -> CoachQuestion:
        anchor = _answer_anchor(answer, current.expected_evidence, review.demonstrated)
        if anchor in {"the concept", "the target concepts"}:
            anchor = state.domain
        text = f"You mentioned {anchor}. How did you apply it in a real situation, and what result did you achieve?"
        fallback = CoachQuestion(text, state.domain, anchor, anchor, current.difficulty, "adaptive_fallback", "The question asks for concrete evidence from the candidate's response.", (anchor,))
        return self._provided_question(state, fallback) if self.question_provider is not None else fallback

    def _state_for_generation(self, state: PracticeInterviewState) -> dict[str, object]:
        return {
            "domain": state.domain, "goal": state.goal, "job_description": state.job_description,
            "resume": state.resume.to_dict() if state.resume else None,
            "questions": [q.question for q in state.questions], "answers": state.answers,
            "reviews": [{"demonstrated": r.demonstrated, "missing": r.missing, "needs_follow_up": r.needs_follow_up} for r in state.answer_reviews],
            "demonstrated": sorted(state.demonstrated), "performance": state.performance.answers_reviewed,
        }

    def _question_from_raw(self, state: PracticeInterviewState, raw: dict[str, object], difficulty: Difficulty) -> CoachQuestion:
        question = CoachQuestion(raw["question"], state.domain, raw["topic"], raw["competency"], difficulty, raw["question_type"], raw["reason"], tuple(raw["expected_evidence"]))
        _validate_candidate_question(question)
        if question.question in {item.question for item in state.questions}:
            raise ValueError("Generated question repeated a previous question")
        return question

    def _provided_question(self, state: PracticeInterviewState, fallback: CoachQuestion) -> CoachQuestion:
        try:
            raw=self.question_provider(state, fallback)
            if not isinstance(raw, dict): return fallback
            values={field: raw.get(field, getattr(fallback, field)) for field in CoachQuestion.__dataclass_fields__}
            if not all(isinstance(values[field], str) and values[field].strip() for field in ("question","domain","topic","competency","reason")): return fallback
            if values["domain"].lower() != state.domain.lower() or values["question"] in {q.question for q in state.questions}: return fallback
            values["difficulty"]=Difficulty(values["difficulty"])
            values["expected_evidence"]=tuple(x for x in values["expected_evidence"] if isinstance(x,str) and x.strip())
            if not values["expected_evidence"]: return fallback
            question = CoachQuestion(**values)
            _validate_candidate_question(question)
            return question
        except (AttributeError, KeyError, TypeError, ValueError):
            return fallback


_QUESTION_META_PATTERNS = (
    r"what should we (examine|explore|ask)",
    r"what (concept|topic) should we explore",
    r"based on your answer",
    r"what should (the agent|i) ask next",
    r"next question",
)


def _validate_candidate_question(question: CoachQuestion) -> None:
    """Reject planning text before it crosses into the candidate-facing UI."""
    normalized = question.question.strip().lower()
    if any(re.search(pattern, normalized) for pattern in _QUESTION_META_PATTERNS):
        raise ValueError("Question contains internal planning language")
    if not question.question.strip().endswith("?"):
        raise ValueError("Question must be phrased as a candidate-facing question")
    if not question.topic.strip() or question.topic.lower() in {"the concept", "the topic", "candidate-selected focus"}:
        raise ValueError("Question must identify a concrete topic")
    if not question.expected_evidence:
        raise ValueError("Question must identify expected evidence")
def _join(values:tuple[str,...])->str:
    return ", ".join(values) if values else "the target concepts"


def _answer_anchor(answer: str, expected: tuple[str, ...], shown: tuple[str, ...]) -> str:
    """Choose the first demonstrated concept in the candidate's own wording."""
    normalized = answer.lower()
    candidates = tuple(dict.fromkeys((*shown, *expected)))
    positions = [(normalized.find(candidate.lower()), candidate) for candidate in candidates if normalized.find(candidate.lower()) >= 0]
    if positions:
        return min(positions)[1]
    return shown[0] if shown else (expected[0] if expected else "the concept")


def _update_performance(
    current: PracticePerformanceRecord,
    review: AnswerReview,
    voice_feedback: CandidateVoiceFeedback | None,
) -> PracticePerformanceRecord:
    strengths = _append_unique(current.strengths, review.demonstrated)
    gaps = _append_unique(current.knowledge_gaps, review.missing)
    areas = list(current.areas_to_improve)
    recommendations = list(current.recommendations)
    if review.missing:
        areas = list(_append_unique(tuple(areas), ("Provide clearer evidence for " + _join(review.missing),)))
        recommendations = list(_append_unique(tuple(recommendations), ("Practice an example that demonstrates " + _join(review.missing) + ".",)))
    elif review.demonstrated:
        recommendations = list(_append_unique(tuple(recommendations), ("Continue by explaining trade-offs and real-world consequences.",)))
    else:
        recommendations = list(_append_unique(tuple(recommendations), ("Repeat the answer so the coach can analyze it reliably.",)))
    observations = current.communication_observations
    if voice_feedback is not None:
        observations = _append_unique(observations, (voice_feedback.observation,))
        if voice_feedback.suggestion:
            recommendations = list(_append_unique(tuple(recommendations), (voice_feedback.suggestion,)))
    return PracticePerformanceRecord(
        strengths, gaps, observations, tuple(areas), tuple(recommendations), current.answers_reviewed + 1
    )


def _append_unique(existing: tuple[str, ...], values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*existing, *(value for value in values if value))))
