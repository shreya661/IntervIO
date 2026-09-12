"""Combine independent voice and visual observations."""
from __future__ import annotations

from dataclasses import dataclass

from .voice_analyzer import VoiceObservation
from .visual_analyzer import VisualObservation


@dataclass(frozen=True)
class FusedObservation:
    """A multimodal observation with explicit availability flags."""

    voice: VoiceObservation | None
    visual: VisualObservation | None
    available_modalities: tuple[str, ...]
    voice_confidence: float | None = None
    visual_confidence: float | None = None
    confidence: float | None = None
    preferred_modality: str | None = None
    signals_disagree: bool = False


class MultimodalFusion:
    """Join observations without manufacturing a combined performance score."""

    def __init__(self, *, minimum_confidence: float = 0.5, disagreement_tolerance: float = 0.25) -> None:
        if not 0 <= minimum_confidence <= 1:
            raise ValueError("minimum_confidence must be between 0 and 1")
        if not 0 <= disagreement_tolerance <= 1:
            raise ValueError("disagreement_tolerance must be between 0 and 1")
        self.minimum_confidence = minimum_confidence
        self.disagreement_tolerance = disagreement_tolerance

    def combine(
        self,
        voice: VoiceObservation | None = None,
        visual: VisualObservation | None = None,
        *,
        voice_change: bool | None = None,
        visual_change: bool | None = None,
    ) -> FusedObservation:
        available = tuple(
            name for name, value in (("voice", voice), ("visual", visual)) if value is not None
        )
        voice_confidence = _voice_confidence(voice)
        visual_confidence = _visual_confidence(visual)
        signals_disagree = (
            voice_change is not None
            and visual_change is not None
            and voice_change != visual_change
        )
        confidence_values = [value for value in (voice_confidence, visual_confidence) if value is not None]
        confidence = min(confidence_values) if signals_disagree else max(confidence_values, default=None)
        if signals_disagree and confidence is not None:
            confidence *= 0.5
        preferred = self._preferred(
            voice_confidence, visual_confidence, confidence, signals_disagree
        )
        return FusedObservation(
            voice, visual, available, voice_confidence, visual_confidence,
            confidence, preferred, signals_disagree,
        )

    def _preferred(
        self,
        voice_confidence: float | None,
        visual_confidence: float | None,
        confidence: float | None,
        signals_disagree: bool,
    ) -> str | None:
        if confidence is None or confidence < self.minimum_confidence:
            if signals_disagree and voice_confidence is not None and voice_confidence >= self.minimum_confidence and (
                visual_confidence is None or voice_confidence > visual_confidence
            ):
                return "voice"
            return None
        if voice_confidence is None:
            return "visual"
        if visual_confidence is None:
            return "voice"
        if abs(voice_confidence - visual_confidence) <= self.disagreement_tolerance:
            return "voice_and_visual"
        return "voice" if voice_confidence > visual_confidence else "visual"


def _voice_confidence(voice: VoiceObservation | None) -> float | None:
    if voice is None:
        return None
    if voice.transcription_reliability is None or not voice.analysis_reliable:
        return 0.0
    return max(0.0, min(1.0, voice.transcription_reliability))


def _visual_confidence(visual: VisualObservation | None) -> float | None:
    if visual is None:
        return None
    if visual.confidence is not None:
        return max(0.0, min(1.0, visual.confidence))
    if not visual.frame_available:
        return 0.0
    if visual.lighting_quality is not None:
        return max(0.0, min(1.0, visual.lighting_quality))
    return 0.0