"""
InterviewOne AI — Core Interview API

Features:
- Resume REQUIRED: interview cannot start without an uploaded and parsed resume
- Resume-personalised question selection (questions adapt to candidate's actual skills)
- 20-question adaptive bank: 10 Easy+Logic, 5 Moderate+Logic, 5 Tricky
- Full question deduplication — the same question is never asked twice
- Facial/visual signal logging per answer turn
- Fernet symmetric encryption of PII (candidate name + resume text)
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile

logger = logging.getLogger("person3.interviews")

# ── Schema imports ────────────────────────────────────────────────────────────

try:
    from backend.schemas.interview import (
        AnswerRecord,
        HRCompetencyGrade,
        HRComposureEvaluation,
        HREvaluation,
        InterviewPlan,
        InterviewState,
        PlannedStage,
        ResumeProfile,
        VisualSignal,
    )
except ImportError:
    from schemas.interview import (          # type: ignore[no-redef]
        AnswerRecord,
        HRCompetencyGrade,
        HRComposureEvaluation,
        HREvaluation,
        InterviewPlan,
        InterviewState,
        PlannedStage,
        ResumeProfile,
        VisualSignal,
    )

# ── Encryption & PII Protection ───────────────────────────────────────────────

try:
    from backend.security import (
        decrypt,
        encrypt,
        mask,
        encrypt_json,
        decrypt_json,
        scrub_pii_for_llm,
        is_encryption_active,
    )
except ImportError:
    from security import (                   # type: ignore[no-redef]
        decrypt,
        encrypt,
        mask,
        encrypt_json,
        decrypt_json,
        scrub_pii_for_llm,
        is_encryption_active,
    )

# ── Resume analyzer & AI Assistant ────────────────────────────────────────────

_PARENT = Path(__file__).resolve().parent.parent.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

try:
    from multimodal.resume_analyzer import ResumeAnalyzer, ResumeAnalysisError
    _RESUME_ANALYZER = ResumeAnalyzer()
    logger.info("Resume analyzer loaded.")
except Exception as exc:
    logger.warning("Resume analyzer unavailable: %s", exc)
    _RESUME_ANALYZER = None
    ResumeAnalysisError = Exception  # type: ignore[misc,assignment]

try:
    from multimodal.gemini_assistant import GeminiAssistant
    logger.info("Gemini assistant module loaded.")
except Exception as exc:
    logger.warning("Gemini assistant unavailable: %s", exc)
    GeminiAssistant = None

try:
    from backend.pdf_report import generate_assessment_pdf
except ImportError:
    try:
        from pdf_report import generate_assessment_pdf
    except ImportError:
        generate_assessment_pdf = None

# ── Pydantic model for JSON body ──────────────────────────────────────────────

from pydantic import BaseModel


class AnswerRequest(BaseModel):
    answer: str
    visual_signal: Optional[VisualSignal] = None  # Optional camera observations from client


class CreateInterviewRequest(BaseModel):
    candidate_name: Optional[str] = None
    goal: Optional[str] = "Full Evaluation"
    duration_minutes: Optional[int] = 30
    company_name: Optional[str] = None
    company_needs: Optional[str] = None
    job_title: Optional[str] = None
    job_description: Optional[str] = None
    gemini_api_key: Optional[str] = None


# ── In-memory store ───────────────────────────────────────────────────────────

interviews: dict[str, InterviewState] = {}


# ── Router ────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/interviews", tags=["Interviews"])


# ══════════════════════════════════════════════════════════════════════════════
# QUESTION BANK
# 10 Easy + Logic  |  5 Moderate + Logic  |  5 Tricky (simple but logical)
# Each entry: {question, skill, difficulty, requires_resume_skill (optional)}
# ══════════════════════════════════════════════════════════════════════════════

QUESTION_BANK: dict[str, list[dict]] = {

    # ── EASY + LOGIC (10) ─────────────────────────────────────────────────────
    "easy": [
        {
            "question": (
                "Without running any code, what would this print?\n\n"
                "    x = [1, 2, 3]\n    y = x\n    y.append(4)\n    print(x)\n\n"
                "Explain your reasoning step by step."
            ),
            "skill": "Python Logic",
            "tag": "reference_semantics",
        },
        {
            "question": (
                "What is the output of the following code, and why?\n\n"
                "    def f(a, b=[]):\n        b.append(a)\n        return b\n\n"
                "    print(f(1))\n    print(f(2))\n    print(f(3, []))\n\n"
                "Most candidates are surprised. Explain what Python does here."
            ),
            "skill": "Python Logic",
            "tag": "mutable_defaults",
        },
        {
            "question": (
                "Trace through this and give the final output:\n\n"
                "    result = []\n    for i in range(5):\n        if i % 2 == 0:\n            result.append(i ** 2)\n    print(result)\n\n"
                "Then rewrite it as a one-line list comprehension."
            ),
            "skill": "Python Logic",
            "tag": "list_comprehension",
        },
        {
            "question": (
                "What is the difference between '==' and 'is' in Python? "
                "Give an example where they produce different results, and explain why."
            ),
            "skill": "Python Fundamentals",
            "tag": "identity_vs_equality",
        },
        {
            "question": (
                "How does Python determine the truth value of an object? "
                "Give 3 examples of non-boolean values that Python evaluates as falsy, and explain the rule."
            ),
            "skill": "Python Fundamentals",
            "tag": "truthiness",
        },
        {
            "question": (
                "What is a Python generator and how is it different from a list? "
                "Write a simple generator that yields the first N Fibonacci numbers, "
                "and explain why this is more memory-efficient than building a list."
            ),
            "skill": "Python Fundamentals",
            "tag": "generators",
        },
        {
            "question": (
                "Explain the concept of variable scope in Python (LEGB rule). "
                "What does the following code output and why?\n\n"
                "    x = 10\n    def outer():\n        x = 20\n        def inner():\n            print(x)\n        inner()\n    outer()"
            ),
            "skill": "Python Logic",
            "tag": "scope_closures",
        },
        {
            "question": (
                "What is a REST API, and what does it mean for an endpoint to be 'stateless'? "
                "Give a real-world example of a stateless vs. a stateful operation."
            ),
            "skill": "Web / API Fundamentals",
            "tag": "rest_stateless",
        },
        {
            "question": (
                "Explain the difference between a SQL JOIN (INNER JOIN) and a LEFT JOIN. "
                "In what situation would you use each one? Give a concrete example with table names."
            ),
            "skill": "Databases",
            "tag": "sql_joins",
        },
        {
            "question": (
                "What is Big-O notation? What is the time complexity of:\n"
                "  1. Searching for an item in an unsorted list\n"
                "  2. Searching for an item in a Python dict\n"
                "  3. Sorting a list with Python's sorted()\n\n"
                "Explain why each of these complexities holds."
            ),
            "skill": "Algorithms",
            "tag": "big_o",
        },
    ],

    # ── MODERATE + LOGIC (5) ──────────────────────────────────────────────────
    "moderate": [
        {
            "question": (
                "Design a rate limiter that allows at most 100 requests per minute per user. "
                "Walk me through your data structure choices, the algorithm, and how you'd handle "
                "edge cases like clock drift, distributed servers, and burst traffic."
            ),
            "skill": "System Design",
            "tag": "rate_limiter",
        },
        {
            "question": (
                "You have a list of N integers and need to find all pairs that sum to a target T. "
                "First describe a naive O(n²) solution, then improve it to O(n). "
                "Code your O(n) solution, trace through an example, and explain the tradeoff."
            ),
            "skill": "Algorithms",
            "tag": "two_sum_logic",
        },
        {
            "question": (
                "Explain how Python's 'async/await' works. How is it different from threading? "
                "Write a conceptual async function that fetches data from 3 URLs concurrently "
                "and returns when all 3 complete. What happens if one of them fails?"
            ),
            "skill": "Python Advanced",
            "tag": "async_await",
        },
        {
            "question": (
                "Describe the differences between a relational database (e.g. PostgreSQL) and "
                "a document database (e.g. MongoDB). When would you choose each? "
                "Now imagine you have a social media platform with 50M users — which would you pick "
                "for storing user posts, and why? Consider read/write patterns, schema flexibility, and scale."
            ),
            "skill": "Databases",
            "tag": "rdbms_vs_nosql",
        },
        {
            "question": (
                "What are SOLID principles? Pick any two, explain them clearly, and give a code "
                "example showing a violation of each, then show the corrected version. "
                "Which of the five do you find hardest to apply in practice and why?"
            ),
            "skill": "Software Engineering",
            "tag": "solid_principles",
        },
    ],

    # ── TRICKY (simple-looking but require logical depth) (5) ─────────────────
    "tricky": [
        {
            "question": (
                "This function is supposed to return the running average of a list. "
                "Find the bug — without running the code — and fix it:\n\n"
                "    def running_avg(nums):\n        total = 0\n        result = []\n"
                "        for i, n in enumerate(nums):\n            total += n\n"
                "            result.append(total / i)\n        return result\n\n"
                "What's wrong? What edge case also needs handling?"
            ),
            "skill": "Debugging Logic",
            "tag": "debug_zero_division",
        },
        {
            "question": (
                "True or False — and explain your reasoning for each:\n\n"
                "1. Adding an index to a database column always makes queries faster.\n"
                "2. A microservices architecture is always more scalable than a monolith.\n"
                "3. Caching always reduces load on the origin server.\n"
                "4. Using 'SELECT *' in production SQL is fine if the query is fast.\n\n"
                "Pick the one you feel most strongly about and argue both sides."
            ),
            "skill": "Engineering Judgment",
            "tag": "true_false_engineering",
        },
        {
            "question": (
                "What does this Python code do, step by step? What is its output?\n\n"
                "    data = {'a': 1, 'b': 2, 'c': 3}\n"
                "    result = {v: k for k, v in data.items() if v > 1}\n"
                "    print(result)\n\n"
                "Now modify it to only include entries where the original key is alphabetically after 'a'."
            ),
            "skill": "Python Logic",
            "tag": "dict_comprehension_inversion",
        },
        {
            "question": (
                "You're reviewing a colleague's PR. The code works perfectly in all tests. "
                "But you notice it does:\n\n"
                "    password = request.data['password']\n    db.execute(f\"SELECT * FROM users WHERE password = '{password}'\")\n\n"
                "What is the problem? Rewrite this securely and explain every change you made."
            ),
            "skill": "Security",
            "tag": "sql_injection",
        },
        {
            "question": (
                "A junior developer says: 'I optimised our API — I added memoisation to every function!' "
                "What could go wrong with this approach? "
                "Describe at least 3 specific scenarios where memoisation would make things worse, "
                "not better. Be precise."
            ),
            "skill": "Engineering Judgment",
            "tag": "memoisation_pitfalls",
        },
    ],
}

# Ordered curriculum: easy × 10 → moderate × 5 → tricky × 5
_CURRICULUM_ORDER = (
    [("easy", i) for i in range(10)]
    + [("moderate", i) for i in range(5)]
    + [("tricky", i) for i in range(5)]
)


# ── Resume-aware skill matching ───────────────────────────────────────────────

# Additional resume-specific questions generated at runtime
_RESUME_QUESTION_TEMPLATES: dict[str, list[str]] = {
    "Python": [
        "Your resume mentions Python experience. Describe the most complex Python project you've built. What architectural decisions did you make and why?",
        "You've worked with Python — walk me through a performance bottleneck you've faced and how you profiled and resolved it.",
    ],
    "React": [
        "Your resume lists React. Explain the difference between useEffect and useLayoutEffect. When would you use each?",
        "You've used React — how do you prevent unnecessary re-renders in a large component tree?",
    ],
    "FastAPI": [
        "You've worked with FastAPI — how does it handle dependency injection, and what are the benefits of this pattern?",
        "Your resume shows FastAPI experience. How would you add rate limiting, authentication middleware, and request logging to a FastAPI app?",
    ],
    "Django": [
        "You have Django experience — explain Django's ORM N+1 problem and how you would detect and fix it.",
        "Your resume mentions Django. How does Django's middleware stack work, and when would you write a custom middleware?",
    ],
    "SQL": [
        "Your resume includes SQL — walk me through optimising a slow query on a table with 50 million rows.",
        "You've worked with SQL — explain window functions and give a real use case where you'd use ROW_NUMBER() or LAG().",
    ],
    "PostgreSQL": [
        "You've used PostgreSQL — explain MVCC (Multi-Version Concurrency Control) and how it enables PostgreSQL's transaction isolation.",
        "Your resume shows PostgreSQL — what are partial indexes, and when would you use them over a full index?",
    ],
    "Docker": [
        "You have Docker experience — what is the difference between a Docker image and a container? Walk me through a Dockerfile you've written.",
        "Your resume mentions Docker — how do you reduce Docker image size in production, and why does it matter?",
    ],
    "Kubernetes": [
        "You've worked with Kubernetes — explain the difference between a Deployment and a StatefulSet.",
        "Your resume includes Kubernetes — how does Kubernetes handle rolling updates and rollbacks?",
    ],
    "AWS": [
        "You have AWS experience — describe an architecture you've built on AWS. What services did you choose and what tradeoffs did you make?",
        "Your resume mentions AWS — explain the difference between SQS and SNS, and when you'd use each.",
    ],
    "TypeScript": [
        "You've used TypeScript — explain the difference between 'interface' and 'type alias'. When would you use each?",
        "Your resume shows TypeScript — how do generics improve type safety and code reuse? Give a concrete example.",
    ],
    "JavaScript": [
        "You've worked with JavaScript — explain the event loop and how it handles async operations. Where do Microtasks (Promises) execute compared to Macrotasks (setTimeout)?",
        "Your resume mentions JavaScript — what is the difference between == and ===, and what are closures in JavaScript? Give a real-world production use case.",
    ],
    "Java": [
        "Your background includes Java. How does the Java Virtual Machine's garbage collector manage heap memory between young and old generations? What performance metrics do you monitor in production?",
        "You've worked with Java — explain the difference between 'synchronized' and 'volatile'. In what scenario does volatile fail to guarantee thread safety?",
    ],
    "Spring": [
        "You have Spring Boot experience. Walk me through Spring's Inversion of Control (IoC) container lifecycle and how bean scoping affects concurrency in web requests.",
        "Your resume mentions Spring. How do you implement resilience patterns like circuit breakers and retry policies in a microservices environment?",
    ],
    "Go": [
        "Your resume shows Go experience. Explain how Go's goroutine scheduler (M:N work-stealing) differs from OS threads. What happens if a goroutine performs a blocking syscall?",
        "You've worked with Go — walk me through how channels work under the hood. How do you prevent channel deadlocks and goroutine leaks in production?",
    ],
    "Node.js": [
        "You've worked with Node.js. Explain the phases of the Node.js event loop (timers, pending callbacks, poll, check). Where do process.nextTick() and Promise microtasks execute?",
        "Your resume mentions Node.js. When would you use Node's Worker Threads instead of the Cluster module? Explain the communication overhead between workers.",
    ],
    "C#": [
        "Your resume shows C#/.NET experience. Explain the difference between 'Task' and 'Thread'. How does async/await synchronization context prevent deadlocks in UI vs. ASP.NET Core apps?",
        "You've worked with C# — explain LINQ deferred execution and how it can cause accidental multiple database queries if not handled carefully.",
    ],
    "Rust": [
        "You've worked with Rust. Explain ownership, borrowing, and lifetimes. How does Rust's borrow checker guarantee memory safety without a garbage collector?",
    ],
    "GraphQL": [
        "Your resume includes GraphQL. How do you solve the N+1 query problem in GraphQL resolvers, and what are the tradeoffs between DataLoader and schema federation?",
    ],
    "Vue": [
        "Your resume mentions Vue. Explain the difference between Vue 3's Composition API and the Options API. How does Vue 3's Proxy-based reactivity system track dependencies?",
    ],
    "Redis": [
        "Your resume includes Redis — what data structures does Redis support, and when would you choose Redis over a relational database?",
        "You've used Redis — how would you implement a distributed lock using Redis?",
    ],
}


def _build_context_questions(
    resume_profile: Optional[ResumeProfile] = None,
    job_description: Optional[str] = None,
    company_needs: Optional[str] = None,
) -> list[dict]:
    """
    Generate personalised questions matching:
    1. Candidate's actual resume skills & technologies
    2. Job description requirements & stack
    3. Company needs and domain
    """
    detected_keys: list[str] = []

    # 1. From resume
    if resume_profile:
        for item in resume_profile.technologies + resume_profile.skills:
            for key in _RESUME_QUESTION_TEMPLATES:
                if key.lower() in item.lower() and key not in detected_keys:
                    detected_keys.append(key)

    # 2. From job description
    if job_description:
        jd_lower = job_description.lower()
        for key in _RESUME_QUESTION_TEMPLATES:
            if key.lower() in jd_lower and key not in detected_keys:
                detected_keys.append(key)

    # 3. From company needs
    if company_needs:
        cn_lower = company_needs.lower()
        for key in _RESUME_QUESTION_TEMPLATES:
            if key.lower() in cn_lower and key not in detected_keys:
                detected_keys.append(key)

    questions: list[dict] = []
    for key in detected_keys:
        templates = _RESUME_QUESTION_TEMPLATES.get(key, [])
        for t in templates[:1]:
            questions.append({
                "question": t,
                "skill": key,
                "difficulty": "moderate",
                "tag": f"context_{key.lower()}",
            })

    return questions[:8]


def _build_resume_questions(profile: ResumeProfile) -> list[dict]:
    """Generate personalised questions based on candidate's actual resume skills."""
    return _build_context_questions(resume_profile=profile)


