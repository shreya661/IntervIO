"""
Rubric Scoring Engine for InterviewOne AI (Person 3).
Computes evidence-backed competency scores (1 to 5) with strict
Zero-Unsupported-Score Guardrail constraints.
"""

from typing import List, Tuple
from .schemas import (
    CompetencyState,
    CompetencyScore,
    EvidenceItem,
    DepthLevel,
)


class ScoringEngine:
    """
    Evaluates competency performance against an objective rubric.
    Enforces the 'Zero-Unsupported-Score' integrity rule:
    Never grant a high score (>= 4.0) without sufficient verified intermediate/advanced evidence.
    """

    @classmethod
    def evaluate_competency(
        cls,
        state: CompetencyState,
        latest_technical_accuracy: float = 3.5,
    ) -> Tuple[CompetencyScore, bool]:
        """
        Evaluates the competency score and returns (CompetencyScore, guardrail_applied: bool).
        """
        evidence_list: List[EvidenceItem] = state.evidence_list

        # If no evidence has been recorded at all
        if not evidence_list:
            score_obj = CompetencyScore(
                technical_accuracy=0.0,
                architectural_depth=0.0,
                practical_tradeoffs=0.0,
                communication_clarity=0.0,
                overall_score=0.0,
                rationale=f"No verified evidence yet recorded for {state.competency}.",
            )
            return score_obj, False

        # Count evidence depth distribution
        adv_count = sum(1 for e in evidence_list if e.depth_level == DepthLevel.ADVANCED)
        int_count = sum(1 for e in evidence_list if e.depth_level == DepthLevel.INTERMEDIATE)
        fund_count = sum(1 for e in evidence_list if e.depth_level in [DepthLevel.FUNDAMENTAL, DepthLevel.SURFACE])

        # 1. Base rubric dimension estimates from evidence
        if adv_count >= 2:
            arch_depth = 4.8
            tradeoffs = 4.5
        elif adv_count == 1:
            arch_depth = 4.2
            tradeoffs = 4.0
        elif int_count >= 2:
            arch_depth = 3.8
            tradeoffs = 3.5
        elif int_count == 1:
            arch_depth = 3.2
            tradeoffs = 3.0
        else:
            arch_depth = 2.0
            tradeoffs = 2.0

        clarity = min(5.0, 3.0 + (0.5 * len(evidence_list)))
        accuracy = max(1.0, min(5.0, latest_technical_accuracy))

        # Weighted calculation
        raw_overall = (accuracy * 0.35) + (arch_depth * 0.30) + (tradeoffs * 0.20) + (clarity * 0.15)

        # 2. STRICT ZERO-UNSUPPORTED-SCORE GUARDRAIL
        # Rule: A score >= 4.0 requires at least 1 Advanced item or 2 Intermediate items.
        guardrail_applied = False
        capped_overall = raw_overall

        if raw_overall >= 4.0 and adv_count == 0 and int_count < 2:
            capped_overall = 3.5
            guardrail_applied = True
        elif raw_overall >= 3.0 and adv_count == 0 and int_count == 0 and fund_count < 2:
            capped_overall = 2.5
            guardrail_applied = True

        final_score = round(min(5.0, max(1.0, capped_overall)), 2)

        # 3. Generate explainable audit rationale
        quotes_summary = "; ".join([f'"{e.quote[:60]}..."' for e in evidence_list[:2]])
        rationale = (
            f"Score of {final_score}/5 supported by {len(evidence_list)} evidence items "
            f"({adv_count} advanced, {int_count} intermediate, {fund_count} fundamental). "
            f"Demonstrated concepts: {quotes_summary}."
        )
        if guardrail_applied:
            rationale += " [Guardrail applied: score capped due to insufficient verified advanced evidence]."

        score_obj = CompetencyScore(
            technical_accuracy=round(accuracy, 2),
            architectural_depth=round(arch_depth, 2),
            practical_tradeoffs=round(tradeoffs, 2),
            communication_clarity=round(clarity, 2),
            overall_score=final_score,
            rationale=rationale,
        )

        return score_obj, guardrail_applied
