"""Per-answer voice processing for a browser-based live interview.

The browser records one candidate answer and sends its bytes to the backend.
``LiveVoiceProcessor`` writes those bytes to an automatically removed temporary
file, transcribes them locally, and returns neutral delivery observations for
the agent controller. It does not select questions or make hiring decisions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
import logging
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable

import numpy as np

from .speech_to_text import EmptyAudioError, SpeechToText, SpeechToTextError, TranscriptionResult
from .voice_analyzer import CandidateVoiceFeedback, VoiceAnalyzer, VoiceDashboardPresentation, VoiceObservation, VoiceObservationPresenter
from .multimodal_fusion import FusedObservation, MultimodalFusion
from .support_engine import SupportEngine, SupportMessage

logger = logging.getLogger(__name__)
AudioDecoder = Callable[[Path], tuple[np.ndarray, int]]


class VoiceTurnStatus(StrEnum):
    """A backend-safe outcome for one recorded candidate answer."""

    ACCEPTED = "accepted"
    NO_SPEECH = "no_speech"
    REPEAT_REQUESTED = "repeat_requested"


@dataclass(frozen=True)
class LiveVoiceResult:
    """Structured handoff from Person 2's module to the interview controller."""

    status: VoiceTurnStatus
    message: str | None
    transcription: TranscriptionResult
    observation: VoiceObservation
    presentation: VoiceDashboardPresentation
    candidate_feedback: CandidateVoiceFeedback
    fused_observation: FusedObservation | None = None
    support_message: SupportMessage | None = None

    def to_payload(self) -> dict[str, object]:
        """Return JSON-compatible data for a future FastAPI answer endpoint."""
        return {
            "status": self.status.value,
            "message": self.message,
            "transcription": asdict(self.transcription),
            "voice_observation": asdict(self.observation),
            "voice_presentation": asdict(self.presentation),
            "candidate_voice_feedback": asdict(self.candidate_feedback),
            "fused_observation": asdict(self.fused_observation) if self.fused_observation else None,
            "support_message": asdict(self.support_message) if self.support_message else None,
        }


class LiveVoiceProcessor:
    """Process a single answer recorded by a live interview client.

    The processor supports common browser formats (for example WebM/Ogg) when
    faster-whisper's bundled decoder can decode them. Audio is not retained:
    byte uploads exist only in a temporary file for the duration of processing.
    """

    def __init__(
        self,
        *,
        speech_to_text: SpeechToText | None = None,
        voice_analyzer: VoiceAnalyzer | None = None,
        presenter: VoiceObservationPresenter | None = None,
        reliability_threshold: float = 0.50,
        audio_decoder: AudioDecoder | None = None,
    ) -> None:
        if not 0.0 <= reliability_threshold <= 1.0:
            raise ValueError("reliability_threshold must be between 0 and 1")
        self.speech_to_text = speech_to_text or SpeechToText()
        self.voice_analyzer = voice_analyzer or VoiceAnalyzer(
            reliability_threshold=reliability_threshold
        )
        self.reliability_threshold = reliability_threshold
        self.presenter = presenter or VoiceObservationPresenter()
        self.fusion = MultimodalFusion()
        self.support_engine = SupportEngine()
        self._audio_decoder = audio_decoder or _decode_with_faster_whisper

    def process_bytes(
        self,
        audio: bytes,
        *,
        filename: str = "answer.webm",
        language: str | None = None,
        baseline: VoiceObservation | None = None,
    ) -> LiveVoiceResult:
        """Process browser-uploaded audio without permanently storing it."""
        if not audio:
            raise EmptyAudioError("Uploaded audio is empty")
        suffix = Path(filename).suffix or ".webm"
        if len(suffix) > 12 or not suffix.startswith("."):
            raise ValueError("filename must have a normal audio filename suffix")
        # Windows locks a NamedTemporaryFile while it is open. Close it before
        # PyAV/faster-whisper opens the path, then remove it in all cases.
        temporary = NamedTemporaryFile(suffix=suffix, delete=False)
        temporary_path = Path(temporary.name)
        try:
            temporary.write(audio)
            temporary.flush()
            temporary.close()
            return self.process_file(temporary_path, language=language, baseline=baseline)
        finally:
            if not temporary.closed:
                temporary.close()
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass

    def process_file(
        self,
        audio_path: str | Path,
        *,
        language: str | None = None,
        baseline: VoiceObservation | None = None,
    ) -> LiveVoiceResult:
        """Process a local answer recording; callers own the supplied file."""
        path = Path(audio_path)
        transcription = self.speech_to_text.transcribe(path, language=language)
        samples, sample_rate = self._decode_optional(path)
        observation = self.voice_analyzer.analyze(
            transcription, samples=samples, sample_rate=sample_rate
        )
        status, message = self._turn_status(transcription, observation)
        presentation = self.presenter.present(observation, baseline=baseline)
        fused = self.fusion.combine(voice=observation)
        return LiveVoiceResult(
            status, message, transcription, observation, presentation,
            self.presenter.candidate_feedback(observation, baseline=baseline),
            fused,
            self.support_engine.generate(fused),
        )

    def _decode_optional(self, audio_path: Path) -> tuple[np.ndarray | None, int | None]:
        try:
            return self._audio_decoder(audio_path)
        except Exception as exc:  # STT can still provide useful timestamp metrics.
            logger.warning("Could not decode %s for volume analysis: %s", audio_path.name, exc)
            return None, None

    def _turn_status(
        self, transcription: TranscriptionResult, observation: VoiceObservation
    ) -> tuple[VoiceTurnStatus, str | None]:
        if not transcription.transcript.strip():
            return VoiceTurnStatus.NO_SPEECH, "No speech was detected. Please repeat your answer."
        reliability = transcription.transcription_reliability
        if reliability is None or reliability < self.reliability_threshold:
            return VoiceTurnStatus.REPEAT_REQUESTED, (
                "I could not transcribe that reliably. Please repeat your answer."
            )
        if not observation.analysis_reliable:
            return VoiceTurnStatus.REPEAT_REQUESTED, (
                "I could not analyze that answer reliably. Please repeat your answer."
            )
        return VoiceTurnStatus.ACCEPTED, None


def _decode_with_faster_whisper(audio_path: Path) -> tuple[np.ndarray, int]:
    """Decode local audio with faster-whisper's installed PyAV-based decoder."""
    from faster_whisper.audio import decode_audio

    sample_rate = 16_000
    return np.asarray(decode_audio(str(audio_path), sampling_rate=sample_rate)), sample_rate
