from types import SimpleNamespace
import numpy as np
import pytest
from multimodal.speech_to_text import EmptyAudioError, SpeechToText, SpeechToTextError, TranscriptSegment, TranscriptionResult
from multimodal.voice_analyzer import VoiceAnalyzer, VoiceObservation, VoiceObservationPresenter, VoicePresentationThresholds

class FakeModel:
    def transcribe(self, audio, **kwargs):
        assert kwargs["vad_filter"] and kwargs["word_timestamps"]
        return iter([SimpleNamespace(id=0,start=0,end=2,text=" Hello world",avg_logprob=-.1,no_speech_prob=.05,words=[])]), SimpleNamespace(language="en",language_probability=.93)
def result(text="one two", segments=(TranscriptSegment(0,0,2,"one two"),), reliability=.8): return TranscriptionResult(text,"en",.9,segments,reliability)
def test_stt_configuration_and_timestamps(tmp_path):
    p=tmp_path/"a.wav"; p.write_bytes(b"fake")
    out=SpeechToText(model=FakeModel()).transcribe(p)
    assert out.transcript=="Hello world" and out.language_probability==.93 and out.segments[0].start==0 and out.transcription_reliability is not None
    with pytest.raises(ValueError): SpeechToText(model_name="large")
def test_stt_missing_empty_and_failure(tmp_path):
    with pytest.raises(FileNotFoundError): SpeechToText(model=FakeModel()).transcribe(tmp_path/"none.wav")
    p=tmp_path/"empty.wav"; p.touch()
    with pytest.raises(EmptyAudioError): SpeechToText(model=FakeModel()).transcribe(p)
    p.write_bytes(b"x")
    with pytest.raises(SpeechToTextError): SpeechToText(model=SimpleNamespace(transcribe=lambda *_a,**_k: (_ for _ in ()).throw(RuntimeError()))).transcribe(p)
def test_no_speech_zero_values():
    o=VoiceAnalyzer().analyze(result("",(),None),samples=np.array([]),sample_rate=16000)
    assert o.speech_rate_wpm==o.filler_rate==o.volume_mean==o.volume_std==o.volume_stability==0 and not o.analysis_reliable
def test_wpm_pauses_and_microgaps():
    s=(TranscriptSegment(0,0,2,"one two three four"),TranscriptSegment(1,2.1,3.1,"five six"),TranscriptSegment(2,4,5,"seven eight"))
    o=VoiceAnalyzer(minimum_pause_seconds=.5).analyze(result("one two three four five six seven eight",s))
    assert o.speech_duration_seconds==4 and o.speech_rate_wpm==120 and o.pause_count==1 and o.longest_pause_seconds==pytest.approx(.9)
def test_fillers_volume_low_reliability():
    o=VoiceAnalyzer().analyze(result("Um, I like coding, um okay",reliability=.2),samples=np.array([0.,.5,-.5]),sample_rate=1)
    assert o.filler_count==3 and o.fillers.count("um")==2 and o.filler_rate==pytest.approx(.5) and 0<=o.volume_stability<=1 and not o.analysis_reliable
def test_volume_from_local_wav(tmp_path):
    import wave
    path=tmp_path/"voice.wav"
    with wave.open(str(path),"wb") as output:
        output.setnchannels(1); output.setsampwidth(2); output.setframerate(2); output.writeframes(np.array([0, 16384],dtype=np.int16).tobytes())
    o=VoiceAnalyzer().analyze(result(),audio_path=path)
    assert o.total_duration_seconds==2 and o.volume_mean==pytest.approx(.25)
def test_analysis_reliable_requires_stt_signal_and_speech():
    assert VoiceAnalyzer().analyze(result()).analysis_reliable
    assert not VoiceAnalyzer().analyze(result(reliability=None)).analysis_reliable


def observation(*, wpm=140, pauses=2, speech_duration=60, filler_rate=.02, filler_count=2, volume_stability=.8, reliability=.8):
    return VoiceObservation(60, speech_duration, wpm, pauses, 2, 1, 1, filler_count, filler_rate, (), .2, .1, volume_stability, reliability, True)


def test_dashboard_presentation_has_clear_normal_observations():
    dashboard = VoiceObservationPresenter().present(observation())
    assert dashboard.speaking_pace.label == "Moderate"
    assert dashboard.pauses.label == "Occasional"
    assert dashboard.filler_words.label == "Low"
    assert dashboard.volume.label == "Stable"
    assert dashboard.transcription.label == "Reliable"
    assert dashboard.baseline_change.available is False
    assert "moderate pace" in dashboard.overall


def test_dashboard_category_boundaries_are_descriptive_and_configurable():
    presenter = VoiceObservationPresenter(VoicePresentationThresholds(slow_max_wpm=100, moderate_max_wpm=160))
    assert presenter.present(observation(wpm=100, pauses=1, filler_rate=.03)).speaking_pace.label == "Slow"
    assert presenter.present(observation(wpm=160, pauses=4, filler_rate=.10)).speaking_pace.label == "Moderate"
    dashboard = presenter.present(observation(wpm=161, pauses=5, filler_rate=.11, volume_stability=.64))
    assert (dashboard.speaking_pace.label, dashboard.pauses.label, dashboard.filler_words.label, dashboard.volume.label) == ("Fast", "Frequent", "High", "Variable")


def test_dashboard_describes_only_own_meaningful_baseline_change():
    baseline = observation(wpm=120, filler_rate=.01, pauses=0, volume_stability=.9)
    dashboard = VoiceObservationPresenter().present(observation(wpm=160, filler_rate=.08, pauses=3, volume_stability=.7), baseline=baseline)
    assert dashboard.baseline_change.available
    assert "speaking pace" in dashboard.baseline_change.description.lower()
    assert "filler-word usage" in dashboard.baseline_change.description.lower()
    assert "faster than your earlier responses" in dashboard.speaking_pace.description


def test_dashboard_baseline_without_meaningful_change_is_neutral():
    dashboard = VoiceObservationPresenter().present(observation(), baseline=observation(wpm=145, filler_rate=.03, pauses=2))
    assert dashboard.baseline_change.available
    assert dashboard.baseline_change.description.startswith("No meaningful")


def test_dashboard_low_transcription_reliability_limits_summary():
    dashboard = VoiceObservationPresenter().present(observation(reliability=.2))
    assert dashboard.transcription.label == "Low Confidence"
    assert "repeating" in dashboard.transcription.description.lower()
    assert dashboard.overall.startswith("Transcription needs review")


def test_candidate_feedback_is_short_and_omits_raw_measurements():
    feedback = VoiceObservationPresenter().candidate_feedback(observation(wpm=190, filler_rate=.12, volume_stability=.4))
    assert "relatively fast" in feedback.observation
    assert "filler words" in feedback.observation
    assert "audio level varied" in feedback.observation
    assert feedback.suggestion == "Try slowing down slightly to make your delivery easier to follow."
    assert "190" not in feedback.observation and "%" not in feedback.observation


def test_candidate_feedback_uses_own_baseline_and_low_reliability_caveat():
    presenter = VoiceObservationPresenter()
    changed = presenter.candidate_feedback(observation(wpm=160), baseline=observation(wpm=120))
    assert changed.observation == "Your speaking pace was faster than your earlier responses."
    low_reliability = presenter.candidate_feedback(observation(wpm=190, reliability=.2))
    assert "could not be transcribed reliably" in low_reliability.observation
    assert "repeating" in low_reliability.suggestion.lower()