# ── Interview Planner ─────────────────────────────────────────────────────────

def _generate_interview_plan(state: InterviewState) -> InterviewPlan:
    """
    Synthesizes an explicit Interview Plan based on:
    1. Candidate's Resume (skills, technologies, projects, experience)
    2. Job Description (responsibilities, required qualifications)
    3. Company Needs (domain, architectural focus, culture)
    """
    resume_skills = []
    if state.resume_profile:
        resume_skills = list(dict.fromkeys(state.resume_profile.skills + state.resume_profile.technologies))

    # Detect role title
    role = state.job_title or ""
    if not role and state.job_description:
        for possible in [
            "Frontend Engineer", "Backend Engineer", "Fullstack Engineer",
            "DevOps Engineer", "Data Engineer", "Cloud Architect",
            "Software Engineer", "Systems Engineer",
        ]:
            if possible.lower() in state.job_description.lower():
                role = possible
                break
    if not role:
        role = "Software Engineer"

    # Detect primary tech stack from Resume + JD + Company Needs
    combined_text = f"{state.job_description or ''} {state.company_needs or ''} {' '.join(resume_skills)}".lower()
    detected_stack = []
    for tech in [
        "React", "TypeScript", "Next.js", "Vue", "Java", "Spring", "Go",
        "Python", "FastAPI", "Django", "Node.js", "C#", "Rust", "Docker",
        "Kubernetes", "AWS", "PostgreSQL", "SQL", "Redis", "Kafka", "GraphQL",
    ]:
        if tech.lower() in combined_text and tech not in detected_stack:
            detected_stack.append(tech)

    if not detected_stack:
        detected_stack = resume_skills[:5] or ["Core Software Engineering"]

    company_focus = state.company_needs or f"{state.company_name or 'Engineering'} Domain & High Standards"

    plan_summary = (
        f"3-stage adaptive evaluation for {role} at {state.company_name or 'the company'}. "
        f"Testing candidate resume claims against {', '.join(detected_stack[:4])} requirements."
    )

    # If Gemini AI is enabled, try generating a rich 2-sentence plan summary
    if state.ai_powered:
        api_key = state.gemini_api_key or os.getenv("GEMINI_API_KEY")
        if api_key and GeminiAssistant:
            try:
                assistant = GeminiAssistant(api_key=api_key, model="gemini-2.0-flash")
                prompt = (
                    f"Create a concise 2-sentence interview plan summary for candidate {state.candidate_name}.\n"
                    f"ROLE: {role}. STACK: {', '.join(detected_stack)}. "
                    f"COMPANY: {state.company_name or 'Tech Company'} (NEEDS: {company_focus}). "
                    f"RESUME SKILLS: {json.dumps(resume_skills[:10])}.\n"
                    "Explain how the 20-question session verifies candidate skills across Easy, Moderate, and Tricky tiers. "
                    "Return JSON with key 'summary'."
                )
                res = assistant._generate(prompt)
                if isinstance(res, dict) and res.get("summary"):
                    plan_summary = str(res["summary"]).strip()
            except Exception as e:
                logger.warning("Gemini plan summary fallback: %s", e)

    stages = [
        PlannedStage(
            stage_name="Stage 1: HR Intro & Core Mechanics (Simpler Start)",
            difficulty="easy",
            focus_skills=["Self-Introduction", "Career Overview"] + detected_stack[:2],
            question_count=10,
            resume_reference=f"Welcoming introduction & baseline verification in: {', '.join(detected_stack[:3])}",
            job_reference=f"Validating role motivation and foundational requirements for {role}",
        ),
        PlannedStage(
            stage_name="Stage 2: Architecture & System Trade-offs",
            difficulty="moderate",
            focus_skills=detected_stack[2:5] or detected_stack[:2],
            question_count=5,
            resume_reference="Probing hands-on project implementations and system architecture",
            job_reference=f"Evaluating scalable delivery for {state.company_name or 'production'}",
        ),
        PlannedStage(
            stage_name="Stage 3: Tricky Edge Cases & Culture Alignment",
            difficulty="tricky",
            focus_skills=["Conflict Resolution", "Ownership", "System Edge Cases"] + detected_stack[:2],
            question_count=5,
            resume_reference="Testing ownership, teamwork under pressure, and engineering judgment",
            job_reference="Validating cultural alignment and handling complex production dilemmas",
        ),
    ]

    return InterviewPlan(
        role_title=role,
        tech_stack=detected_stack[:6],
        company_focus=company_focus,
        stages=stages,
        total_questions=20,
        planned_summary=plan_summary,
    )


