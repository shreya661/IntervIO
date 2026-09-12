"""Observable voice-delivery measurements, not psychological or hiring scores."""
from __future__ import annotations
from dataclasses import dataclass
import re
from pathlib import Path
from typing import Iterable, Sequence
import wave
import numpy as np
from .speech_to_text import TranscriptSegment, TranscriptionResult

DEFAULT_FILLERS = ("um", "uh", "erm", "ah", "like", "you know")
_WORD = re.compile(r"[\w]+(?:['’][\w]+)?", re.UNICODE)

@dataclass(frozen=True)
class VoiceObservation:
    """Candidate-specific delivery signals for comparison to that candidate's baseline."""
    total_duration_seconds: float; speech_duration_seconds: float; speech_rate_wpm: float
    pause_count: int; total_pause_duration_seconds: float; average_pause_duration_seconds: float; longest_pause_seconds: float
    filler_count: int; filler_rate: float; fillers: tuple[str, ...]
    volume_mean: float | None; volume_std: float | None; volume_stability: float | None
    transcription_reliability: float | None; analysis_reliable: bool
    pitch_mean_hz: float | None = None; pitch_min_hz: float | None = None; pitch_max_hz: float | None = None
    pitch_std_hz: float | None = None; pitch_variation: float | None = None


@dataclass(frozen=True)
class DeliveryPresentation:
    """One dashboard-ready, descriptive delivery observation."""

    label: str
    description: str


@dataclass(frozen=True)
class BaselineChange:
    """A comparison to the same candidate's earlier observation only."""

    available: bool
    description: str | None = None


@dataclass(frozen=True)
class VoiceDashboardPresentation:
    """Human-readable presentation while retaining ``VoiceObservation`` as audit data."""

    speaking_pace: DeliveryPresentation
    pauses: DeliveryPresentation
    filler_words: DeliveryPresentation
    volume: DeliveryPresentation
    transcription: DeliveryPresentation
    baseline_change: BaselineChange
    overall: str


@dataclass(frozen=True)
class CandidateVoiceFeedback:
    """Short, candidate-facing delivery feedback with no audit metrics."""

    observation: str
    suggestion: str | None = None


@dataclass(frozen=True)
class VoicePresentationThresholds:
    """Configurable descriptive categories, not validated psychological thresholds."""

    slow_max_wpm: float = 110.0
    moderate_max_wpm: float = 170.0
    minimal_pause_rate_per_minute: float = 1.0
    occasional_pause_rate_per_minute: float = 4.0
    low_filler_rate: float = 0.03
    moderate_filler_rate: float = 0.10
    stable_volume_minimum: float = 0.65
    reliability_threshold: float = 0.50
    low_confidence_threshold: float = 0.35
    baseline_pace_change_ratio: float = 0.15
    baseline_filler_rate_change: float = 0.03
    baseline_pause_rate_change: float = 1.0
    baseline_volume_stability_change: float = 0.15

    def __post_init__(self) -> None:
        if not 0 <= self.slow_max_wpm < self.moderate_max_wpm:
            raise ValueError("pace thresholds must be non-negative and ascending")
        if not 0 <= self.minimal_pause_rate_per_minute < self.occasional_pause_rate_per_minute:
            raise ValueError("pause thresholds must be non-negative and ascending")
        if not 0 <= self.low_filler_rate < self.moderate_filler_rate <= 1:
            raise ValueError("filler thresholds must be between zero and one and ascending")
        if not 0 <= self.stable_volume_minimum <= 1:
            raise ValueError("stable_volume_minimum must be between zero and one")
        if not 0 <= self.low_confidence_threshold <= self.reliability_threshold <= 1:
            raise ValueError("reliability thresholds must be between zero and one and ascending")


