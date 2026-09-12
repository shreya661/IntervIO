# Person 2 Multimodal Interview Coach

This project is organized into independent multimodal layers:

```text
multimodal/
├── speech_to_text.py       # local Whisper transcription
├── voice_analyzer.py       # observable audio delivery measurements
├── visual_analyzer.py      # observable camera-frame measurements
├── baseline.py             # per-candidate comparison state
├── multimodal_fusion.py    # explicit voice/visual composition
└── support_engine.py       # neutral candidate-facing guidance
```

The browser demo also supports:

- PDF/DOCX resume upload and structured extraction of skills, education,
	projects, experience, technologies, and achievements.
- Technology and non-technology practice-domain selection.
- Resume and candidate context supplied to an agent that chooses each question on demand.
- Optional microphone and camera capture.
- A final coaching record with strengths, knowledge gaps, recommendations, and
	graph-ready voice delivery measurements.

`live_voice.py` and `interview_coach.py` remain compatibility entry points for
the existing browser demo. Camera input is optional; audio processing still
works when no frame is supplied. The system reports observable signals only and
does not infer emotion, personality, or hiring suitability.

## Run

Activate the virtual environment, install dependencies, and run the demo:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn voice_demo:app --reload
```

Open `http://127.0.0.1:8000`. The setup screen lets you upload a PDF or DOCX,
choose a domain, enable the camera optionally, and start practice. Camera and
voice observations are used only as observable coaching signals; they do not
infer emotion, personality, honesty, or hiring suitability.

## Optional Gemini reasoning

Gemini is used for resume understanding, answer analysis, adaptive reasoning,
and question wording. WPM, pauses, pitch, volume, and other voice metrics stay
deterministic in Python. Configure Gemini in PowerShell before starting the app:

```powershell
$env:GEMINI_API_KEY="your-key-here"
python -m uvicorn voice_demo:app --reload
```

The key is read from the environment and is never sent to the browser. If the
variable is absent or Gemini returns invalid data, the deterministic coach
continues automatically.

The practice UI displays a focus reminder and may record browser visibility or
window-focus changes as technical telemetry. Browsers do not expose reliable
information about which other tab or application is open, and camera gaze or
head orientation cannot prove copying or dishonesty. These signals are never
used to mark an answer wrong, select the next question, score the candidate, or
make a hiring decision.

Useful API routes are `GET /api/domains`, `POST /api/resume/analyze`,
`POST /api/coach/start`, `POST /api/coach/answer`, and
`GET /api/coach/{interview_id}/report`.

Run tests with:

```powershell
python -m pytest
```