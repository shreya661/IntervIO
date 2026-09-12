from pathlib import Path

import numpy as np
import pytest

from multimodal.live_voice import LiveVoiceProcessor, VoiceTurnStatus
from multimodal.speech_to_text import EmptyAudioError, TranscriptSegment, TranscriptionResult
from multimodal.voice_analyzer import VoiceObservation


class FakeSpeechToText:
    def __init__(self, result: TranscriptionResult) -> None:
        self.result = result
        self.paths: list[Path] = []

    def transcribe(self, path: Path, *, language: str | None = None) -> TranscriptionResult:
        self.paths.append(Path(path))
        return self.result


class FakeAnalyzer:
    def __init__(self, reliable: bool = True) -> None:
        self.reliable = reliable

    def analyze(self, transcription, *, samples, sample_rate) -> VoiceObservation:
        return VoiceObservation(2, 2, 60, 0, 0, 0, 0, 0, 0, (), .2, .1, .5,
                                transcription.transcription_reliability, self.reliable)


def transcript(text: str = "A clear answer", reliability: float | None = .8) -> TranscriptionResult:
    segments = (TranscriptSegment(0, 0, 2, text),) if text else ()
    return TranscriptionResult(text, "en", .9, segments, reliability)


def test_processes_browser_bytes_without_persistent_audio_file():
    stt = FakeSpeechToText(transcript())
    processor = LiveVoiceProcessor(speech_to_text=stt, voice_analyzer=FakeAnalyzer(),
                                   audio_decoder=lambda _: (np.array([.2]), 16000))
    result = processor.process_bytes(b"browser recording", filename="answer.webm")
    assert result.status is VoiceTurnStatus.ACCEPTED
    assert result.observation.volume_mean == .2
    assert len(stt.paths) == 1 and not stt.paths[0].exists()
    assert result.to_payload()["status"] == "accepted"
    assert result.to_payload()["voice_presentation"]["speaking_pace"]["label"] == "Slow"


def test_requests_repeat_for_no_speech_or_low_reliability(tmp_path):
    path = tmp_path / "answer.ogg"; path.write_bytes(b"recording")
    no_speech = LiveVoiceProcessor(speech_to_text=FakeSpeechToText(transcript("", .9)), voice_analyzer=FakeAnalyzer())
    low_reliability = LiveVoiceProcessor(speech_to_text=FakeSpeechToText(transcript(reliability=.2)), voice_analyzer=FakeAnalyzer())
    assert no_speech.process_file(path).status is VoiceTurnStatus.NO_SPEECH
    assert low_reliability.process_file(path).status is VoiceTurnStatus.REPEAT_REQUESTED


def test_decode_failure_keeps_timestamp_based_analysis(tmp_path):
    path = tmp_path / "answer.webm"; path.write_bytes(b"recording")
    processor = LiveVoiceProcessor(speech_to_text=FakeSpeechToText(transcript()), voice_analyzer=FakeAnalyzer(),
                                   audio_decoder=lambda _: (_ for _ in ()).throw(ValueError("unsupported")))
    result = processor.process_file(path)
    assert result.status is VoiceTurnStatus.ACCEPTED


def test_rejects_empty_upload_and_invalid_configuration():
    with pytest.raises(EmptyAudioError):
        LiveVoiceProcessor(speech_to_text=FakeSpeechToText(transcript()), voice_analyzer=FakeAnalyzer()).process_bytes(b"")
    with pytest.raises(ValueError):
        LiveVoiceProcessor(reliability_threshold=1.1)
