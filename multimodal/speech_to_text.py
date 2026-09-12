"""Local speech-to-text helpers built on faster-whisper.

``language_probability`` identifies the language; it is not transcription
accuracy. ``transcription_reliability`` is an uncalibrated decoder-signal
heuristic, never a correctness claim.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
from typing import Any, Callable, Mapping

AudioPath = str | Path
ModelFactory = Callable[..., Any]


class SpeechToTextError(RuntimeError):
    """Raised when local transcription cannot complete."""


class EmptyAudioError(SpeechToTextError):
    """Raised for a zero-byte audio file."""


@dataclass(frozen=True)
class WordTimestamp:
    start: float | None
    end: float | None
    word: str
    probability: float | None = None


@dataclass(frozen=True)
class TranscriptSegment:
    id: int
    start: float
    end: float
    text: str
    words: tuple[WordTimestamp, ...] = ()
    avg_logprob: float | None = None
    no_speech_prob: float | None = None
    compression_ratio: float | None = None


@dataclass(frozen=True)
class TranscriptionResult:
    """Transcription plus raw timing and a limited STT reliability signal.

    Reliability is duration-weighted ``exp(avg_logprob) * (1-no_speech_prob)``.
    It is only available if faster-whisper exposes both decoder signals and is
    neither calibrated confidence nor an estimate of transcript accuracy.
    """
    transcript: str
    language: str | None
    language_probability: float | None
    segments: tuple[TranscriptSegment, ...]
    transcription_reliability: float | None
    reliability_method: str = field(default="duration-weighted decoder signal heuristic; not transcription accuracy")

    @property
    def confidence(self) -> float | None:
        """Compatibility alias for the explicitly named reliability signal."""
        return self.transcription_reliability

    @property
    def confidence_method(self) -> str:
        return self.reliability_method


class SpeechToText:
    """Lazily-loaded local faster-whisper client (small/CPU/INT8 by default)."""
    def __init__(self, model_name: str = "small", *, device: str = "cpu", compute_type: str = "int8", model: Any | None = None, model_factory: ModelFactory | None = None) -> None:
        if model_name not in {"base", "small", "medium"}:
            raise ValueError("model_name must be one of: base, small, medium")
        if device not in {"cpu", "cuda"}:
            raise ValueError("device must be 'cpu' or 'cuda'")
        if not compute_type.strip():
            raise ValueError("compute_type must not be empty")
        self.model_name, self.device, self.compute_type = model_name, device, compute_type
        self._model, self._model_factory = model, model_factory

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            if self._model_factory is None:
                from faster_whisper import WhisperModel
                self._model_factory = WhisperModel
            self._model = self._model_factory(self.model_name, device=self.device, compute_type=self.compute_type)
            return self._model
        except Exception as exc:
            raise SpeechToTextError(f"Unable to load Whisper model {self.model_name!r}: {exc}") from exc

    def transcribe(self, audio: AudioPath, *, language: str | None = None, beam_size: int = 5, vad_filter: bool = True, word_timestamps: bool = True) -> TranscriptionResult:
        """Transcribe a local file, with VAD and word timestamps enabled by default."""
        path = Path(audio)
        if not path.exists(): raise FileNotFoundError(f"Audio file does not exist: {path}")
        if not path.is_file(): raise ValueError(f"Audio path is not a file: {path}")
        if path.stat().st_size == 0: raise EmptyAudioError(f"Audio file is empty: {path}")
        if beam_size < 1: raise ValueError("beam_size must be at least 1")
        if language is not None and not language.strip(): raise ValueError("language must be a non-empty code or None")
        try:
            raw, info = self._load_model().transcribe(str(path), language=language, beam_size=beam_size, vad_filter=vad_filter, word_timestamps=word_timestamps)
            segments = tuple(self._normalize(segment, i) for i, segment in enumerate(raw))
        except SpeechToTextError: raise
        except Exception as exc: raise SpeechToTextError(f"Transcription failed for {path}: {exc}") from exc
        return TranscriptionResult(" ".join(s.text.strip() for s in segments if s.text.strip()).strip(), _string(_get(info, "language")), _bounded(_get(info, "language_probability")), segments, self._reliability(segments))

    @staticmethod
    def _normalize(item: Any, index: int) -> TranscriptSegment:
        words = tuple(WordTimestamp(_number(_get(w, "start")), _number(_get(w, "end")), str(_get(w, "word", "")), _bounded(_get(w, "probability"))) for w in (_get(item, "words", ()) or ()))
        return TranscriptSegment(int(_get(item, "id", index)), _nonnegative(_get(item, "start", 0)), _nonnegative(_get(item, "end", 0)), str(_get(item, "text", "")), words, _number(_get(item, "avg_logprob")), _bounded(_get(item, "no_speech_prob")), _number(_get(item, "compression_ratio")))

    @staticmethod
    def _reliability(segments: tuple[TranscriptSegment, ...]) -> float | None:
        scores = [(max(0., min(1., math.exp(min(0., s.avg_logprob)) * (1 - s.no_speech_prob))), max(0., s.end - s.start)) for s in segments if s.avg_logprob is not None and s.no_speech_prob is not None]
        if not scores: return None
        duration = sum(weight for _, weight in scores)
        return sum(score * weight for score, weight in scores) / duration if duration else sum(score for score, _ in scores) / len(scores)


def _get(obj: Any, name: str, default: Any = None) -> Any:
    return obj.get(name, default) if isinstance(obj, Mapping) else getattr(obj, name, default)
def _number(value: Any) -> float | None:
    try:
        number = float(value); return number if math.isfinite(number) else None
    except (TypeError, ValueError): return None
def _nonnegative(value: Any) -> float: return max(0., _number(value) or 0.)
def _bounded(value: Any) -> float | None:
    number = _number(value); return None if number is None else max(0., min(1., number))
def _string(value: Any) -> str | None: return str(value) if value is not None else None
def transcribe_audio(audio: AudioPath, **kwargs: Any) -> TranscriptionResult:
    """Transcribe via the default small CPU/INT8 model."""
    return SpeechToText().transcribe(audio, **kwargs)