class VoiceObservationPresenter:
    """Turn neutral measurements into concise dashboard text.

    This class makes no psychological, competency, or hiring inference. Its
    baseline comparisons are always between a candidate's current and earlier
    ``VoiceObservation`` values.
    """

    def __init__(self, thresholds: VoicePresentationThresholds | None = None) -> None:
        self.thresholds = thresholds or VoicePresentationThresholds()

    def present(self, observation: VoiceObservation, *, baseline: VoiceObservation | None = None) -> VoiceDashboardPresentation:
        """Create dashboard categories from one observation and optional own baseline."""
        pace = self._pace(observation)
        pauses = self._pauses(observation)
        fillers = self._fillers(observation)
        volume = self._volume(observation)
        transcription = self._transcription(observation)
        baseline_change = self._baseline_change(observation, baseline)
        if baseline_change.available and baseline_change.description:
            pace = self._add_pace_baseline_note(pace, observation, baseline)
        return VoiceDashboardPresentation(
            speaking_pace=pace,
            pauses=pauses,
            filler_words=fillers,
            volume=volume,
            transcription=transcription,
            baseline_change=baseline_change,
            overall=self._overall(pace, pauses, fillers, volume, transcription),
        )

    def candidate_feedback(self, observation: VoiceObservation, *, baseline: VoiceObservation | None = None) -> CandidateVoiceFeedback:
        """Create concise, neutral delivery feedback without exposing raw metrics.

        The result intentionally omits normal signals to avoid repetitive
        feedback. Low transcription reliability takes precedence because other
        delivery observations should not be stated strongly in that case.
        """
        transcription = self._transcription(observation)
        if transcription.label != "Reliable":
            return CandidateVoiceFeedback(
                "Some parts of the response could not be transcribed reliably.",
                "Repeating the answer may improve the transcription result.",
            )

        statements: list[str] = []
        pace_changed = baseline is not None and _relative_change(
            observation.speech_rate_wpm, baseline.speech_rate_wpm
        ) >= self.thresholds.baseline_pace_change_ratio
        if pace_changed:
            direction = "faster" if observation.speech_rate_wpm > baseline.speech_rate_wpm else "slower"
            statements.append(f"Your speaking pace was {direction} than your earlier responses.")
        elif self._pace(observation).label == "Fast":
            statements.append("Your speaking pace was relatively fast.")
        elif self._pace(observation).label == "Slow":
            statements.append("Your speaking pace was relatively slow.")

        if self._fillers(observation).label == "High":
            statements.append("You used filler words fairly often during this response.")
        if self._volume(observation).label == "Variable":
            statements.append("Your audio level varied during the response.")
        if self._pauses(observation).label == "Frequent":
            statements.append("You took frequent meaningful pauses during the response.")

        if not statements:
            return CandidateVoiceFeedback("No notable delivery changes were observed in this response.")
        suggestion = self._candidate_suggestion(observation, baseline, pace_changed)
        return CandidateVoiceFeedback(" ".join(statements), suggestion)

    def _candidate_suggestion(self, observation: VoiceObservation, baseline: VoiceObservation | None, pace_changed: bool) -> str | None:
        pace = self._pace(observation).label
        if pace == "Fast" or (pace_changed and baseline is not None and observation.speech_rate_wpm > baseline.speech_rate_wpm):
            return "Try slowing down slightly to make your delivery easier to follow."
        if pace == "Slow" or (pace_changed and baseline is not None and observation.speech_rate_wpm < baseline.speech_rate_wpm):
            return "Try using a slightly more even pace in your next response."
        if self._volume(observation).label == "Variable":
            return "Try maintaining a consistent distance from the microphone."
        if self._fillers(observation).label == "High":
            return "Try taking a brief pause before continuing instead of using filler words."
        if self._pauses(observation).label == "Frequent":
            return "Try grouping your response into a few complete points."
        return None

    def _pace(self, observation: VoiceObservation) -> DeliveryPresentation:
        wpm = observation.speech_rate_wpm
        if wpm <= self.thresholds.slow_max_wpm:
            label = "Slow"
        elif wpm <= self.thresholds.moderate_max_wpm:
            label = "Moderate"
        else:
            label = "Fast"
        return DeliveryPresentation(label, f"Measured speaking pace was {wpm:.0f} words per minute.")

    def _pauses(self, observation: VoiceObservation) -> DeliveryPresentation:
        rate = _per_minute(observation.pause_count, observation.speech_duration_seconds)
        if rate <= self.thresholds.minimal_pause_rate_per_minute:
            label = "Minimal"
        elif rate <= self.thresholds.occasional_pause_rate_per_minute:
            label = "Occasional"
        else:
            label = "Frequent"
        return DeliveryPresentation(
            label,
            f"{observation.pause_count} meaningful pause(s), about {rate:.1f} per minute of speech.",
        )

    def _fillers(self, observation: VoiceObservation) -> DeliveryPresentation:
        rate = observation.filler_rate
        if rate <= self.thresholds.low_filler_rate:
            label = "Low"
        elif rate <= self.thresholds.moderate_filler_rate:
            label = "Moderate"
        else:
            label = "High"
        return DeliveryPresentation(label, f"{observation.filler_count} filler word(s), {rate:.0%} of spoken words.")

    def _volume(self, observation: VoiceObservation) -> DeliveryPresentation:
        if observation.volume_stability is None:
            return DeliveryPresentation("Unavailable", "Volume data was not available for this response.")
        label = "Stable" if observation.volume_stability >= self.thresholds.stable_volume_minimum else "Variable"
        return DeliveryPresentation(label, f"Audio volume consistency measured {observation.volume_stability:.0%}.")

    def _transcription(self, observation: VoiceObservation) -> DeliveryPresentation:
        reliability = observation.transcription_reliability
        if reliability is None or reliability < self.thresholds.low_confidence_threshold:
            return DeliveryPresentation("Low Confidence", "Transcription quality was low; repeating the answer may improve the result.")
        if reliability < self.thresholds.reliability_threshold:
            return DeliveryPresentation("Needs Review", "Transcription quality needs review; repeating the answer may improve the result.")
        return DeliveryPresentation("Reliable", "Transcription had a usable decoder-signal reliability estimate.")

    def _baseline_change(self, current: VoiceObservation, baseline: VoiceObservation | None) -> BaselineChange:
        if baseline is None:
            return BaselineChange(False)
        changes: list[str] = []
        if _relative_change(current.speech_rate_wpm, baseline.speech_rate_wpm) >= self.thresholds.baseline_pace_change_ratio:
            changes.append("speaking pace")
        if abs(current.filler_rate - baseline.filler_rate) >= self.thresholds.baseline_filler_rate_change:
            changes.append("filler-word usage")
        if abs(_per_minute(current.pause_count, current.speech_duration_seconds) - _per_minute(baseline.pause_count, baseline.speech_duration_seconds)) >= self.thresholds.baseline_pause_rate_change:
            changes.append("pause frequency")
        if current.volume_stability is not None and baseline.volume_stability is not None and abs(current.volume_stability - baseline.volume_stability) >= self.thresholds.baseline_volume_stability_change:
            changes.append("volume consistency")
        if not changes:
            return BaselineChange(True, "No meaningful delivery changes were measured compared with earlier responses.")
        return BaselineChange(True, f"{_join_items(changes).capitalize()} changed compared with your earlier responses.")

    def _add_pace_baseline_note(self, pace: DeliveryPresentation, current: VoiceObservation, baseline: VoiceObservation | None) -> DeliveryPresentation:
        if baseline is None or _relative_change(current.speech_rate_wpm, baseline.speech_rate_wpm) < self.thresholds.baseline_pace_change_ratio:
            return pace
        direction = "faster" if current.speech_rate_wpm > baseline.speech_rate_wpm else "slower"
        return DeliveryPresentation(pace.label, f"{pace.description} This was {direction} than your earlier responses.")

    @staticmethod
    def _overall(pace: DeliveryPresentation, pauses: DeliveryPresentation, fillers: DeliveryPresentation, volume: DeliveryPresentation, transcription: DeliveryPresentation) -> str:
        if transcription.label != "Reliable":
            return "Transcription needs review; repeat the response to confirm these observable delivery measurements."
        volume_text = "unavailable volume data" if volume.label == "Unavailable" else f"{volume.label.lower()} audio volume"
        return f"This response had {pace.label.lower()} pace, {pauses.label.lower()} pauses, {fillers.label.lower()} filler-word usage, and {volume_text}."

