"""
Demonstration walkthrough of the InterviewOne AI Evaluation Module (Person 3).
Simulates a multi-turn interview showcasing:
1. 'Claims != Evidence' detection and probe generation
2. Claim verification resolution
3. Vagueness detection and follow-up
4. Contradiction Detection vs Resume
5. Live Competency Map & Evidence Gap tracking
6. Zero-Unsupported-Score Guardrail
7. Final Dossier Report export in Markdown and JSON
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation import Evaluator, ActionRecommendation


def main():
    print("=" * 75)
    print(" INTERVIEWONE AI — PERSON 3 (EVIDENCE + EVALUATION) DEMO")
    print("=" * 75)

    evaluator = Evaluator()
    resume = (
        "Alex Chen — Senior Backend Systems Engineer\n"
        "• 5 years experience designing distributed systems with Redis and PostgreSQL\n"
        "• Led Kubernetes cluster deployment and Helm chart automation for microservices\n"
        "• Advanced Python concurrency and asynchronous systems"
    )

    # --- TURN 1: Candidate makes broad claim ---
    print("\n[TURN 1 — Unverified Ownership Claim]")
    q1 = "Can you describe your role and experience in backend systems?"
    a1 = "I designed the entire backend architecture myself from scratch for the enterprise platform."
    print(f"Question: {q1}")
    print(f"Answer:   {a1}")

    result1 = evaluator.process_turn(
        turn_index=1,
        question=q1,
        answer=a1,
        current_competency="System Design",
        candidate_resume_context=resume,
    )

    print(f"-> Recommended Action: {result1.recommended_action.value}")
    print(f"-> Why:                {result1.action_reason}")
    print(f"-> Suggested Probe:    {result1.suggested_followup_question}")

    # --- TURN 2: Candidate answers the verification probe ---
    print("\n" + "-" * 75)
    print("[TURN 2 — Verification Probe Resolution]")
    q2 = result1.suggested_followup_question
    a2 = (
        "I personally chose Redis Pub/Sub combined with Celery workers to decouple the HTTP ingestion layer. "
        "I also added Redis read-replicas and sharded the keys by tenant_id to prevent write bottlenecks."
    )
    print(f"Question: {q2}")
    print(f"Answer:   {a2}")

    result2 = evaluator.process_turn(
        turn_index=2,
        question=q2,
        answer=a2,
        current_competency="System Design",
        candidate_resume_context=resume,
    )

    comp_sd = result2.live_competency_map["System Design"]
    print(f"-> Claim Status:       VERIFIED and converted into EvidenceItem")
    print(f"-> Current SD Score:   {comp_sd.score}/5.0")
    print(f"-> Current SD Conf:    {comp_sd.confidence:.2f}")
    print(f"-> Evidence Count:     {len(comp_sd.evidence_list)}")
    print(f"-> Recommended Action: {result2.recommended_action.value}")

    # --- TURN 3: Candidate gives a vague answer ---
    print("\n" + "-" * 75)
    print("[TURN 3 — Vague Answer Handling]")
    q3 = "How did you monitor system latency and database query performance?"
    a3 = "We had very scalable monitoring. Everything was clean, modern, and followed best practices."
    print(f"Question: {q3}")
    print(f"Answer:   {a3}")

    result3 = evaluator.process_turn(
        turn_index=3,
        question=q3,
        answer=a3,
        current_competency="Debugging & Troubleshooting",
        candidate_resume_context=resume,
    )

    print(f"-> Vagueness Score:    {result3.analysis.vagueness_score:.2f} (High)")
    print(f"-> Recommended Action: {result3.recommended_action.value}")
    print(f"-> Why:                {result3.action_reason}")
    print(f"-> Suggested Probe:    {result3.suggested_followup_question}")

    # --- TURN 4: Candidate gives strong technical Python answer ---
    print("\n" + "-" * 75)
    print("[TURN 4 — Technical Python Competency Demonstration]")
    q4 = "How does Python handle concurrency under the Global Interpreter Lock (GIL)?"
    a4 = (
        "The GIL ensures only one native thread executes Python bytecode at a time. For I/O-bound tasks, "
        "asyncio is optimal because the thread yields during network waits. For CPU-bound tasks, we spawn "
        "separate processes using multiprocessing or Celery workers to utilize all CPU cores."
    )
    print(f"Question: {q4}")
    print(f"Answer:   {a4}")

    result4 = evaluator.process_turn(
        turn_index=4,
        question=q4,
        answer=a4,
        current_competency="Python",
        candidate_resume_context=resume,
    )

    comp_py = result4.live_competency_map["Python"]
    print(f"-> Python Score:       {comp_py.score}/5.0")
    print(f"-> Python Conf:        {comp_py.confidence:.2f}")
    print(f"-> Recommended Action: {result4.recommended_action.value}")

    # --- TURN 5: Injected Contradiction vs Resume ---
    print("\n" + "-" * 75)
    print("[TURN 5 — Judge Mode Perturbation: Contradiction vs Resume]")
    q5 = "How did you manage container orchestration across nodes in production?"
    a5 = "To be honest, I never worked with Kubernetes or container orchestration before. We just ran scripts on bare VMs."
    print(f"Question: {q5}")
    print(f"Answer:   {a5}")

    result5 = evaluator.process_turn(
        turn_index=5,
        question=q5,
        answer=a5,
        current_competency="System Design",
        candidate_resume_context=resume,
    )

    print(f"-> Recommended Action: {result5.recommended_action.value}")
    print(f"-> Why:                {result5.action_reason}")
    print(f"-> Clarification Q:    {result5.suggested_followup_question}")
    print(f"-> Contradictions:     {len(result5.contradictions)} discrepancy flagged!")

    # --- LIVE COMPETENCY & GAP RADAR ---
    print("\n" + "=" * 75)
    print(" LIVE COMPETENCY & EVIDENCE GAP MAP (Sent to Person 1 & 4)")
    print("=" * 75)
    for name, state in result5.live_competency_map.items():
        gap_bar = "#" * int(state.evidence_gap * 4)
        print(f"{name:30} | Score: {state.score:4.1f}/5 | Conf: {state.confidence:4.2f} | Gap: {state.evidence_gap:4.2f} [{gap_bar}]")

    largest_gap, gap_val = evaluator.evidence_manager.get_largest_evidence_gap()
    print(f"\n[NEXT ACTION FOR PERSON 1 PLANNER]: Target '{largest_gap}' (Largest Gap: {gap_val:.2f})")

    # --- FINAL REPORT DOSSIER EXPORT ---
    print("\n" + "=" * 75)
    print(" FINAL CANDIDATE ASSESSMENT DOSSIER EXPORT")
    print("=" * 75)
    md_path, json_path = evaluator.export_report(
        interview_id="int_hackathon_demo_01",
        candidate_name="Alex Chen",
        job_title="Senior Backend Systems Engineer",
        output_dir=str(Path(__file__).resolve().parent),
    )

    print(f"-> Markdown Report Saved: {md_path}")
    print(f"-> JSON Dossier Saved:    {json_path}")
    print("=" * 75)


if __name__ == "__main__":
    main()
