"""Multimodal interview-practice components.

The package keeps audio processing, visual observations, personal baselines,
fusion, and candidate support as separate layers so each can be tested or
replaced independently.
"""
<<<<<<< HEAD
=======

>>>>>>> 6c367e4ed213302f79d78ca86b61c661a65824f4
from .speech_to_text import SpeechToText
from .live_voice import LiveVoiceProcessor, LiveVoiceResult, VoiceTurnStatus
from .visual_analyzer import VisualAnalyzer, VisualObservation
from .baseline import BaselineProfile, BaselineStore
from .multimodal_fusion import FusedObservation, MultimodalFusion
from .support_engine import SupportEngine, SupportMessage
from .resume_analyzer import ResumeAnalyzer, ResumeAnalysisError, ResumeProfile
from .gemini_assistant import GeminiAnswerAnalysis, GeminiAssistant

__all__ = [
    "SpeechToText",
    "SpeechToTextError",
    "TranscriptionResult",
    "transcribe_audio",
    "LiveVoiceProcessor",
    "LiveVoiceResult",
    "VoiceTurnStatus",
    "VisualAnalyzer",
    "VisualObservation",
    "BaselineProfile",
    "BaselineStore",
    "FusedObservation",
    "MultimodalFusion",
    "SupportEngine",
    "SupportMessage",
    "ResumeAnalyzer",
    "ResumeAnalysisError",
    "ResumeProfile",
    "GeminiAnswerAnalysis",
    "GeminiAssistant",
]