class VoiceAnalyzer:
    """Measure timestamps, lexical fillers, and supplied normalized audio samples.

    Filler rate is fillers divided by spoken words. Volume is mean/std absolute
    sample amplitude; stability is ``1 - std/mean`` clipped to 0..1.
    """
    def __init__(self, *, minimum_pause_seconds: float = .35, fillers: Sequence[str] = DEFAULT_FILLERS, reliability_threshold: float = .5) -> None:
        if minimum_pause_seconds < 0: raise ValueError("minimum_pause_seconds must be non-negative")
        if not 0 <= reliability_threshold <= 1: raise ValueError("reliability_threshold must be between 0 and 1")
        self.fillers = tuple(x.strip().lower() for x in fillers if x.strip())
        if not self.fillers: raise ValueError("fillers must not be empty")
        self.minimum_pause_seconds, self.reliability_threshold = minimum_pause_seconds, reliability_threshold

    def analyze(self, transcription: TranscriptionResult, *, audio_path: str | Path | None = None, samples: np.ndarray | Sequence[float] | None = None, sample_rate: int | None = None) -> VoiceObservation:
        """Analyze STT output and optional local WAV audio or decoded samples."""
        if audio_path is not None and samples is not None:
            raise ValueError("provide either audio_path or samples, not both")
        if audio_path is not None:
            samples, sample_rate = _read_wav(audio_path)
        speech, pauses = _speech_and_pauses(transcription.segments, self.minimum_pause_seconds)
        words, matches = _tokens(transcription.transcript), _find_fillers(transcription.transcript, self.fillers)
        mean, std, stability = _volume(samples)
        pitch_mean, pitch_min, pitch_max, pitch_std, pitch_variation = _pitch(samples, sample_rate)
        sample_duration = len(samples) / sample_rate if samples is not None and sample_rate and sample_rate > 0 else 0.
        total = max(max((s.end for s in transcription.segments), default=0.), sample_duration)
        reliability = transcription.transcription_reliability
        return VoiceObservation(total, speech, len(words)*60/speech if speech else 0., len(pauses), sum(pauses), sum(pauses)/len(pauses) if pauses else 0., max(pauses, default=0.), len(matches), len(matches)/len(words) if words else 0., tuple(matches), mean, std, stability, reliability, bool(words and speech and reliability is not None and reliability >= self.reliability_threshold), pitch_mean, pitch_min, pitch_max, pitch_std, pitch_variation)

