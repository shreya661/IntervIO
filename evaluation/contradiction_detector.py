"""
Contradiction Detector for InterviewOne AI (Person 3).
Identifies factual inconsistencies between:
1. Candidate answer vs Uploaded Resume / Profile
2. Candidate answer vs Statements made in earlier interview turns
"""

import os
import re
import json
import uuid
from typing import List, Optional, Dict, Any
from .schemas import Contradiction


CONTRADICTION_PROMPT = """You are the Contradiction Detection Engine of InterviewOne AI.
Your role is to detect genuine, substantive factual conflicts between a candidate's current answer and either their resume or prior interview statements.

RULES:
1. ONLY flag substantive contradictions (e.g., claiming to have never used a technology that is prominently listed on their resume, or stating conflicting system architectures).
2. Do NOT flag minor nuances or slight phrasing differences as contradictions.
3. Every contradiction MUST cite the exact text from Source A (resume/prior turn) and Source B (current answer).
4. Provide a polite, professional, neutral clarification question to give the candidate a fair opportunity to explain.

Return JSON matching:
{
  "contradictions": [
    {
      "source_a": "<exact quote from resume or prior turn>",
      "source_b": "<exact quote from current answer>",
      "description": "<why these conflict>",
      "severity": "<Low | Medium | High>",
      "clarification_question": "<polite clarification question>"
    }
  ]
}
"""


class ContradictionDetector:
    """Detects factual inconsistencies using LLM with deterministic heuristic fallback."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gpt-4o-mini"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model_name = model_name
        self._client = None

        if self.api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except Exception:
                self._client = None

    def detect_contradictions(
        self,
        current_answer: str,
        resume_context: Optional[str] = None,
        prior_answers: Optional[List[Dict[str, str]]] = None,
    ) -> List[Contradiction]:
        """
        Scans current answer against resume and prior answers for discrepancies.
        """
        if self._client and (resume_context or prior_answers):
            try:
                return self._detect_with_llm(
                    current_answer=current_answer,
                    resume_context=resume_context,
                    prior_answers=prior_answers,
                )
            except Exception:
                pass

        return self._detect_heuristic(
            current_answer=current_answer,
            resume_context=resume_context,
            prior_answers=prior_answers,
        )

    def _detect_with_llm(
        self,
        current_answer: str,
        resume_context: Optional[str],
        prior_answers: Optional[List[Dict[str, str]]],
    ) -> List[Contradiction]:
        prior_text = "\n".join([f"Turn {p.get('turn')}: {p.get('answer')}" for p in (prior_answers or [])])
        user_prompt = f"""
RESUME / CANDIDATE PROFILE:
{resume_context or 'None provided'}

PRIOR INTERVIEW STATEMENTS:
{prior_text or 'None recorded'}

CURRENT CANDIDATE ANSWER:
{current_answer}

