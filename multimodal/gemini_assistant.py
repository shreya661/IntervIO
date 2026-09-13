"""Optional Gemini reasoning for resume and interview language tasks."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any


@dataclass(frozen=True)
class GeminiAnswerAnalysis:
    demonstrated: tuple[str, ...]
    missing: tuple[str, ...]
    feedback: str
    needs_follow_up: bool


class GeminiAssistant:
    """Use Gemini for text reasoning; voice metrics remain Python-owned."""

    def __init__(self, *, api_key: str | None = None, model: str = "gemini-2.0-flash", client: Any | None = None) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model
        self._client = client

    @property
    def enabled(self) -> bool:
        return bool(self.api_key or self._client)

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        try:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
            return self._client
        except Exception as exc:
            raise RuntimeError(f"Could not initialize Gemini: {exc}") from exc

    def _generate(self, prompt: str) -> dict[str, Any]:
        response = self._get_client().models.generate_content(
            model=self.model, contents=prompt, config={"response_mime_type": "application/json"}
        )
        raw = getattr(response, "text", None)
        if not isinstance(raw, str):
            raise ValueError("Gemini returned no text")
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        value = json.loads(cleaned)
        if not isinstance(value, dict):
            raise ValueError("Gemini response was not an object")
        return value

    def analyze_resume(self, resume_text: str, base_profile: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            "Extract only facts explicitly present in this resume for a practice coach. "
            "Return JSON arrays named skills, education, projects, experience, technologies, "
            "achievements, other_details. Do not infer or invent facts. Merge the deterministic "
            f"profile where accurate. PROFILE: {json.dumps(base_profile)} RESUME: {resume_text[:30000]}"
        )
        value = self._generate(prompt)
        return {key: _string_tuple(value.get(key, base_profile.get(key, ()))) for key in _PROFILE_KEYS}

    def analyze_answer(self, *, question: str, answer: str, domain: str, goal: str, resume: dict[str, Any] | None = None) -> GeminiAnswerAnalysis:
        prompt = (
            "You are a supportive practice-interview coach, not a recruiter. Analyze the answer "
            "only against the actual question. Do not require generic contribution, result, example, "
            "or tradeoff items unless the question asks for them. Return JSON with arrays demonstrated "
            "and missing, feedback string, and needs_follow_up boolean. "
            f"QUESTION: {question} DOMAIN: {domain} GOAL: {goal} RESUME: {json.dumps(resume or {})} "
            f"ANSWER: {answer[:12000]}"
        )
        value = self._generate(prompt)
        return GeminiAnswerAnalysis(
            _string_tuple(value.get("demonstrated", ())),
            _string_tuple(value.get("missing", ())),
            str(value.get("feedback", "Let’s build on your answer."))[:1000],
            bool(value.get("needs_follow_up", False)),
        )

    def generate_question(self, *, question: str, answer: str, analysis: GeminiAnswerAnalysis, domain: str, goal: str, difficulty: str, previous_questions: tuple[str, ...], interview_state: dict[str, Any] | None = None) -> dict[str, Any]:
        prompt = (
            "Act as an adaptive practice-interview agent. Generate exactly one newly written question "
            "that is useful now. Reason over the complete interview state and the candidate's actual "
            "answer. Do not follow a sequence, question bank, rubric order, template chain, or random "
            "rotation. Do not repeat a question or substantially repeat an explored topic. A follow-up "
            "is justified only by evidence in the answer. You may change topic when that is more useful. "
            "Choose difficulty from the evidence, not from a fixed progression. Return JSON with question, "
            "topic, competency, question_type, reason, and expected_evidence array. "
            f"DOMAIN: {domain} GOAL: {goal} DIFFICULTY: {difficulty} CURRENT QUESTION: {question} "
            f"ANSWER: {answer[:10000]} DEMONSTRATED: {json.dumps(analysis.demonstrated)} "
            f"MISSING: {json.dumps(analysis.missing)} PREVIOUS: {json.dumps(previous_questions)} "
            f"INTERVIEW_STATE: {json.dumps(interview_state or {})}"
        )
        value = self._generate(prompt)
        required = ("question", "topic", "competency", "question_type", "reason")
        if not all(isinstance(value.get(key), str) and value[key].strip() for key in required):
            raise ValueError("Gemini question response is incomplete")
        expected_evidence = _string_tuple(value.get("expected_evidence", ()))
        question = value["question"].strip()
        if _contains_planning_language(question) or not question.endswith("?") or not expected_evidence:
            raise ValueError("Gemini returned a non-candidate-facing question")
        return {key: value[key].strip() for key in required} | {"expected_evidence": expected_evidence}

    def generate_curriculum_question(
        self,
        *,
        question_number: int,
        difficulty: str,
        resume_profile: dict[str, Any] | None,
        job_description: str | None,
        company_name: str | None,
        company_needs: str | None,
        previous_questions: list[str],
        last_answer: str = "",
        last_depth: str = "",
    ) -> dict[str, Any]:
        """
        Generate an interview question (1–20) as an Agentic HR & Talent Partner.
        Follows authentic HR interview methodology:
        - Q1: Warm greeting, self-introduction, career story & role motivation (simpler opening).
        - Q2: Resume walkthrough & key project strengths in candidate's own words.
        - Q3–10: Resume skills & technical verification (simpler to moderate depth in candidate's actual stack).
        - Q11–15: Behavioral, ownership, teamwork & STAR situational questions.
        - Q16–20: Culture fit, tricky dilemmas, stakeholder management & role alignment.
        """
        prompt = (
            "You are an expert Agentic Technical HR & Talent Partner conducting an authentic, professional interview for "
            f"{company_name or 'the hiring company'}.\n\n"
            f"COMPANY NEEDS & DOMAIN: {company_needs or 'General high-performance engineering & collaborative team culture'}\n"
            f"JOB DESCRIPTION & ROLE: {job_description or 'Software Engineer'}\n"
            f"CANDIDATE RESUME: {json.dumps(resume_profile or {})}\n"
            f"CURRICULUM TURN: Question {question_number} of 20 (Target Tier: {difficulty.upper()})\n"
            f"ALREADY ASKED QUESTIONS (DO NOT REPEAT): {json.dumps(previous_questions)}\n"
            f"LAST CANDIDATE ANSWER: {last_answer[:2000]}\n"
            f"ASSESSED ANSWER DEPTH: {last_depth}\n\n"
            "HR INTERVIEW GUIDELINES:\n"
            "1. TONE & PERSONA: Warm, encouraging, empathetic, and professional HR Talent Partner. Ask the question naturally as an HR leader interviews candidates.\n"
            "2. SIMPLER START FOR Q1 & Q2:\n"
            "   - If Question 1: Ask a warm, simpler introductory question inviting the candidate to introduce themselves, share their career journey, and explain what excites them about this role.\n"
            "   - If Question 2: Reference their uploaded resume directly (e.g. key project or core skill) and ask them to walk through their main contributions and top strengths.\n"
            "3. FOR QUESTIONS 3–10 (Resume Skills & Hands-On Verification):\n"
            "   - Probe specific skills, technologies, and achievements listed on their resume (e.g. React, TypeScript, Java, Go, SQL, APIs, Cloud). Start accessible and progressively explore their design choices.\n"
            "   - DO NOT default to Python unless their resume or the role specifically focuses on Python.\n"
            "4. FOR QUESTIONS 11–15 (Behavioral & STAR Method):\n"
            "   - Ask behavioral questions on team collaboration, conflict resolution, managing tight deadlines, or taking ownership when an outage/bug occurred.\n"
            "5. FOR QUESTIONS 16–20 (Culture Fit & Situational Judgment):\n"
            "   - Probe engineering judgment, working style, feedback receptivity, and alignment with company goals.\n"
            "6. Return valid JSON with:\n"
            "   - question: The exact candidate-facing question ending with '?'\n"
            "   - skill: The specific competency or skill (e.g. 'Self-Introduction', 'React State', 'Conflict Resolution', 'Ownership')\n"
            "   - difficulty: 'easy', 'moderate', or 'tricky'\n"
            "   - agent_action: e.g. 'WARM_WELCOME', 'VERIFY_RESUME_CLAIM', 'PROBE_BEHAVIORAL', 'ASSESS_CULTURE_FIT'\n"
            "   - agent_reasoning: 1-sentence HR reasoning explaining why this question is asked at this stage.\n"
        )
        value = self._generate(prompt)
        q = str(value.get("question", "")).strip()
        if not q or not q.endswith("?"):
            raise ValueError("Invalid question generated by Gemini")
        return {
            "question": q,
            "skill": str(value.get("skill", "Introduction & Experience")).strip(),
            "difficulty": str(value.get("difficulty", difficulty)).strip().lower(),
            "agent_action": str(value.get("agent_action", "WARM_WELCOME" if question_number == 1 else "PROBE_DEEPER")).strip(),
            "agent_reasoning": str(
                value.get("agent_reasoning", "Agentic HR progression tailored to candidate resume and role requirements")
            ).strip(),
        }

    def evaluate_hr_candidate(
        self,
        *,
        candidate_name: str,
        role_title: str,
        company_name: str | None,
        company_needs: str | None,
        resume_profile: dict[str, Any] | None,
        qa_pairs: list[dict[str, str]],
    ) -> dict[str, Any]:
        """
        Generate a comprehensive HR Candidate Grade (A+, A, B+, B, C, D) and competency scorecard.
        """
        prompt = (
            "You are a Senior Director of Technical Talent Acquisition & People Operations. "
            f"Evaluate candidate {candidate_name} for the role of {role_title} at {company_name or 'the hiring company'}.\n\n"
            f"COMPANY NEEDS: {company_needs or 'High-performance, collaborative engineering team'}\n"
            f"RESUME: {json.dumps(resume_profile or {})}\n"
            f"INTERVIEW QUESTIONS & CANDIDATE ANSWERS:\n{json.dumps(qa_pairs[:20])}\n\n"
            "TASK:\n"
            "Produce an official HR Candidate Evaluation & Grade Scorecard.\n"
            "Return valid JSON with:\n"
            "- overall_grade: One of ['A+', 'A', 'B+', 'B', 'C', 'D']\n"
            "- overall_score: A float from 1.0 to 10.0\n"
            "- hiring_recommendation: e.g. 'Strong Hire - Fast-track to Team Matching', 'Hire - Proceed to Final Architecture Round', 'Lean Hire - Additional Prep Needed', 'No Hire'\n"
            "- candidate_summary: 2-3 concise sentences summarizing candidate's strengths, communication clarity, and role fit.\n"
            "- intro_grade: Letter grade for their self-introduction, career story, and motivation.\n"
            "- skills_grade: Letter grade for verification of skills claimed on resume.\n"
            "- behavioral_grade: Letter grade for teamwork, conflict resolution, ownership, and culture fit.\n"
            "- competencies: A list of 5 objects with fields ['category', 'grade', 'score', 'feedback'] covering:\n"
            "  1. 'Introduction & Communication'\n"
            "  2. 'Resume Authenticity & Claim Verification'\n"
            "  3. 'Technical Competency & Breadth'\n"
            "  4. 'Behavioral & Culture Fit'\n"
            "  5. 'Ownership & Leadership Potential'\n"
        )
        try:
            val = self._generate(prompt)
            if isinstance(val, dict) and "overall_grade" in val and "competencies" in val:
                return val
        except Exception:
            pass
        return {}


_PROFILE_KEYS = ("skills", "education", "projects", "experience", "technologies", "achievements", "other_details")


def _string_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


def _contains_planning_language(question: str) -> bool:
    normalized = question.lower()
    return any(phrase in normalized for phrase in (
        "what should we examine", "what should we explore", "what should we ask",
        "what concept should we explore", "based on your answer", "next question",
    ))