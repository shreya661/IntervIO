import numpy as np

from multimodal.multimodal_fusion import MultimodalFusion
from multimodal.support_engine import SupportEngine
from multimodal.visual_analyzer import VisualAnalyzer


def test_visual_analyzer_reports_brightness_and_motion():
    analyzer = VisualAnalyzer()
    first = analyzer.analyze(np.zeros((2, 3, 3), dtype=np.uint8))
    second = analyzer.analyze(np.full((2, 3, 3), 255, dtype=np.uint8))
    assert first.frame_available and first.brightness == 0
    assert second.brightness == 1 and second.motion == 1


def test_invalid_or_missing_camera_frame_is_unavailable():
    observation = VisualAnalyzer().analyze(None)
    assert not observation.frame_available
    assert observation.brightness is None


def test_fusion_and_support_keep_visual_feedback_neutral():
    visual = VisualAnalyzer().analyze(np.zeros((4, 4), dtype=np.uint8))
    fused = MultimodalFusion().combine(visual=visual)
    message = SupportEngine().generate(fused)
    assert fused.available_modalities == ("visual",)
    assert "dark" in message.observation


def test_fusion_prefers_reliable_voice_and_reduces_disagreement_confidence():
    from multimodal.voice_analyzer import VoiceObservation

    voice = VoiceObservation(2, 2, 120, 0, 0, 0, 0, 0, 0, (), .2, .1, .8, .9, True)
    dim = VisualAnalyzer().analyze(np.full((10, 10), 20, dtype=np.uint8), face_bbox=(2, 2, 6, 6))
    fused = MultimodalFusion().combine(voice, dim, voice_change=True, visual_change=False)
    assert fused.preferred_modality == "voice"
    assert fused.signals_disagree
    assert fused.confidence is not None and fused.confidence < fused.voice_confidence


def test_support_intervention_requires_incomplete_reliable_response():
    from multimodal.voice_analyzer import VoiceObservation

    voice = VoiceObservation(2, 2, 0, 0, 0, 0, 0, 0, 0, (), .2, .1, .8, .9, True)
    fused = MultimodalFusion().combine(voice=voice)
    message = SupportEngine().generate(fused, candidate_completed=False)
    assert message.intervention_given is True
    assert message.assessment_eligible is False
    assert "problem" in message.suggestion