Scan for factual contradictions and return JSON only.
"""
        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": CONTRADICTION_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )

        data = json.loads(response.choices[0].message.content)
        contradictions: List[Contradiction] = []
        for c in data.get("contradictions", []):
            contradictions.append(
                Contradiction(
                    id=f"contra_{uuid.uuid4().hex[:6]}",
                    source_a=c.get("source_a", ""),
                    source_b=c.get("source_b", ""),
                    description=c.get("description", "Inconsistency detected"),
                    severity=c.get("severity", "Medium"),
                    clarification_question=c.get("clarification_question", "Could you clarify this discrepancy?"),
                    resolved=False,
                )
            )
        return contradictions

    def _detect_heuristic(
        self,
        current_answer: str,
        resume_context: Optional[str],
        prior_answers: Optional[List[Dict[str, str]]],
    ) -> List[Contradiction]:
        """Deterministic keyword and negation matcher for common contradiction patterns."""
        contradictions: List[Contradiction] = []
        answer_lower = current_answer.lower()

        # Pattern A: Candidate denies experience that is in Resume
        # e.g., "never worked with kubernetes", "haven't used redis", "no experience with sql"
        negation_patterns = [
            (r"(never (worked with|used|touched|managed)|haven't used|no experience with|didn't use)\s+([a-zA-Z0-9_\-\.]+)", "Resume conflict"),
        ]

        if resume_context:
            resume_lower = resume_context.lower()
            for pattern, desc in negation_patterns:
                match = re.search(pattern, answer_lower)
                if match:
                    tech_mentioned = match.group(3).strip()
                    # Check if tech is claimed in resume
                    if tech_mentioned in resume_lower and len(tech_mentioned) >= 3:
                        contradictions.append(
                            Contradiction(
                                id=f"contra_{uuid.uuid4().hex[:6]}",
                                source_a=f"Resume mentions experience with '{tech_mentioned}'",
                                source_b=match.group(0),
                                description=f"Candidate stated '{match.group(0)}', which contradicts their resume claiming '{tech_mentioned}'.",
                                severity="High",
                                clarification_question=(
                                    f"Your resume mentions experience with {tech_mentioned}, but you mentioned '{match.group(0)}'. "
                                    f"Could you clarify the extent of your hands-on involvement with {tech_mentioned}?"
                                ),
                                resolved=False,
                            )
                        )

        # Pattern B: Candidate contradicts earlier turn architecture
        # e.g. Turn 1 says "we had no cache / only relational DB", Turn 3 says "we used Redis cache"
        if prior_answers:
            for past in prior_answers:
                past_answer = past.get("answer", "").lower()
                past_turn = past.get("turn", 1)

                # Direct caching conflict
                if "no cache" in past_answer or "didn't have any caching" in past_answer:
                    if any(c in answer_lower for c in ["used redis", "redis cache", "memcached"]):
                        contradictions.append(
                            Contradiction(
                                id=f"contra_{uuid.uuid4().hex[:6]}",
                                source_a=f"Turn {past_turn}: '{past.get('answer')[:80]}...'",
                                source_b=current_answer[:80] + "...",
                                description="Candidate previously stated no caching was used, but later mentioned using Redis cache.",
                                severity="Medium",
                                clarification_question="In an earlier question you mentioned that no cache was used, but just now you mentioned Redis caching. Could you clarify how caching fit into that architecture?",
                                resolved=False,
                            )
                        )

        return contradictions

    @staticmethod
    def detect_self_correction(current_answer: str) -> bool:
        """
        Detects whether a candidate is changing or retracting a prior statement.
        Used by Evaluator for ANSWER_CHANGED judge events and natural self-corrections.
        Returns True if correction signals are detected.
        """
        answer_lower = current_answer.lower().strip()
        correction_triggers = [
            "actually, i meant", "let me correct", "i should clarify",
            "i misspoke", "to rephrase that", "what i meant to say",
            "i want to take back", "i was wrong about", "i'd like to correct",
            "actually no", "wait, no", "actually, that's not right",
        ]
        return any(trigger in answer_lower for trigger in correction_triggers)

    @staticmethod
    def detect_refusal(current_answer: str) -> bool:
        """
        Detects whether a candidate is refusing or unable to answer a question.
        Used by Evaluator to emit SWITCH_COMPETENCY instead of scoring a zero.
        Returns True if refusal patterns are detected.
        """
        answer_lower = current_answer.lower().strip()
        refusal_triggers = [
            "i don't know", "i don't really know", "not sure about this",
            "i'd rather not", "i prefer not to", "i can't answer",
            "i have no experience with", "i haven't worked with",
            "pass on this", "skip this one", "no idea",
        ]
        return any(trigger in answer_lower for trigger in refusal_triggers)

    @staticmethod
    def detect_clarification_request(current_answer: str) -> bool:
        """
        Detects if the candidate is asking the interviewer to clarify or rephrase the question.
        Returns True if clarification-seeking patterns are detected.
        """
        answer_lower = current_answer.lower().strip()
        clarification_triggers = [
            "could you rephrase", "could you clarify", "could you repeat",
            "what do you mean by", "i'm not sure i understand", "i don't understand the question",
            "can you explain what you mean", "can you rephrase", "can you clarify",
            "i'm confused by", "the question is unclear",
        ]
        return any(trigger in answer_lower for trigger in clarification_triggers)
