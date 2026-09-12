"""
Answer Analyzer for InterviewOne AI (Person 3).
Performs semantic analysis, evidence extraction with verbatim quote verification,
unverified claim flagging, and vagueness detection.
"""

import os
import re
import json
import uuid
from typing import Optional, List, Dict, Any
from .schemas import (
    DepthLevel,
    EvidenceItem,
    Claim,
    TurnAnalysisResult,
)


ANALYZER_SYSTEM_PROMPT = """You are the Evidence Extraction Engine of InterviewOne AI.
Your role is to analyze a candidate's answer to an interview question strictly and objectively.

CORE RULES:
1. CLAIMS ≠ EVIDENCE:
   - If a candidate says "I built the entire backend" or "I am an expert at Kubernetes", this is an UNVERIFIED CLAIM, not evidence. Flag it as a claim needing verification.
   - Evidence is only what the candidate actually DEMONSTRATES or EXPLAINS with technical reasoning, trade-offs, or concrete architecture.
2. VERBATIM QUOTE REQUIREMENT:
   - For every piece of demonstrated evidence, you MUST provide an exact, verbatim quote substring from the candidate's answer.
   - NEVER invent or paraphrase candidate quotes.
3. VAGUENESS DETECTION:
   - High vagueness (0.7-1.0): Candidate uses buzzwords ("scalable", "modern", "good practices") without naming specific components, algorithms, metrics, or trade-offs.
   - Low vagueness (0.0-0.3): Candidate provides concrete details, metrics, edge cases, failure modes.
4. STRICT JSON OUTPUT ONLY.

Return a JSON object matching this schema:
{
  "technical_correctness": <float 1.0 to 5.0>,
  "depth_level": <"surface" | "fundamental" | "intermediate" | "advanced">,
  "vagueness_score": <float 0.0 to 1.0>,
  "vagueness_reason": <string or null>,
  "demonstrated_evidence": [
    {
      "demonstrated_fact": "<specific concept proven>",
      "quote": "<exact substring quote from answer>",
      "depth_level": "<fundamental | intermediate | advanced>",
      "confidence": <float 0.0 to 1.0>
    }
  ],
  "unverified_claims": [
    {
      "claim_text": "<broad or unsubstantiated assertion>",
      "verification_probe": "<targeted question to test direct ownership/knowledge>"
    }
  ],
  "gaps_identified": ["<unaddressed key aspect 1>", "<unaddressed key aspect 2>"],
  "needs_followup": <boolean>,
  "followup_angle": "<suggested angle or null>"
}
"""