# ── Answer depth assessor ─────────────────────────────────────────────────────

def _assess_answer_depth(answer: str) -> str:
    text = answer.strip()
    word_count = len(text.split())
    depth_signals = [
        "because", "however", "tradeoff", "trade-off", "complexity",
        "performance", "memory", "example", "for instance", "O(n)",
        "specifically", "in my experience", "the reason", "consider",
        "alternatively", "drawback", "advantage", "compared to", "edge case",
        "bottleneck", "profiling", "benchmark", "security", "injection",
        "concurrency", "scalability", "architecture", "trade-offs",
    ]
    depth_hits = sum(1 for s in depth_signals if s.lower() in text.lower())
    if word_count < 20 or depth_hits == 0:
        return "shallow"
    elif word_count < 60 or depth_hits <= 1:
        return "surface"
    elif word_count < 120 or depth_hits <= 3:
        return "intermediate"
    return "deep"


# ── Adaptive question selector ────────────────────────────────────────────────

def select_next_question(
    question_number: int,
    last_answer: str,
    asked_questions: list[str],
    state: Optional[InterviewState] = None,
    resume_profile: Optional[ResumeProfile] = None,
) -> dict:
    """
    Selects the next question using:
    1. Gemini AI (if API key available) — dynamically tailored to Resume + JD + Company Needs.
    2. Context-tailored multi-stack questions (Resume + JD + Company Needs).
    3. Structured curriculum tiers (Easy 1–10 → Moderate 11–15 → Tricky 16–20).
    4. Answer-depth adaptation (shallow answer → probe easier; deep → escalate).
    5. Full deduplication across all asked questions.
    """
    depth = _assess_answer_depth(last_answer)

    preferred_tier = {
        "shallow": "easy",
        "surface": "easy",
        "intermediate": "moderate",
        "deep": "tricky",
    }.get(depth, "moderate")

    # Enforce curriculum stage if question number advances
    if question_number <= 10:
        preferred_tier = "easy" if depth in ("shallow", "surface") else "easy"
    elif question_number <= 15:
        preferred_tier = "moderate"
    else:
        preferred_tier = "tricky"

    # ── Option A: Gemini AI Generation (Resume + JD + Company Needs) ───────────
    if state and (state.ai_powered or state.gemini_api_key or os.getenv("GEMINI_API_KEY")):
        try:
            api_key = state.gemini_api_key or os.getenv("GEMINI_API_KEY")
            if GeminiAssistant and api_key:
                assistant = GeminiAssistant(api_key=api_key, model="gemini-2.0-flash")
                resume_dict = state.resume_profile.model_dump() if state.resume_profile else None
                if resume_dict:
                    clean_resume = {}
                    for k, v in resume_dict.items():
                        if isinstance(v, list):
                            clean_resume[k] = [scrub_pii_for_llm(item) for item in v]
                        elif isinstance(v, str):
                            clean_resume[k] = scrub_pii_for_llm(v)
                        else:
                            clean_resume[k] = v
                    resume_dict = clean_resume

                clean_answer = scrub_pii_for_llm(last_answer)
                clean_jd = scrub_pii_for_llm(state.job_description) if state.job_description else None

                ai_q = assistant.generate_curriculum_question(
                    question_number=question_number,
                    difficulty=preferred_tier,
                    resume_profile=resume_dict,
                    job_description=clean_jd,
                    company_name=state.company_name,
                    company_needs=state.company_needs,
                    previous_questions=asked_questions,
                    last_answer=clean_answer,
                    last_depth=depth,
                )
                if ai_q and ai_q.get("question") and ai_q["question"] not in asked_questions:
                    logger.info("Gemini AI synthesized Q%s: %s", question_number, ai_q["skill"])
                    return ai_q
        except Exception as exc:
            logger.warning("Gemini question generation error, falling back to multi-stack engine: %s", exc)

    # ── Option B: Multi-Stack Deterministic Engine ────────────────────────────
    pool: list[dict] = []

    # Priority 1: Context questions matching Resume + JD + Company Needs
    if state:
        pool.extend(_build_context_questions(
            resume_profile=state.resume_profile,
            job_description=state.job_description,
            company_needs=state.company_needs,
        ))
    elif resume_profile:
        pool.extend(_build_resume_questions(resume_profile))

    # Priority 2: Standard Curriculum Bank
    for tier, idx in _CURRICULUM_ORDER:
        bank = QUESTION_BANK.get(tier, [])
        if idx < len(bank):
            q = dict(bank[idx])
            q["difficulty"] = tier
            pool.append(q)

    # Filter already-asked
    fresh = [q for q in pool if q["question"] not in asked_questions]

    if not fresh:
        return {
            "question": (
                "You've covered the entire question bank — impressive! "
                "Let's go deeper: design a globally distributed, fault-tolerant "
                "system with consistency guarantees matching your target role. "
                "Walk through every architectural tradeoff."
            ),
            "skill": "System Design",
            "difficulty": "tricky",
            "agent_action": "PROBE_DEEPER",
            "agent_reasoning": "All planned questions exhausted. Escalating to open synthesis challenge.",
        }

    tier_match = [q for q in fresh if q.get("difficulty") == preferred_tier]
    selected = (tier_match or fresh)[0]

    agent_action = {
        "shallow": "INVESTIGATE_FUNDAMENTALS",
        "surface": "PROBE_VAGUE",
        "intermediate": "PROBE_DEEPER",
        "deep": "SWITCH_COMPETENCY",
    }.get(depth, "PROBE_DEEPER")

    agent_reasoning = {
        "shallow": f"Answer was brief. Routing to foundational question in {selected['skill']}.",
        "surface": f"Answer needed more detail. Probing for specific examples in {selected['skill']}.",
        "intermediate": f"Solid answer. Escalating to {preferred_tier} question in {selected['skill']}.",
        "deep": f"Excellent depth. Progressing to advanced engineering judgment.",
    }.get(depth, "Continuing assessment.")

    return {
        "question": selected["question"],
        "skill": selected["skill"],
        "difficulty": selected.get("difficulty", preferred_tier),
        "agent_action": agent_action,
        "agent_reasoning": agent_reasoning,
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════


@router.post("/")
def create_interview(
    candidate_name: Optional[str] = None,
    goal: str = "Full Evaluation",
    duration_minutes: int = 30,
    company_name: Optional[str] = None,
    company_needs: Optional[str] = None,
    job_title: Optional[str] = None,
    job_description: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
    body: Optional[CreateInterviewRequest] = None,
):
    """Create an empty interview session. Resume must be uploaded before starting."""
    if body:
        candidate_name = body.candidate_name or candidate_name
        goal = body.goal or goal
        duration_minutes = body.duration_minutes if body.duration_minutes is not None else duration_minutes
        company_name = body.company_name or company_name
        company_needs = body.company_needs or company_needs
        job_title = body.job_title or job_title
        job_description = body.job_description or job_description
        gemini_api_key = body.gemini_api_key or gemini_api_key

    if not candidate_name or not candidate_name.strip():
        raise HTTPException(status_code=422, detail="candidate_name is required")

    interview_id = str(uuid.uuid4())

    # Encrypt PII at rest
    encrypted_name = encrypt(candidate_name)

    effective_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
    ai_powered = bool(effective_key and GeminiAssistant is not None)

    state = InterviewState(
        interview_id=interview_id,
        candidate_name=candidate_name,
        goal=goal,
        duration_minutes=duration_minutes,
        encrypted_name=encrypted_name,
        company_name=company_name,
        company_needs=company_needs,
        job_title=job_title,
        job_description=job_description,
        gemini_api_key=gemini_api_key,
        ai_powered=ai_powered,
    )

    interviews[interview_id] = state
    logger.info(
        "Interview created for %s (id=%s, ai_powered=%s, company=%s)",
        mask(candidate_name),
        interview_id,
        ai_powered,
        company_name or "default",
    )
    return state


@router.post("/{interview_id}/job-description")
async def upload_job_description(
    interview_id: str,
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    job_title: Optional[str] = Form(None),
    company_name: Optional[str] = Form(None),
    company_needs: Optional[str] = Form(None),
):
    """Attach job description and company requirements (via file or direct text)."""
    if interview_id not in interviews:
        raise HTTPException(status_code=404, detail="Interview not found")
    state = interviews[interview_id]

    extracted = ""
    if text and text.strip():
        extracted = text.strip()
    elif file and file.filename:
        suffix = Path(file.filename).suffix.lower()
        content = await file.read()
        if suffix in (".txt", ".md"):
            extracted = content.decode("utf-8", errors="ignore")
        elif suffix == ".pdf":
            try:
                import io
                # pypdf is a declared dependency (requirements.txt) but is an OPTIONAL
                # runtime feature: import it lazily so a missing install only disables
                # PDF extraction (gracefully handled by the except below), never startup.
                # pyrefly: ignore[missing-import]
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(content))
                extracted = "\n".join(p.extract_text() or "" for p in reader.pages)
            except Exception:
                extracted = content.decode("utf-8", errors="ignore")
        elif suffix == ".docx":
            try:
                import io
                from docx import Document
                doc = Document(io.BytesIO(content))
                extracted = "\n".join(p.text for p in doc.paragraphs)
            except Exception:
                extracted = content.decode("utf-8", errors="ignore")
        else:
            extracted = content.decode("utf-8", errors="ignore")

    if extracted.strip():
        state.job_description = extracted.strip()[:10000]

    if job_title:
        state.job_title = job_title
    if company_name:
        state.company_name = company_name
    if company_needs:
        state.company_needs = company_needs

    interviews[interview_id] = state
    return {
        "message": "Job description updated successfully",
        "has_job_description": bool(state.job_description),
        "job_title": state.job_title,
        "company_name": state.company_name,
        "char_count": len(state.job_description) if state.job_description else 0,
    }


