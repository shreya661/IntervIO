import logging
from typing import Optional, Dict, List, Any, Tuple
from .schemas import (
    EvaluationTurnResult,
    ActionRecommendation,
    CompetencyState,
    EvidenceStatus,
    Contradiction,
    FinalAssessmentReport,
    InterviewMode,
)
from .answer_analyzer import AnswerAnalyzer
from .evidence_manager import EvidenceManager
from .contradiction_detector import ContradictionDetector
from .verifier import ClaimVerifier
from .report_generator import ReportGenerator
from .mocks import get_default_competencies

logger = logging.getLogger("person3.evaluator")


class Evaluator:
    """
    Production assessment coordinator.
    This is the primary class called by Person 1 (Agent Controller) on every candidate answer.

    Usage:
        evaluator = Evaluator()                              # Default SE competencies, Assessment mode
        evaluator = Evaluator(competencies={"Python": 4.5})  # Custom competencies
        evaluator = Evaluator(interview_mode=InterviewMode.PRACTICE)  # Practice mode
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        initial_competencies: Optional[Dict[str, CompetencyState]] = None,
        competencies: Optional[Dict[str, float]] = None,
        interview_mode: InterviewMode = InterviewMode.ASSESSMENT,
    ):
        """
        Args:
            api_key: OpenAI API key for LLM-powered analysis (falls back to heuristic if None)
            initial_competencies: Full CompetencyState map (advanced use, e.g. from job config)
            competencies: Simple {competency_name: priority} dict for quick initialization
            interview_mode: ASSESSMENT (default) | PRACTICE | CONFIDENCE_COACH
        """
        from .evidence_manager import build_competency_map

        if initial_competencies:
            comp_map = initial_competencies
        elif competencies:
            comp_map = build_competency_map(competencies)
        else:
            comp_map = get_default_competencies()

        self.interview_mode = interview_mode
        self.evidence_manager = EvidenceManager(comp_map)
        self.analyzer = AnswerAnalyzer(api_key=api_key)
        self.contradiction_detector = ContradictionDetector(api_key=api_key)
        self.verifier = ClaimVerifier()
        self.turn_history: List[EvaluationTurnResult] = []
        self.all_contradictions: List[Contradiction] = []
        self.past_answers: List[Dict[str, Any]] = []
        self.active_verification_claim_id: Optional[str] = None
        self._remaining_seconds: Optional[int] = None
        self._support_interventions_count: int = 0
        self._answer_changes_detected: int = 0

    # ────────────────────────────────────────────────────────────
    # Public: Judge Mode / Event Injection (for Person 1 + Demo)
    # ────────────────────────────────────────────────────────────

    def inject_judge_event(self, event: Dict[str, Any]):
        """
        Receives judge-injected runtime events during the hackathon demo.
        Supported event types:
          { "type": "TIME_REDUCTION", "value": 120 }
          { "type": "CAMERA_FAILURE" }
          { "type": "CONTRADICTION_FOUND" }
          { "type": "REQUIREMENT_CHANGE", "new_competencies": {"Security": 5.0} }
        """
        event_type = event.get("type", "")

        if event_type == "TIME_REDUCTION":
            self._remaining_seconds = int(event.get("value", 120))
            logger.warning(f"[JUDGE EVENT] Time reduced to {self._remaining_seconds}s. Switching to PRIORITIZE_HIGH_VALUE mode.")

        elif event_type == "CAMERA_FAILURE":
            logger.warning("[JUDGE EVENT] Camera unavailable. Visual signals disabled.")

        elif event_type == "REQUIREMENT_CHANGE":
            new_comps = event.get("new_competencies", {})
            from .evidence_manager import build_competency_map
            for name, priority in new_comps.items():
                if name not in self.evidence_manager.competency_map:
                    new_map = build_competency_map({name: priority})
                    self.evidence_manager.competency_map[name] = new_map[name]
                    logger.info(f"[JUDGE EVENT] Added new required competency: {name} (priority {priority})")

        elif event_type == "CONTRADICTION_FOUND":
            logger.warning("[JUDGE EVENT] External contradiction injected by judge.")

    # ────────────────────────────────────────────────────────────
    # Main: Turn Processing
    # ────────────────────────────────────────────────────────────

    def process_turn(
        self,
        turn_index: int,
        question: str,
        answer: str,
        current_competency: str,
        stt_confidence: float = 1.0,
        job_context: Optional[str] = None,
        candidate_resume_context: Optional[str] = None,
    ) -> EvaluationTurnResult:
        """
        Executes the complete evaluation turn pipeline.
        Safe: never raises — logs errors and returns degraded result instead.
        """
        # ── Pre-checks: Special candidate signals ──

        # Candidate asking for question clarification — re-ask, don't score
        if ContradictionDetector.detect_clarification_request(answer):
            logger.info(f"[TURN {turn_index}] Candidate requested clarification of question.")
            from .schemas import TurnAnalysisResult, DepthLevel
            empty_analysis = TurnAnalysisResult(
                technical_correctness=0.0,
                depth_level=DepthLevel.SURFACE,
                vagueness_score=0.0,
                needs_followup=False,
            )
            return EvaluationTurnResult(
                turn_index=turn_index,
                competency_tested=current_competency,
                analysis=empty_analysis,
                new_evidence=[],
                claims_flagged=[],
                contradictions=[],
                live_competency_map=self.evidence_manager.get_live_map(),
                recommended_action=ActionRecommendation.PROBE_VAGUE,
                action_reason="Candidate requested question clarification. Rephrasing before scoring.",
                suggested_followup_question=f"Let me rephrase: {question} — specifically, I'd like to understand your direct hands-on experience.",
            )

        # Candidate refusing to answer — don't score zero, switch competency
        if ContradictionDetector.detect_refusal(answer):
            logger.info(f"[TURN {turn_index}] Candidate refused / unable to answer {current_competency}.")
            comp = self.evidence_manager.get_competency(current_competency)
            comp.status = EvidenceStatus.EVIDENCE_GAP
            comp.missing_evidence.append("Candidate unable to demonstrate during session")
            next_gap_comp, gap_val = self.evidence_manager.get_largest_evidence_gap()
            from .schemas import TurnAnalysisResult, DepthLevel
            empty_analysis = TurnAnalysisResult(
                technical_correctness=0.0,
                depth_level=DepthLevel.SURFACE,
                vagueness_score=0.0,
                needs_followup=False,
            )
            return EvaluationTurnResult(
                turn_index=turn_index,
                competency_tested=current_competency,
                analysis=empty_analysis,
                new_evidence=[],
                claims_flagged=[],
                contradictions=[],
                live_competency_map=self.evidence_manager.get_live_map(),
                recommended_action=ActionRecommendation.SWITCH_COMPETENCY,
                action_reason=f"Candidate declined to answer {current_competency}. Evidence gap recorded. Moving to '{next_gap_comp}'.",
                suggested_followup_question=None,
            )

        # Candidate changing / retracting a prior answer
        if ContradictionDetector.detect_self_correction(answer):
            self._answer_changes_detected += 1
            logger.warning(f"[TURN {turn_index}] Candidate self-corrected a prior statement (total: {self._answer_changes_detected}).")

        # ── Step 1: Resolve a pending verification probe if active ──
        if self.active_verification_claim_id:
            claim = self.evidence_manager.claims_ledger.get(self.active_verification_claim_id)
            if claim:
                try:
                    verified, rationale = self.verifier.evaluate_probe_response(claim, answer)
                    self.evidence_manager.resolve_claim(
                        claim_id=self.active_verification_claim_id,
                        verified=verified,
                        verification_response=answer,
                        candidate_turn_index=turn_index,
                    )
                    logger.info(f"[VERIFIER] Claim '{claim.claim_id}' resolved: verified={verified}. {rationale}")
                except Exception as e:
                    logger.error(f"[VERIFIER] Failed to evaluate probe response: {e}")
            self.active_verification_claim_id = None

        # ── Step 2: Detect Contradictions vs Resume & Prior Answers ──
        contradictions = []
        try:
            contradictions = self.contradiction_detector.detect_contradictions(
                current_answer=answer,
                resume_context=candidate_resume_context,
                prior_answers=self.past_answers,
            )
            if contradictions:
                self.all_contradictions.extend(contradictions)
                logger.warning(f"[CONTRADICTION] {len(contradictions)} new contradiction(s) detected on turn {turn_index}.")
        except Exception as e:
            logger.error(f"[CONTRADICTION DETECTOR] Failed on turn {turn_index}: {e}")

        # ── Step 3: Analyze the answer for depth, facts, vagueness ──
        try:
            analysis = self.analyzer.analyze(
                question=question,
                answer=answer,
                target_competency=current_competency,
                turn_index=turn_index,
                job_context=job_context,
                candidate_resume_context=candidate_resume_context,
            )
        except Exception as e:
            logger.error(f"[ANALYZER] Failed on turn {turn_index}: {e}. Using safe fallback.")
            from .schemas import TurnAnalysisResult, DepthLevel
            analysis = TurnAnalysisResult(
                technical_correctness=2.5,
                depth_level=DepthLevel.FUNDAMENTAL,
                vagueness_score=0.5,
                needs_followup=True,
                followup_angle="Could you elaborate further on that?"
            )

        # ── Step 4: Register new claims with tailored verification probes ──
        for claim in analysis.claims_detected:
            try:
                claim.verification_question = self.verifier.generate_probe(claim)
                self.evidence_manager.register_claim(claim)
                logger.info(f"[CLAIMS] New claim registered: '{claim.claim_text[:50]}' → probe generated.")
            except Exception as e:
                logger.error(f"[CLAIMS] Failed to register claim: {e}")

        # ── Step 5: Ingest evidence → update score & confidence ──
        try:
            comp_state = self.evidence_manager.add_turn_evidence(
                competency_name=current_competency,
                new_evidence=analysis.demonstrated_evidence,
                technical_accuracy=analysis.technical_correctness,
                stt_confidence=stt_confidence,
                unresolved_contradictions=self.all_contradictions,
            )
        except Exception as e:
            logger.error(f"[EVIDENCE MANAGER] Failed on turn {turn_index}: {e}")
            comp_state = self.evidence_manager.get_competency(current_competency)

        # ── Step 6: Record turn to history ──
        self.past_answers.append({
            "turn": turn_index,
            "question": question,
            "answer": answer,
            "competency": current_competency,
        })

        # ── Step 7: Action Recommendation Logic ──
        recommended_action, action_reason, suggested_q = self._decide_action(
            turn_index=turn_index,
            current_competency=current_competency,
            comp_state=comp_state,
            analysis=analysis,
            contradictions=contradictions,
            stt_confidence=stt_confidence,
        )

        # ── Step 8: Build result ──
        result = EvaluationTurnResult(
            turn_index=turn_index,
            competency_tested=current_competency,
            analysis=analysis,
            new_evidence=analysis.demonstrated_evidence,
            claims_flagged=analysis.claims_detected,
            contradictions=contradictions,
            live_competency_map=self.evidence_manager.get_live_map(),
            recommended_action=recommended_action,
            action_reason=action_reason,
            suggested_followup_question=suggested_q,
        )

        self.turn_history.append(result)
        logger.info(f"[TURN {turn_index}] {current_competency} → {recommended_action.value}")
        return result

    def _decide_action(
        self,
        turn_index: int,
        current_competency: str,
        comp_state: CompetencyState,
        analysis: Any,
        contradictions: List[Contradiction],
        stt_confidence: float,
    ):
        """Centralized action-selection logic. Returns (action, reason, suggested_question)."""

        # Priority 0: Time pressure (Judge Mode — PRIORITIZE_HIGH_VALUE)
        if self._remaining_seconds is not None and self._remaining_seconds <= 180:
            largest_gap_comp, gap_val = self.evidence_manager.get_largest_evidence_gap()
            untested = self.evidence_manager.get_untested_competencies()
            action_reason = (
                f"⏱ Only {self._remaining_seconds}s remaining. Targeting highest-value gap: "
                f"'{largest_gap_comp}' (gap={gap_val:.2f}). Skipping lower-priority items."
            )
            logger.info(f"[TIME PRESSURE] {action_reason}")
            return (
                ActionRecommendation.PRIORITIZE_HIGH_VALUE,
                action_reason,
                f"We have limited time — could you briefly address {largest_gap_comp}: what is the most critical trade-off you've dealt with in that area?"
            )

        # Priority 1: Poor audio — support intervention
        if stt_confidence < 0.55:
            self._support_interventions_count += 1
            return (
                ActionRecommendation.SUPPORT_INTERVENTION,
                f"Audio transcription confidence is very low ({stt_confidence:.2f}). Requesting candidate to rephrase.",
                "I may have had difficulty hearing your response clearly. Could you briefly restate your key point?"
            )


        # Priority 2: Contradiction detected
        if contradictions:
            target_c = contradictions[0]
            return (
                ActionRecommendation.VERIFY_CONTRADICTION,
                f"Contradiction detected ({target_c.severity} severity): {target_c.description}",
                target_c.clarification_question,
            )

        # Priority 3: Unverified claims
        pending_claims = [c for c in comp_state.claims_pending if c.verification_needed and not c.verified]
        if pending_claims:
            target_claim = pending_claims[0]
            self.active_verification_claim_id = target_claim.claim_id
            return (
                ActionRecommendation.VERIFY_CLAIM,
                f"Candidate made an unverified claim: '{target_claim.claim_text[:60]}'. Need to verify direct ownership.",
                target_claim.verification_question,
            )

        # Priority 4: Vague answer
        if analysis.vagueness_score >= 0.65:
            return (
                ActionRecommendation.PROBE_VAGUE,
                f"Answer was vague ({analysis.vagueness_reason or 'Lacked concrete trade-offs'}). Request concrete implementation details.",
                analysis.followup_angle or "Could you walk through a concrete production scenario where you had to debug or optimize that?",
            )

        # Priority 5: Competency saturated
        if comp_state.status == EvidenceStatus.WELL_TESTED:
            next_gap_comp, gap_val = self.evidence_manager.get_largest_evidence_gap()
            return (
                ActionRecommendation.SWITCH_COMPETENCY,
                (
                    f"'{current_competency}' is now well-tested (Score: {comp_state.score}/5, Conf: {comp_state.confidence:.2f}). "
                    f"Switch to '{next_gap_comp}' which has the largest remaining gap ({gap_val:.2f})."
                ),
                None,
            )

        # Priority 6: Technical weakness
        if analysis.technical_correctness < 2.5:
            return (
                ActionRecommendation.INVESTIGATE_FUNDAMENTALS,
                f"Candidate struggled with {current_competency}. Investigate missing baseline concepts.",
                f"Let's step back — could you explain the fundamental mechanism behind {current_competency} and where it most commonly fails?",
            )

        # Default: Probe deeper
        return (
            ActionRecommendation.PROBE_DEEPER,
            "Answer demonstrated solid knowledge. Probe deeper to test boundary conditions.",
            None,
        )

    # ────────────────────────────────────────────────────────────
    # Report Generation
    # ────────────────────────────────────────────────────────────

    def generate_final_report(
        self,
        interview_id: str,
        candidate_name: str,
        job_title: str,
        interview_duration_seconds: Optional[int] = None,
    ) -> FinalAssessmentReport:
        """Compiles the final evaluation dossier."""
        live_map = self.evidence_manager.get_live_map()
        active = [c for c in live_map.values() if len(c.evidence_list) > 0]

        # Gap 5: Dynamically prune missing_evidence for sub-skills that have been demonstrated
        for comp in live_map.values():
            if comp.evidence_list:
                proven_facts = " ".join(e.demonstrated_fact.lower() for e in comp.evidence_list)
                comp.missing_evidence = [
                    gap for gap in comp.missing_evidence
                    if not any(keyword in proven_facts for keyword in gap.lower().split() if len(keyword) > 4)
                ]

        if not active:
            overall_score, overall_conf, verdict = 0.0, 0.0, "Reject"
            rationale = "No evidence gathered during the interview."
        else:
            total_weight = sum(c.priority for c in active)
            overall_score = sum(c.score * c.priority for c in active) / total_weight
            overall_conf = sum(c.confidence * c.priority for c in active) / total_weight

            if overall_score >= 4.0 and overall_conf >= 0.75:
                verdict = "Strong Hire"
            elif overall_score >= 3.5 and overall_conf >= 0.65:
                verdict = "Hire"
            elif overall_score >= 2.8:
                verdict = "Lean Hire"
            elif overall_score >= 2.2:
                verdict = "Lean Reject"
            else:
                verdict = "Reject"

            mode_note = (
                f" [⚠️ Conducted in {self.interview_mode.value.upper()} mode"
                + (f" with {self._support_interventions_count} coaching intervention(s)" if self._support_interventions_count > 0 else "")
                + "]" if self.interview_mode != InterviewMode.ASSESSMENT else ""
            )
            rationale = (
                f"Candidate completed evaluation across {len(active)} technical competencies. "
                f"Weighted score: {overall_score:.2f}/5, confidence: {overall_conf:.2f}.{mode_note}"
            )

        all_claims = list(self.evidence_manager.claims_ledger.values())
        strengths = [
            f"Demonstrated {c.competency} depth (Score: {c.score}/5, Conf: {c.confidence:.2f})"
            for c in active if c.score >= 3.8 and c.confidence >= 0.60
        ]
        gaps = [
            f"Evidence gap in {c.competency}: missing {', '.join(c.missing_evidence[:2])}"
            for c in live_map.values() if c.status in [EvidenceStatus.UNTESTED, EvidenceStatus.EVIDENCE_GAP]
        ]

        return FinalAssessmentReport(
            interview_id=interview_id,
            candidate_name=candidate_name,
            job_title=job_title,
            interview_mode=self.interview_mode,
            interview_duration_seconds=interview_duration_seconds,
            overall_recommendation=verdict,
            overall_score=round(overall_score, 2),
            overall_confidence=round(overall_conf, 2),
            summary_rationale=rationale,
            competency_breakdown=live_map,
            verified_claims_count=sum(1 for c in all_claims if c.verified),
            unverified_claims_count=sum(1 for c in all_claims if not c.verified),
            contradictions_found=self.all_contradictions,
            key_strengths=strengths or ["Foundational technical awareness"],
            critical_gaps=gaps or ["None noted"],
            unsupported_score_prevention_applied=self.evidence_manager.guardrail_interventions_count > 0,
            support_interventions_count=self._support_interventions_count,
            answer_changes_detected=self._answer_changes_detected,
            audit_trail=[
                {
                    "turn": t.turn_index,
                    "competency": t.competency_tested,
                    "action": t.recommended_action.value,
                    "reason": t.action_reason,
                    "evidence_count": len(t.new_evidence),
                }
                for t in self.turn_history
            ],
        )

    def export_report(
        self,
        interview_id: str,
        candidate_name: str,
        job_title: str,
        output_dir: str = ".",
        interview_duration_seconds: Optional[int] = None,
    ) -> Tuple[str, str]:
        """Compiles and saves report as Markdown and JSON."""
        report = self.generate_final_report(interview_id, candidate_name, job_title, interview_duration_seconds)
        return ReportGenerator.save_report(report, output_dir=output_dir)