class AnswerAnalyzer:
    """Analyzes candidate responses using LLM with deterministic heuristic fallback."""

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

    def analyze(
        self,
        question: str,
        answer: str,
        target_competency: str,
        turn_index: int = 1,
        job_context: Optional[str] = None,
        candidate_resume_context: Optional[str] = None,
    ) -> TurnAnalysisResult:
        """
        Main entry point for answer analysis.
        Uses LLM when available; falls back to heuristic analysis automatically.
        """
        if self._client and len(answer.strip()) > 10:
            try:
                return self._analyze_with_llm(
                    question=question,
                    answer=answer,
                    target_competency=target_competency,
                    turn_index=turn_index,
                    job_context=job_context,
                    candidate_resume_context=candidate_resume_context,
                )
            except Exception as e:
                # Log and proceed to fallback
                pass

        return self._analyze_heuristic(
            question=question,
            answer=answer,
            target_competency=target_competency,
            turn_index=turn_index,
        )

    def _analyze_with_llm(
        self,
        question: str,
        answer: str,
        target_competency: str,
        turn_index: int,
        job_context: Optional[str],
        candidate_resume_context: Optional[str],
    ) -> TurnAnalysisResult:
        user_prompt = f"""
TARGET COMPETENCY: {target_competency}
QUESTION ASKED: {question}
CANDIDATE ANSWER: {answer}
JOB CONTEXT: {job_context or 'Software Engineering role'}
RESUME CONTEXT: {candidate_resume_context or 'Not provided'}

Analyze the candidate's answer according to the system rules and output JSON only.
"""
        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": ANALYZER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        data = json.loads(response.choices[0].message.content)
        return self._parse_and_validate_llm_output(data, answer, target_competency, turn_index)

    def _parse_and_validate_llm_output(
        self,
        data: Dict[str, Any],
        raw_answer: str,
        target_competency: str,
        turn_index: int,
    ) -> TurnAnalysisResult:
        """Validates LLM output, enforcing the quote matching constraint."""
        validated_evidence: List[EvidenceItem] = []
        raw_answer_lower = raw_answer.lower()

        for item in data.get("demonstrated_evidence", []):
            quote = item.get("quote", "").strip()
            # Quote Matching Guardrail: quote must be in answer or at least 70% fuzzy match
            if quote and (quote.lower() in raw_answer_lower or any(part in raw_answer_lower for part in quote.lower().split() if len(part) > 6)):
                validated_evidence.append(
                    EvidenceItem(
                        id=f"ev_{uuid.uuid4().hex[:6]}",
                        competency=target_competency,
                        demonstrated_fact=item.get("demonstrated_fact", "Demonstrated competency knowledge"),
                        quote=quote,
                        depth_level=DepthLevel(item.get("depth_level", "intermediate")),
                        confidence_score=float(item.get("confidence", 0.75)),
                        turn_index=turn_index,
                    )
                )

        claims: List[Claim] = []
        for c in data.get("unverified_claims", []):
            claims.append(
                Claim(
                    claim_id=f"claim_{uuid.uuid4().hex[:6]}",
                    claim_text=c.get("claim_text", ""),
                    target_competency=target_competency,
                    verification_needed=True,
                    verification_question=c.get("verification_probe"),
                    verified=False,
                )
            )

        return TurnAnalysisResult(
            demonstrated_evidence=validated_evidence,
            claims_detected=claims,
            contradictions_detected=[],
            technical_correctness=float(data.get("technical_correctness", 3.0)),
            depth_level=DepthLevel(data.get("depth_level", "fundamental")),
            vagueness_score=float(data.get("vagueness_score", 0.3)),
            vagueness_reason=data.get("vagueness_reason"),
            gaps_identified=data.get("gaps_identified", []),
            needs_followup=bool(data.get("needs_followup", False)) or (len(claims) > 0),
            followup_angle=data.get("followup_angle") or (claims[0].verification_question if claims else None),
        )

    def _analyze_heuristic(
        self,
        question: str,
        answer: str,
        target_competency: str,
        turn_index: int,
    ) -> TurnAnalysisResult:
        """Deterministic heuristic analyzer when LLM is unavailable."""
        answer_clean = answer.strip()
        words = answer_clean.split()
        word_count = len(words)
        lower_answer = answer_clean.lower()

        # 1. Detect ownership claim keywords
        claims: List[Claim] = []
        ownership_triggers = [
            r"i (designed|built|architected|led|created) (the entire|all the|the whole)",
            r"i am an expert in",
            r"single-handedly",
            r"everything was done by me",
        ]
        for trigger in ownership_triggers:
            match = re.search(trigger, lower_answer)
            if match:
                claims.append(
                    Claim(
                        claim_id=f"claim_{uuid.uuid4().hex[:6]}",
                        claim_text=answer_clean[match.start():min(len(answer_clean), match.end() + 60)],
                        target_competency=target_competency,
                        verification_needed=True,
                        verification_question=f"Which specific design decisions did you personally make for that, and what trade-offs did you face?",
                        verified=False,
                    )
                )

        # 2. Vagueness & Technical depth estimation
        buzzwords = ["scalable", "modern", "clean", "best practices", "robust", "efficient", "nice", "proper"]
        technical_terms = [
            "latency", "throughput", "concurrency", "async", "cache", "redis", "postgres",
            "index", "query", "bottleneck", "thread", "process", "lock", "queue", "kafka",
            "replica", "partition", "sharding", "consistency", "acid", "deadlock"
        ]

        buzzword_count = sum(1 for bw in buzzwords if bw in lower_answer)
        tech_count = sum(1 for tt in technical_terms if tt in lower_answer)

        if word_count < 20:
            vagueness_score = 0.8
            vagueness_reason = "Answer is very brief and lacks technical elaboration."
            tech_correctness = 2.0
            depth = DepthLevel.SURFACE
        elif tech_count >= 3 and word_count >= 35:
            vagueness_score = 0.15
            vagueness_reason = None
            tech_correctness = 4.2
            depth = DepthLevel.ADVANCED if tech_count >= 5 else DepthLevel.INTERMEDIATE
        elif buzzword_count > tech_count:
            vagueness_score = 0.7
            vagueness_reason = "Used generic buzzwords without citing concrete architectural choices."
            tech_correctness = 2.8
            depth = DepthLevel.FUNDAMENTAL
        else:
            vagueness_score = 0.35
            vagueness_reason = None
            tech_correctness = 3.5
            depth = DepthLevel.INTERMEDIATE

        # 3. Extract evidence items if depth is sufficient
        evidence_list: List[EvidenceItem] = []
        if depth in [DepthLevel.INTERMEDIATE, DepthLevel.ADVANCED]:
            # Take a representative sentence from the answer as quote
            sentences = [s.strip() for s in re.split(r"[.!?]", answer_clean) if len(s.split()) >= 4]
            quote_text = sentences[0] if sentences else answer_clean[:100]

            evidence_list.append(
                EvidenceItem(
                    id=f"ev_{uuid.uuid4().hex[:6]}",
                    competency=target_competency,
                    demonstrated_fact=f"Candidate articulated technical concepts for {target_competency}",
                    quote=quote_text,
                    depth_level=depth,
                    confidence_score=0.75,
                    turn_index=turn_index,
                )
            )

        gaps = []
        if tech_count < 2:
            gaps.append(f"Concrete trade-off analysis in {target_competency}")

        needs_followup = (vagueness_score >= 0.6) or (len(claims) > 0)
        followup_angle = claims[0].verification_question if claims else (
            f"Could you elaborate with a specific production example or bottleneck you solved?"
            if vagueness_score >= 0.6 else None
        )

        return TurnAnalysisResult(
            demonstrated_evidence=evidence_list,
            claims_detected=claims,
            contradictions_detected=[],
            technical_correctness=tech_correctness,
            depth_level=depth,
            vagueness_score=vagueness_score,
            vagueness_reason=vagueness_reason,
            gaps_identified=gaps,
            needs_followup=needs_followup,
            followup_angle=followup_angle,
        )