def _speech_and_pauses(segments: Iterable[TranscriptSegment], threshold: float) -> tuple[float, list[float]]:
    merged: list[list[float]] = []; pauses: list[float] = []
    for start, end in sorted((s.start, max(s.start, s.end)) for s in segments if s.end > s.start):
        if not merged: merged.append([start, end]); continue
        if start <= merged[-1][1]: merged[-1][1] = max(merged[-1][1], end); continue
        gap = start - merged[-1][1]
        if gap >= threshold: pauses.append(gap)
        merged.append([start, end])
    return sum(end-start for start, end in merged), pauses
def _tokens(text: str) -> list[str]: return _WORD.findall(text.lower())
def _per_minute(count: int, duration_seconds: float) -> float:
    return count * 60 / duration_seconds if duration_seconds > 0 else 0.
def _relative_change(current: float, baseline: float) -> float:
    return abs(current - baseline) / max(abs(baseline), 1.)
def _join_items(items: Sequence[str]) -> str:
    if len(items) == 1: return items[0]
    if len(items) == 2: return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"
def _find_fillers(text: str, fillers: Sequence[str]) -> list[str]:
    normalized = " ".join(_tokens(text)); found: list[str] = []
    for filler in fillers:
        phrase = " ".join(_tokens(filler))
        if phrase: found.extend([filler] * len(re.findall(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", normalized)))
    return found
def _volume(samples: np.ndarray | Sequence[float] | None) -> tuple[float | None, float | None, float | None]:
    if samples is None: return None, None, None
    values = np.abs(np.asarray(samples, dtype=float).reshape(-1))
    if not values.size: return 0., 0., 0.
    mean, std = float(values.mean()), float(values.std())
    return mean, std, max(0., min(1., 1 - std/(mean + 1e-12))) if mean else 0.

def _pitch(samples: np.ndarray | Sequence[float] | None, sample_rate: int | None) -> tuple[float | None, float | None, float | None, float | None, float | None]:
    """Estimate voiced F0 with bounded autocorrelation; no emotion inference."""
    if samples is None or not sample_rate or sample_rate < 1_000: return None, None, None, None, None
    signal = np.asarray(samples, dtype=float).reshape(-1)
    frame, hop = int(sample_rate * .04), int(sample_rate * .02)
    if len(signal) < frame: return None, None, None, None, None
    low, high = max(1, int(sample_rate / 350)), int(sample_rate / 75)
    values: list[float] = []
    for start in range(0, len(signal) - frame + 1, hop):
        chunk = signal[start:start + frame] - signal[start:start + frame].mean()
        if np.sqrt(np.mean(chunk * chunk)) < .01: continue
        corr = np.correlate(chunk, chunk, mode="full")[frame - 1:]
        if high >= len(corr): continue
        lag = low + int(np.argmax(corr[low:high + 1]))
        if corr[lag] / (corr[0] + 1e-12) >= .25: values.append(sample_rate / lag)
    if not values: return None, None, None, None, None
    pitches = np.asarray(values)
    mean, std = float(pitches.mean()), float(pitches.std())
    return mean, float(pitches.min()), float(pitches.max()), std, std / mean if mean else 0.

def _read_wav(path_value: str | Path) -> tuple[np.ndarray, int]:
    """Read PCM WAV locally; callers may pass decoded samples for other formats."""
    path = Path(path_value)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Audio file does not exist: {path}")
    try:
        with wave.open(str(path), "rb") as source:
            channels, width, rate = source.getnchannels(), source.getsampwidth(), source.getframerate()
            raw = source.readframes(source.getnframes())
    except (OSError, wave.Error) as exc:
        raise ValueError("Volume path input must be PCM WAV; pass decoded samples for another format") from exc
    if width not in (1, 2, 4):
        raise ValueError("Unsupported WAV sample width")
    values = np.frombuffer(raw, dtype={1: np.uint8, 2: np.int16, 4: np.int32}[width]).astype(float)
    values = (values - 128.) / 128. if width == 1 else values / (2 ** (width * 8 - 1))
    return (values.reshape(-1, channels).mean(axis=1) if channels else values), rate