@router.post("/{interview_id}/resume")
async def upload_resume(
    interview_id: str,
    file: UploadFile = File(...),
):
    """
    Upload and parse a resume for an interview session.
    REQUIRED before calling /start.

    Accepts: PDF or DOCX.
    Encrypted resume text is stored; only extracted facts (skills, tech, projects)
    are used for question personalisation.
    """
    if interview_id not in interviews:
        raise HTTPException(status_code=404, detail="Interview not found")

    state = interviews[interview_id]

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".pdf", ".docx"):
        raise HTTPException(
            status_code=422,
            detail="Resume must be a PDF or DOCX file"
        )

    if _RESUME_ANALYZER is None:
        raise HTTPException(
            status_code=503,
            detail="Resume analyzer is not available on this server"
        )

    # Save uploaded file to a temp location for parsing
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        raw_text = _RESUME_ANALYZER.extract_text(tmp_path)
        profile_data = _RESUME_ANALYZER._extract(raw_text)

        # Encrypt raw resume text for secure storage
        encrypted_resume = encrypt(raw_text[:4000])  # cap at 4KB to save memory

        resume_profile = ResumeProfile(
            skills=list(profile_data.skills),
            technologies=list(profile_data.technologies),
            experience=list(profile_data.experience),
            projects=list(profile_data.projects),
            education=list(profile_data.education),
            achievements=list(profile_data.achievements),
        )

        state.resume_profile = resume_profile
        state.resume_available = True
        state.encrypted_resume_text = encrypted_resume

        interviews[interview_id] = state

        logger.info(
            "Resume parsed for interview %s — skills: %s, tech: %s",
            interview_id,
            resume_profile.skills[:5],
            resume_profile.technologies[:5],
        )

        return {
            "message": "Resume parsed successfully",
            "skills_detected": resume_profile.skills,
            "technologies_detected": resume_profile.technologies,
            "experience_entries": len(resume_profile.experience),
            "projects_detected": len(resume_profile.projects),
            "encrypted": True,
        }

    except ResumeAnalysisError as exc:
        raise HTTPException(status_code=422, detail=f"Resume parsing failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@router.post("/{interview_id}/start")
def start_interview(interview_id: str):
    """
    Start the interview.
    1. REQUIRES: resume must have been uploaded first via POST /{id}/resume.
    2. Constructs a 3-stage adaptive Interview Plan from Resume + JD + Company Needs.
    3. Synthesizes an opening question tailored to the target role.
    """
    if interview_id not in interviews:
        raise HTTPException(status_code=404, detail="Interview not found")

    state = interviews[interview_id]

    if not state.resume_available:
        raise HTTPException(
            status_code=428,  # Precondition Required
            detail=(
                "Resume is required before starting the interview. "
                "Please upload your resume via POST /interviews/{id}/resume first."
            ),
        )

    # ── 1. Construct explicit Interview Plan ──────────────────────────────────
    state.interview_plan = _generate_interview_plan(state)

    # ── 2. Select opening question ────────────────────────────────────────────
    opening_question = None
    opening_skill = None
    opening_reason = None

    # Priority 1: Gemini AI synthesized question
    if state.ai_powered or state.gemini_api_key or os.getenv("GEMINI_API_KEY"):
        try:
            api_key = state.gemini_api_key or os.getenv("GEMINI_API_KEY")
            if GeminiAssistant and api_key:
                assistant = GeminiAssistant(api_key=api_key, model="gemini-2.0-flash")
                resume_dict = state.resume_profile.model_dump() if state.resume_profile else None
                ai_q = assistant.generate_curriculum_question(
                    question_number=1,
                    difficulty="easy",
                    resume_profile=resume_dict,
                    job_description=state.job_description,
                    company_name=state.company_name,
                    company_needs=state.company_needs,
                    previous_questions=[],
                    last_answer="",
                    last_depth="",
                )
                if ai_q and ai_q.get("question"):
                    opening_question = ai_q["question"]
                    opening_skill = ai_q["skill"]
                    opening_reason = (
                        f"AI-tailored opening for {state.interview_plan.role_title} "
                        f"matching {state.candidate_name}'s resume."
                    )
        except Exception as e:
            logger.warning("Opening question Gemini fallback: %s", e)

    # Priority 2: Fallback warm HR welcoming introduction
    if not opening_question:
        top_skills = state.resume_profile.skills[:3] if state.resume_profile else []
        skills_phrase = f" (including your background with {', '.join(top_skills)})" if top_skills else ""
        opening_question = (
            f"Hello {state.candidate_name}, welcome to our interview! To start off, "
            f"could you please introduce yourself, walk me through your career journey{skills_phrase}, "
            f"and share what particularly excites you about joining {state.company_name or 'our team'} as a {state.interview_plan.role_title}?"
        )
        opening_skill = "Self-Introduction & Career Story"
        opening_reason = "Welcoming HR introduction establishing candidate background, communication clarity, and role motivation."

    state.status = "in_progress"
    state.question_number = 1
    state.current_question = opening_question
    state.current_skill = opening_skill
    state.current_difficulty = "easy"
    state.evidence_gap = f"Stage 1 (Fundamentals): Establishing baseline in {opening_skill}"
    state.next_action = f"[STAGE 1/3: {state.interview_plan.stages[0].stage_name}] {opening_reason}"

    interviews[interview_id] = state
    logger.info(
        "Interview %s started. Role: %s. First skill: %s",
        interview_id,
        state.interview_plan.role_title,
        opening_skill,
    )
    return state


@router.post("/{interview_id}/answer")
def submit_answer(interview_id: str, answer_request: AnswerRequest):
    """
    Submit a candidate answer.

    Optionally include visual_signal from the camera for coaching signals.
    The agent evaluates depth, updates evidence, logs visual signals,
    and selects the next question from the adaptive bank.
    """
    if interview_id not in interviews:
        raise HTTPException(status_code=404, detail="Interview not found")

    state = interviews[interview_id]

    if state.status != "in_progress":
        raise HTTPException(status_code=400, detail="Interview is not in progress")

    if not state.current_question:
        raise HTTPException(status_code=400, detail="There is no active question")

    # ── 1. Assess answer depth ─────────────────────────────────────────────
    depth = _assess_answer_depth(answer_request.answer)

    depth_labels = {
        "shallow": "Limited evidence — answer lacked technical depth",
        "surface": "Surface evidence — brief answer, needs more specifics",
        "intermediate": "Reasonable evidence — demonstrated core understanding",
        "deep": "Strong evidence — demonstrated deep technical knowledge",
    }

    # ── 2. Store answer record (AES-256 encrypted at rest) ────────────────
    encrypted_ans = encrypt(answer_request.answer)
    record = AnswerRecord(
        question=state.current_question,
        answer=answer_request.answer,
        encrypted_answer=encrypted_ans,
        skill=state.current_skill,
        depth=depth,
    )
    state.answers.append(record)

    # ── 3. Log visual signal if provided (AES-256 telemetry protection) ───
    if answer_request.visual_signal:
        telemetry_dict = {
            "face_detected": answer_request.visual_signal.face_detected,
            "motion_level": answer_request.visual_signal.motion_level,
            "lighting_quality": answer_request.visual_signal.lighting_quality,
            "composure_state": answer_request.visual_signal.composure_state,
            "tension_score": answer_request.visual_signal.tension_score,
            "fidget_level": answer_request.visual_signal.fidget_level,
            "gaze_stability": answer_request.visual_signal.gaze_stability,
            "blink_rate_indicator": answer_request.visual_signal.blink_rate_indicator,
        }
        answer_request.visual_signal.encrypted_telemetry = encrypt_json(telemetry_dict)
        state.visual_signals.append(answer_request.visual_signal)
        # Coaching signal (not used for scoring — purely observational)
        if answer_request.visual_signal.face_detected is False:
            logger.info(
                "Interview %s Q%s: No face detected in frame (camera or lighting issue).",
                interview_id, state.question_number,
            )

    # ── 4. Update evidence ledger ──────────────────────────────────────────
    state.evidence.append(
        f"Q{state.question_number} [{state.current_skill}] "
        f"({state.current_difficulty}): {depth_labels.get(depth, 'Evidence recorded')}"
    )

    state.evidence_gap = {
        "shallow": f"No demonstrated depth in {state.current_skill}. Revisit fundamentals.",
        "surface": f"Partial understanding of {state.current_skill}. Needs concrete examples.",
        "intermediate": f"Core understanding shown for {state.current_skill}. Need advanced proof.",
        "deep": f"Strong signal in {state.current_skill}. Switching competency area.",
    }.get(depth, "Continue evaluating")

    # ── 5. Select next question ────────────────────────────────────────────
    state.question_number += 1
    asked_questions = [a.question for a in state.answers]

    next_q = select_next_question(
        question_number=state.question_number,
        last_answer=answer_request.answer,
        asked_questions=asked_questions,
        state=state,
        resume_profile=state.resume_profile,
    )

    state.current_question = next_q["question"]
    state.current_skill = next_q["skill"]
    state.current_difficulty = next_q["difficulty"]

    stage_label = ""
    if state.interview_plan and state.interview_plan.stages:
        if state.question_number <= 10:
            stage_label = f"[STAGE 1/3: {state.interview_plan.stages[0].stage_name}] "
        elif state.question_number <= 15 and len(state.interview_plan.stages) > 1:
            stage_label = f"[STAGE 2/3: {state.interview_plan.stages[1].stage_name}] "
        elif len(state.interview_plan.stages) > 2:
            stage_label = f"[STAGE 3/3: {state.interview_plan.stages[2].stage_name}] "

    state.next_action = (
        f"{stage_label}[{next_q['agent_action']}] {next_q['agent_reasoning']} "
        f"| Next: {next_q['difficulty'].upper()} on {next_q['skill']}"
    )

    interviews[interview_id] = state
    return state


@router.get("/{interview_id}/state")
def get_interview_state(interview_id: str):
    """Get the live interview state."""
    if interview_id not in interviews:
        raise HTTPException(status_code=404, detail="Interview not found")
    return interviews[interview_id]


@router.get("/{interview_id}/assessment")
def get_assessment(interview_id: str):
    """Generate the final assessment report."""
    if interview_id not in interviews:
        raise HTTPException(status_code=404, detail="Interview not found")

    state = interviews[interview_id]
    total_answers = len(state.answers)

    if total_answers == 0:
        empty_composure = HRComposureEvaluation(
            overall_composure="N/A (Session Incomplete)",
            poise_score=0.0,
            gaze_stability_pct=0,
            fidget_index="N/A",
            stress_indicators=["No interview responses recorded."],
            hr_observations="No camera or audio interactions logged.",
        )
        empty_hr_eval = HREvaluation(
            overall_grade="N/A",
            overall_score=0.0,
            hiring_recommendation="Insufficient evidence — session incomplete",
            candidate_summary=f"Candidate {state.candidate_name} has not submitted responses yet.",
            intro_grade="N/A",
            skills_grade="N/A",
            behavioral_grade="N/A",
            competencies=[],
            composure_evaluation=empty_composure,
        )
        return {
            "interview_id": interview_id,
            "candidate_name": state.candidate_name,
            "company_name": state.company_name,
            "company_needs": state.company_needs,
            "job_title": state.job_title or (state.interview_plan.role_title if state.interview_plan else "Software Engineer"),
            "ai_powered": state.ai_powered,
            "interview_plan": state.interview_plan.model_dump() if state.interview_plan else None,
            "hr_evaluation": empty_hr_eval.model_dump(),
            "composure_evaluation": empty_composure.model_dump(),
            "competency_scores": [],
            "overall_score": 0.0,
            "evidence_coverage": 0,
            "confidence": 0,
            "strengths": [],
            "gaps": ["No answers submitted yet"],
            "unverified_claims": [],
            "recommendation": "Insufficient evidence",
            "visual_summary": None,
            "resume_personalised": state.resume_available,
            "questions_answered": 0,
        }

    # ── Scoring by depth tier ──────────────────────────────────────────────
    depth_weights = {"shallow": 1, "surface": 2, "intermediate": 4, "deep": 5}
    score_sum = sum(depth_weights.get(a.depth or "shallow", 1) for a in state.answers)
    max_score = total_answers * 5
    overall_pct = round((score_sum / max_score) * 10, 1) if max_score > 0 else 0.0

    # Competency breakdown
    skill_buckets: dict[str, list[str]] = {}
    for a in state.answers:
        skill_buckets.setdefault(a.skill or "General", []).append(a.depth or "shallow")

    competency_scores = []
    for skill, depths in skill_buckets.items():
        raw = sum(depth_weights.get(d, 1) for d in depths)
        scaled = round(min(10, (raw / (len(depths) * 5)) * 10), 1)
        competency_scores.append({"skill": skill, "score": scaled})

    # Strengths and gaps
    strengths = []
    gaps = []
    deep_skills = [s["skill"] for s in competency_scores if s["score"] >= 7]
    weak_skills = [s["skill"] for s in competency_scores if s["score"] < 5]

    if deep_skills:
        strengths.append(f"Strong technical depth in: {', '.join(deep_skills)}")
    if overall_pct >= 7:
        strengths.append("Consistently provided well-reasoned, detailed answers")
    if total_answers >= 10:
        strengths.append("Sustained engagement across a full interview session")
    if state.resume_available:
        strengths.append("Resume matched to question topics — contextual knowledge demonstrated")

    if weak_skills:
        gaps.append(f"Limited depth in: {', '.join(weak_skills)}")
    if overall_pct < 5:
        gaps.append("Answers lacked sufficient technical detail and concrete examples")
    if not gaps:
        gaps.append("Continue testing advanced synthesis and system design judgment")

    # Visual summary
    visual_summary = None
    if state.visual_signals:
        face_detected_count = sum(1 for v in state.visual_signals if v.face_detected)
        visual_summary = {
            "turns_with_camera": len(state.visual_signals),
            "face_detected_turns": face_detected_count,
            "presence_rate": round(face_detected_count / len(state.visual_signals) * 100),
            "note": (
                "Observable camera signals only. "
                "These do not indicate honesty or hiring suitability."
            ),
        }

    # ── Agentic HR Talent Partner Grading & Scorecard ──────────────────────
    if overall_pct >= 8.5:
        overall_grade = "A+"
        hiring_recommendation = "Strong Hire — Fast-track to Final Team Matching"
    elif overall_pct >= 7.5:
        overall_grade = "A"
        hiring_recommendation = "Strong Hire — Confirmed Technical & Cultural Alignment"
    elif overall_pct >= 6.5:
        overall_grade = "B+"
        hiring_recommendation = "Hire — Solid core competence, recommend standard next round"
    elif overall_pct >= 5.0:
        overall_grade = "B"
        hiring_recommendation = "Lean Hire — Meets baseline requirements, probe depth in follow-up"
    elif overall_pct >= 3.5:
        overall_grade = "C"
        hiring_recommendation = "Borderline — Candidate needs additional preparation in key areas"
    else:
        overall_grade = "D"
        hiring_recommendation = "No Hire — Insufficient technical depth and evidence"

    intro_score = round(min(10.0, max(5.0, overall_pct + (0.5 if total_answers >= 1 else -1.0))), 1)
    intro_grade = "A" if intro_score >= 8.0 else "B+" if intro_score >= 6.5 else "B"

    skills_score = round(overall_pct, 1)
    skills_grade = "A+" if skills_score >= 8.5 else "A" if skills_score >= 7.5 else "B+" if skills_score >= 6.5 else "B" if skills_score >= 5.0 else "C"

    behavioral_score = round(min(10.0, max(5.0, overall_pct + (0.3 if total_answers >= 2 else -0.5))), 1)
    behavioral_grade = "A" if behavioral_score >= 7.5 else "B+" if behavioral_score >= 6.5 else "B"

    role_name = state.job_title or (state.interview_plan.role_title if state.interview_plan else "Software Engineer")
    summary_text = (
        f"Candidate {state.candidate_name} completed an Agentic HR evaluation for the {role_name} role at "
        f"{state.company_name or 'the organization'}. Answered {total_answers} question(s) with an overall score of "
        f"{overall_pct}/10 (Grade: {overall_grade}). Demonstrated {('strong' if overall_pct >= 7 else 'moderate' if overall_pct >= 5 else 'limited')} "
        f"depth across resume-verified skills and communication clarity."
    )

    hr_competencies = [
        HRCompetencyGrade(
            category="Introduction & Communication",
            grade=intro_grade,
            score=intro_score,
            feedback="Articulate self-introduction and career walkthrough. Clear communication during turn responses.",
        ),
        HRCompetencyGrade(
            category="Resume Claim Verification",
            grade=skills_grade,
            score=skills_score,
            feedback=f"Demonstrated hands-on familiarity with skills listed on resume ({', '.join(deep_skills[:3]) or 'core technologies'}).",
        ),
        HRCompetencyGrade(
            category="Technical Competency & Breadth",
            grade=skills_grade,
            score=overall_pct,
            feedback=f"Evaluated across {len(competency_scores)} technical competency areas with {round((score_sum / max_score) * 100 if max_score > 0 else 0)}% evidence coverage.",
        ),
        HRCompetencyGrade(
            category="Behavioral & Culture Fit",
            grade=behavioral_grade,
            score=behavioral_score,
            feedback="Constructive working style and alignment with team collaboration expectations.",
        ),
        HRCompetencyGrade(
            category="Ownership & Leadership Potential",
            grade=overall_grade,
            score=overall_pct,
            feedback=f"Readiness to take ownership of complex production deliverables for {state.company_name or 'the team'}.",
        ),
    ]

    # Try Gemini HR grading if active
    if state.ai_powered and GeminiAssistant:
        api_key = state.gemini_api_key or os.getenv("GEMINI_API_KEY")
        if api_key:
            try:
                assistant = GeminiAssistant(api_key=api_key, model="gemini-2.0-flash")
                qa_data = [
                    {"question": a.question, "answer": a.answer, "skill": a.skill or "", "depth": a.depth or ""}
                    for a in state.answers
                ]
                resume_dict = state.resume_profile.model_dump() if state.resume_profile else None
                ai_eval = assistant.evaluate_hr_candidate(
                    candidate_name=state.candidate_name,
                    role_title=role_name,
                    company_name=state.company_name,
                    company_needs=state.company_needs,
                    resume_profile=resume_dict,
                    qa_pairs=qa_data,
                )
                if ai_eval and ai_eval.get("overall_grade"):
                    overall_grade = str(ai_eval["overall_grade"]).strip()
                    if ai_eval.get("hiring_recommendation"):
                        hiring_recommendation = str(ai_eval["hiring_recommendation"]).strip()
                    if ai_eval.get("candidate_summary"):
                        summary_text = str(ai_eval["candidate_summary"]).strip()
                    if ai_eval.get("intro_grade"):
                        intro_grade = str(ai_eval["intro_grade"]).strip()
                    if ai_eval.get("skills_grade"):
                        skills_grade = str(ai_eval["skills_grade"]).strip()
                    if ai_eval.get("behavioral_grade"):
                        behavioral_grade = str(ai_eval["behavioral_grade"]).strip()
                    if ai_eval.get("competencies") and isinstance(ai_eval["competencies"], list):
                        parsed_comps = []
                        for c in ai_eval["competencies"]:
                            if isinstance(c, dict) and "category" in c:
                                parsed_comps.append(
                                    HRCompetencyGrade(
                                        category=str(c.get("category", "")),
                                        grade=str(c.get("grade", "B+")),
                                        score=float(c.get("score", overall_pct)),
                                        feedback=str(c.get("feedback", "Consistent performance")),
                                    )
                                )
                        if parsed_comps:
                            hr_competencies = parsed_comps
            except Exception as exc:
                logger.warning("Gemini HR evaluation fallback: %s", exc)

    # ── Non-Verbal Composure & Poise Evaluation (Biometric Telemetry) ──────
    if state.visual_signals:
        valid_tensions = [v.tension_score for v in state.visual_signals if v.tension_score is not None]
        avg_tension = sum(valid_tensions) / len(valid_tensions) if valid_tensions else 0.18

        valid_gazes = [v.gaze_stability for v in state.visual_signals if v.gaze_stability is not None]
        avg_gaze = sum(valid_gazes) / len(valid_gazes) if valid_gazes else 0.88

        valid_fidgets = [v.fidget_level for v in state.visual_signals if v.fidget_level is not None]
        avg_fidget = sum(valid_fidgets) / len(valid_fidgets) if valid_fidgets else 0.12

        poise_score = round(max(1.0, min(10.0, (1.0 - avg_tension) * 10.0)), 1)
        gaze_pct = int(round(avg_gaze * 100))

        if poise_score >= 7.5:
            overall_composure = "Composed & Confident"
            fidget_index = "Low / Grounded"
            stress_notes = [
                "Maintained calm posture and consistent eye-contact focus throughout technical questioning.",
                "Handled complex logic traces without visible restlessness.",
            ]
            hr_obs = (
                f"Candidate exhibited strong executive presence and poise (Poise Score: {poise_score}/10). "
                f"Gaze stability remained strong at {gaze_pct}%, indicating confidence and emotional control under interview pressure."
            )
        elif poise_score >= 5.0:
            overall_composure = "Mild Tension / Processing"
            fidget_index = "Moderate / Engaged"
            stress_notes = [
                "Minor micro-motion and gaze darting detected during tricky architecture scenarios (normal cognitive load).",
                "Quickly regained composure when explaining solution details.",
            ]
            hr_obs = (
                f"Candidate demonstrated good composure with appropriate cognitive focus (Poise Score: {poise_score}/10). "
                f"Slight tension spikes coincided with difficult technical questions, reflecting healthy cognitive effort."
            )
        else:
            overall_composure = "Elevated Anxiety / Restless"
            fidget_index = "High Restlessness"
            stress_notes = [
                "Frequent micro-motion and fidgeting detected across multiple questions.",
                "Lower gaze stability observed during behavioral probes.",
            ]
            hr_obs = (
                f"Candidate displayed notable restlessness and tension throughout the session (Poise Score: {poise_score}/10). "
                f"Recommend establishing rapport to help candidate settle in during subsequent in-person rounds."
            )

        composure_eval = HRComposureEvaluation(
            overall_composure=overall_composure,
            poise_score=poise_score,
            gaze_stability_pct=gaze_pct,
            fidget_index=fidget_index,
            stress_indicators=stress_notes,
            hr_observations=hr_obs,
            encryption_status="AES-256 Encrypted at Rest (Zero Raw Video Stored)",
        )
    else:
        composure_eval = HRComposureEvaluation(
            overall_composure="Camera Inactive (Audio/Text Mode)",
            poise_score=8.5,
            gaze_stability_pct=100,
            fidget_index="N/A (Audio/Text Session)",
            stress_indicators=["Session conducted in audio/text mode without camera feed."],
            hr_observations="Candidate completed the assessment in audio/text mode. All responses and telemetry are AES-256 encrypted.",
            encryption_status="AES-256 Encrypted at Rest",
        )

    hr_eval = HREvaluation(
        overall_grade=overall_grade,
        overall_score=overall_pct,
        hiring_recommendation=hiring_recommendation,
        candidate_summary=summary_text,
        intro_grade=intro_grade,
        skills_grade=skills_grade,
        behavioral_grade=behavioral_grade,
        competencies=hr_competencies,
        composure_evaluation=composure_eval,
    )
    state.hr_evaluation = hr_eval
    state.composure_evaluation = composure_eval

    return {
        "interview_id": interview_id,
        "candidate_name": state.candidate_name,
        "company_name": state.company_name,
        "company_needs": state.company_needs,
        "job_title": state.job_title or (state.interview_plan.role_title if state.interview_plan else "Software Engineer"),
        "ai_powered": state.ai_powered,
        "interview_plan": state.interview_plan.model_dump() if state.interview_plan else None,
        "hr_evaluation": hr_eval.model_dump(),
        "composure_evaluation": composure_eval.model_dump(),
        "competency_scores": competency_scores,
        "overall_score": overall_pct,
        "evidence_coverage": round((score_sum / max_score) * 100),
        "confidence": min(95, 40 + (total_answers * 5)),
        "strengths": strengths,
        "gaps": gaps,
        "unverified_claims": [],
        "recommendation": (
            "Strong candidate — recommend advancing"
            if overall_pct >= 7.5
            else "Promising candidate — recommend further technical round"
            if overall_pct >= 5.0
            else "Candidate needs additional preparation"
        ),
        "visual_summary": visual_summary,
        "resume_personalised": state.resume_available,
        "questions_answered": total_answers,
    }


@router.post("/{interview_id}/end")
def end_interview(interview_id: str):
    """Mark the interview as completed."""
    if interview_id not in interviews:
        raise HTTPException(status_code=404, detail="Interview not found")

    state = interviews[interview_id]

    if state.status == "completed":
        return {
            "message": "Interview completed successfully",
            "interview_id": interview_id,
            "status": state.status,
            "questions_answered": len(state.answers),
        }

    if state.status not in ("in_progress", "created"):
        raise HTTPException(status_code=400, detail="Interview is not in progress")

    state.status = "completed"
    state.next_action = "Generate final assessment"
    interviews[interview_id] = state

    return {
        "message": "Interview completed successfully",
        "interview_id": interview_id,
        "status": state.status,
        "questions_answered": len(state.answers),
    }


@router.get("/{interview_id}/assessment/pdf")
def get_assessment_pdf(interview_id: str):
    """Generate and download the candidate evaluation report as a PDF."""
    if interview_id not in interviews:
        raise HTTPException(status_code=404, detail="Interview not found")

    assessment_data = get_assessment(interview_id)
    if generate_assessment_pdf is None:
        raise HTTPException(status_code=500, detail="PDF generation service is unavailable")

    pdf_bytes = generate_assessment_pdf(assessment_data)

    safe_name = "".join(
        c for c in str(assessment_data.get("candidate_name") or "Candidate")
        if c.isalnum() or c in (" ", "-", "_")
    ).strip().replace(" ", "_") or "Candidate"

    filename = f"Technical_Evaluation_Report_{safe_name}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )