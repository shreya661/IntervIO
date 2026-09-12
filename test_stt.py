from pathlib import Path

import pytest

from multimodal.speech_to_text import SpeechToText


def test_stt_demo_audio() -> None:
	audio_files = tuple(
		path for suffix in ("*.ogg", "*.wav", "*.mp3", "*.webm", "*.m4a")
		for path in Path("demo").glob(suffix)
	) if Path("demo").is_dir() else ()
	if not audio_files:
		pytest.skip("No demo audio fixture is present in the repository")
	result = SpeechToText().transcribe(audio_files[0])
	assert result.transcript is not None