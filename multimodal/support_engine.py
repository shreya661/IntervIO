"""Candidate-facing support messages based on observable signals."""
from __future__ import annotations

from dataclasses import dataclass

from .multimodal_fusion import FusedObservation


@dataclass(frozen=True)
class SupportMessage:
    """A short neutral observation and an optional actionable suggestion."""

    observation: str
    suggestion: str | None = None
    intervention_given: bool = False
    assessment_eligible: bool = True


class SupportEngine:
    """Produce supportive guidance without psychological or hiring claims."""

    def generate(
        self,
        fused: FusedObservation,
        *,
        candidate_completed: bool = True,
        intervention_given: bool = False,
    ) -> SupportMessage:
        """Create support without treating coaching as assessment evidence.

        Intervention is offered only for a reliable voice response that is not
        complete. A caller must explicitly pass ``candidate_completed=False``;
        this prevents accidental coaching during final assessment.
        """
        if intervention_given:
            return SupportMessage("Support was already provided for this response.", intervention_given=True)
        if fused.voice is not None and not fused.voice.analysis_reliable:
            return SupportMessage(
                "Some parts of the response could not be analyzed reliably.",
                "Repeating the answer may improve the analysis result.",
                assessment_eligible=False,
            )
        if fused.visual is not None and fused.visual.brightness is not None:
            if fused.visual.brightness < 0.15:
                return SupportMessage(
                    "The camera image was quite dark.",
                    "Try moving to a brighter, evenly lit space.",
                )
        if (
            not candidate_completed
            and fused.voice is not None
            and fused.voice.analysis_reliable
            and fused.voice.speech_duration_seconds > 0
            and fused.voice.speech_rate_wpm == 0
        ):
            return SupportMessage(
                "Take a moment before continuing your answer.",
                "You can structure your answer as problem, approach, and result.",
                intervention_given=True,
                assessment_eligible=False,
            )
        return SupportMessage("No notable delivery changes were observed in this response.")