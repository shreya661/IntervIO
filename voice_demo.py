"""Temporary local web demo for Person 2's live voice pipeline.

Run with ``python -m uvicorn voice_demo:app --reload`` and open the displayed
localhost URL. This is intentionally independent of the team's future
frontend/backend and contains no camera or interview-evaluation logic.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from functools import lru_cache
import os
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from multimodal.live_voice import LiveVoiceProcessor
from multimodal.speech_to_text import EmptyAudioError, SpeechToTextError
from multimodal.resume_analyzer import ResumeAnalysisError, ResumeAnalyzer, ResumeProfile
from multimodal.domains import DOMAINS
from multimodal.visual_analyzer import VisualAnalyzer
from multimodal.gemini_assistant import GeminiAssistant
from interview_coach import AdaptiveInterviewCoach, PracticeInterviewState


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>InterviewOne — Voice Demo</title>
<style>
body{font:16px system-ui,sans-serif;max-width:860px;margin:48px auto;padding:0 20px;background:#f6f8fb;color:#142033}main{background:white;padding:28px;border-radius:12px;box-shadow:0 2px 12px #0001}button{padding:10px 14px;margin:6px 6px 6px 0;border:0;border-radius:7px;background:#1959b8;color:white;font-weight:600}button:disabled{background:#8ca5c9}#stop{background:#9f2935}.hidden{display:none}#status{min-height:25px;font-weight:600}pre{white-space:pre-wrap;background:#f0f3f8;padding:14px;border-radius:8px;overflow:auto}small{color:#526277}label{display:block;margin:12px 0}select,input{padding:8px;margin-left:8px;max-width:100%}.notice{padding:12px;background:#eef5ff;border-left:4px solid #1959b8}.graph{width:100%;height:120px;border:1px solid #d8e0eb;margin:8px 0;background:#fbfcfe}</style>
</head><body><main><h1>InterviewOne Voice Demo</h1>
<p>Upload your resume, choose a practice domain, and receive adaptive coaching based on your answers.</p>
<p class="notice"><strong>Practice focus:</strong> keep this interview tab open, answer in your own words, and do not use outside assistance. Camera and browser-focus signals are technical prompts only; they are not proof of copying and do not affect answer evaluation.</p>
<label>Domain <select id="domain"></select></label>
<label>Resume <input id="resume" type="file" accept=".pdf,.docx"><button id="upload">Analyze resume</button></label>
<p id="resume-status" aria-live="polite"></p><button id="begin">Start practice</button>
<section id="question" class="hidden"><h2>Question</h2><p id="question-text"></p><button id="camera">Enable camera</button><video id="preview" class="hidden" autoplay muted playsinline width="240"></video><button id="start">Start recording</button><button id="stop" disabled>Stop and continue</button></section>
<p id="status" aria-live="polite"></p><section id="report" class="hidden"><h2>Practice Feedback</h2><p id="content"></p><p id="feedback"></p><p id="suggestion"></p><button id="finish">View final coaching report</button></section>
<section id="final" class="hidden"><h2>Final Coaching Report</h2><h3>Overall Performance</h3><p id="final-summary"></p><h3>Answer &amp; Content Analysis</h3><p id="final-content"></p><h3>Strengths</h3><ul id="final-strengths"></ul><h3>Genuine Knowledge/Answer Gaps</h3><ul id="final-gaps"></ul><h3>Voice &amp; Delivery</h3><p id="final-voice"></p><div id="charts"><canvas id="wpm" class="graph"></canvas><canvas id="volume" class="graph"></canvas><canvas id="pitch" class="graph"></canvas><canvas id="pauses" class="graph"></canvas></div><h3>Coach Feedback</h3><ul id="final-feedback"></ul><h3>Next Practice Recommendation</h3><p id="final-next"></p></section>
<small>Voice and camera signals are optional observable coaching data. They do not infer emotion, personality, honesty, or hiring suitability.</small>
</main><script>
let recorder, parts=[], stream, cameraStream, interviewId, resumeId=null, focusEvents=[], focusStarted=Date.now();
const begin=document.querySelector('#begin'), domain=document.querySelector('#domain'), question=document.querySelector('#question'), questionText=document.querySelector('#question-text'), camera=document.querySelector('#camera'), preview=document.querySelector('#preview'), start=document.querySelector('#start'), stop=document.querySelector('#stop'), status=document.querySelector('#status'), report=document.querySelector('#report'), content=document.querySelector('#content'), feedback=document.querySelector('#feedback'), suggestion=document.querySelector('#suggestion'), resume=document.querySelector('#resume'), upload=document.querySelector('#upload'), resumeStatus=document.querySelector('#resume-status'), finish=document.querySelector('#finish'), final=document.querySelector('#final');
fetch('/api/domains').then(r=>r.json()).then(body=>body.domains.forEach(item=>{const option=document.createElement('option');option.value=item;option.textContent=item;domain.append(option);}));
document.addEventListener('visibilitychange',()=>{if(document.hidden)focusEvents.push('page_hidden');else focusEvents.push('page_visible');});
window.addEventListener('blur',()=>focusEvents.push('window_blur'));
window.addEventListener('focus',()=>focusEvents.push('window_focus'));
upload.onclick=async()=>{if(!resume.files[0]){resumeStatus.textContent='Choose a PDF or DOCX resume first.';return;}const form=new FormData();form.append('resume',resume.files[0]);resumeStatus.textContent='Analyzing resume…';const response=await fetch('/api/resume/analyze',{method:'POST',body:form});const body=await response.json();if(!response.ok){resumeStatus.textContent=body.detail||'Resume analysis failed.';return;}resumeId=body.resume_id;resumeStatus.textContent='Resume analyzed. Your first question will use it.';};
begin.onclick=async()=>{const form=new FormData();form.append('domain',domain.value);if(resumeId)form.append('resume_id',resumeId);const response=await fetch('/api/coach/start',{method:'POST',body:form});const body=await response.json();interviewId=body.interview_id;questionText.textContent=body.question.question;question.classList.remove('hidden');begin.disabled=true;domain.disabled=true;status.textContent='Start with this accessible question.';};
camera.onclick=async()=>{try{cameraStream=await navigator.mediaDevices.getUserMedia({video:true});preview.srcObject=cameraStream;preview.classList.remove('hidden');camera.disabled=true;camera.textContent='Camera enabled';}catch(error){status.textContent='Camera unavailable; continuing with voice only.';}};
start.onclick=async()=>{try{stream=await navigator.mediaDevices.getUserMedia({audio:true});const mime=MediaRecorder.isTypeSupported('audio/webm;codecs=opus')?'audio/webm;codecs=opus':'';recorder=new MediaRecorder(stream,mime?{mimeType:mime}:undefined);parts=[];recorder.ondataavailable=e=>parts.push(e.data);recorder.onstop=send;recorder.start();start.disabled=true;stop.disabled=false;status.textContent='Recording…';}catch(error){status.textContent='Microphone access failed: '+error.message;}};
stop.onclick=()=>{stop.disabled=true;status.textContent='Preparing audio…';recorder.stop();stream.getTracks().forEach(track=>track.stop());};
async function send(){const blob=new Blob(parts,{type:recorder.mimeType||'audio/webm'});const form=new FormData();form.append('audio',blob,'answer.webm');form.append('interview_id',interviewId);form.append('focus_events',JSON.stringify(focusEvents));if(cameraStream){const canvas=document.createElement('canvas');canvas.width=preview.videoWidth;canvas.height=preview.videoHeight;canvas.getContext('2d').drawImage(preview,0,0);const frame=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg'));if(frame)form.append('camera',frame,'frame.jpg');}status.textContent='Reviewing your answer…';report.classList.add('hidden');try{const response=await fetch('/api/coach/answer',{method:'POST',body:form});const body=await response.json();if(!response.ok)throw new Error(body.detail||'Analysis failed');content.textContent=body.report.answer_content;feedback.textContent=body.report.voice_delivery||'';suggestion.textContent=body.report.coaching_suggestions.join(' ');report.classList.remove('hidden');if(body.next_question){questionText.textContent=body.next_question.question;status.textContent='Here is your next practice question.';}else status.textContent=body.voice_message||'Please repeat your answer.';}catch(error){status.textContent='Error: '+error.message;}finally{start.disabled=false;stop.disabled=true;}}
finish.onclick=async()=>{const response=await fetch('/api/coach/'+interviewId+'/report');const body=await response.json();final.classList.remove('hidden');const candidate=body.candidate_report;final.querySelector('#final-summary').textContent=candidate.overall;final.querySelector('#final-content').textContent=candidate.answer_content;fillList('final-strengths',candidate.strengths);fillList('final-gaps',candidate.gaps);fillList('final-feedback',candidate.coach_feedback);final.querySelector('#final-voice').textContent=candidate.voice_delivery||'No voice observation is available yet.';final.querySelector('#final-next').textContent=candidate.next_practice;draw('wpm',body.voice_graphs.speech_rate_wpm,'Speech rate (WPM)');draw('volume',body.voice_graphs.volume_stability,'Volume stability');draw('pitch',body.voice_graphs.pitch_mean_hz,'Pitch (Hz)');draw('pauses',body.voice_graphs.pause_count,'Meaningful pauses');};
function fillList(id,values){const list=document.getElementById(id);list.replaceChildren();(values.length?values:['None recorded yet.']).forEach(value=>{const item=document.createElement('li');item.textContent=value;list.append(item);});}
function draw(id,values,label){const canvas=document.getElementById(id),ctx=canvas.getContext('2d');canvas.width=canvas.clientWidth||700;canvas.height=120;ctx.clearRect(0,0,canvas.width,canvas.height);ctx.fillStyle='#526277';ctx.fillText(label,10,18);const points=values.map((value,index)=>({value,index})).filter(point=>Number.isFinite(point.value));if(!points.length)return;const max=Math.max(...points.map(point=>point.value),1),min=Math.min(...points.map(point=>point.value),0),range=max-min||1;ctx.strokeStyle='#1959b8';ctx.beginPath();points.forEach((point,index)=>{const x=10+point.index*(canvas.width-20)/Math.max(values.length-1,1),y=canvas.height-10-((point.value-min)/range)*(canvas.height-35);index?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.stroke();}
</script></body></html>"""

_gemini = GeminiAssistant()
_coach = AdaptiveInterviewCoach(ai_assistant=_gemini)
_sessions: dict[str, PracticeInterviewState] = {}
_resumes: dict[str, ResumeProfile] = {}


def create_app(processor_factory: Callable[[], LiveVoiceProcessor] | None = None) -> FastAPI:
    """Create the isolated demo app; dependency injection keeps endpoint tests offline."""
    factory = processor_factory or _processor
    app = FastAPI(title="InterviewOne Voice Demo", version="0.1.0")

    @app.get("/", response_class=HTMLResponse)
    async def page() -> str:
        return PAGE

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "voice-demo"}

    @app.get("/api/domains")
    async def domains() -> dict[str, tuple[str, ...]]:
        return {"domains": DOMAINS}

    @app.post("/api/resume/analyze")
    async def analyze_resume(resume: UploadFile = File(...)) -> dict[str, Any]:
        suffix = Path(resume.filename or "").suffix.lower()
        if suffix not in {".pdf", ".docx"}:
            raise HTTPException(status_code=415, detail="Resume must be a PDF or DOCX file.")
        temporary = NamedTemporaryFile(suffix=suffix, delete=False)
        path = Path(temporary.name)
        try:
            temporary.write(await resume.read())
            temporary.close()
            analyzer = ResumeAnalyzer()
            profile = analyzer.analyze(path)
            if _gemini.enabled:
                try:
                    profile = ResumeProfile(**_gemini.analyze_resume(analyzer.extract_text(path), profile.to_dict()))
                except (RuntimeError, ValueError, TypeError, KeyError):
                    pass
            resume_id = str(uuid4())
            _resumes[resume_id] = profile
            return {"resume_id": resume_id, "profile": profile}
        except (ResumeAnalysisError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            if not temporary.closed:
                temporary.close()
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass

    @app.post("/api/voice/analyze")
    async def analyze_audio(
        audio: UploadFile = File(...), language: str | None = Form(default=None)
    ) -> dict[str, Any]:
        try:
            result = factory().process_bytes(
                await audio.read(), filename=audio.filename or "answer.webm", language=language
            )
            return result.to_payload()
        except EmptyAudioError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (SpeechToTextError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/coach/start")
    async def start_coach(
        domain: str = Form(...), goal: str = Form(default="practice"),
        resume_id: str | None = Form(default=None),
    ) -> dict[str, Any]:
        if domain not in DOMAINS and not domain.strip():
            raise HTTPException(status_code=400, detail="Choose a valid interview domain.")
        resume = _resumes.get(resume_id) if resume_id else None
        state, question = _coach.start(domain, goal, resume=resume)
        interview_id = str(uuid4())
        _sessions[interview_id] = state
        return {"interview_id": interview_id, "question": question}

    @app.post("/api/coach/answer")
    async def answer_coach(
        interview_id: str = Form(...), audio: UploadFile = File(...),
        camera: UploadFile | None = File(default=None),
        focus_events: str = Form(default="[]"),
    ) -> dict[str, Any]:
        state = _sessions.get(interview_id)
        if state is None:
            raise HTTPException(status_code=404, detail="Practice session was not found. Start a new session.")
        try:
            baseline = state.voice_observations[-1] if state.voice_observations else None
            voice = factory().process_bytes(
                await audio.read(), filename=audio.filename or "answer.webm", baseline=baseline
            )
            state.voice_observations.append(voice.observation)
            try:
                events = json.loads(focus_events)
                if isinstance(events, list):
                    state.focus_events.extend(str(event) for event in events if isinstance(event, str))
            except json.JSONDecodeError:
                pass
            visual_observation = await _analyze_camera_upload(camera) if camera else None
            if visual_observation is not None:
                state.visual_observations.append(visual_observation)
            review, next_question = _coach.answer(
                state,
                voice.transcription.transcript,
                transcription_reliable=voice.status.value == "accepted",
                voice_feedback=voice.candidate_feedback,
            )
            report = _coach.report(
                review,
                next_question,
                voice_feedback=voice.candidate_feedback,
                observation=voice.observation,
                baseline=baseline,
            )
            return {
                "report": report, "next_question": next_question, "voice_message": voice.message,
                "visual_observation": visual_observation,
            }
        except EmptyAudioError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (SpeechToTextError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/coach/{interview_id}/report")
    async def final_report(interview_id: str) -> dict[str, Any]:
        state = _sessions.get(interview_id)
        if state is None:
            raise HTTPException(status_code=404, detail="Practice session was not found.")
        observations = state.voice_observations
        latest_voice = observations[-1] if observations else None
        return {
            "practice_record": asdict(_coach.final_report(state)),
            "candidate_report": _candidate_report(state),
            "voice_delivery": {
                "speech_rate_wpm": latest_voice.speech_rate_wpm,
                "pause_count": latest_voice.pause_count,
                "filler_rate": latest_voice.filler_rate,
                "volume_stability": latest_voice.volume_stability,
                "pitch_mean_hz": latest_voice.pitch_mean_hz,
                "pitch_variation": latest_voice.pitch_variation,
                "analysis_reliable": latest_voice.analysis_reliable,
            } if latest_voice else None,
            "voice_graphs": {
                "speech_rate_wpm": [observation.speech_rate_wpm for observation in observations],
                "pause_count": [observation.pause_count for observation in observations],
                "filler_rate": [observation.filler_rate for observation in observations],
                "volume_stability": [observation.volume_stability for observation in observations],
                "pitch_mean_hz": [observation.pitch_mean_hz for observation in observations],
                "lighting_quality": [observation.lighting_quality for observation in state.visual_observations],
            },
            "questions_reviewed": len(state.answers),
            "domain": state.domain,
            "goal": state.goal,
            "practice_focus": {
                "browser_focus_events": len(state.focus_events),
                "note": "These are technical focus signals only, not evidence of copying or dishonesty.",
            },
        }

    return app


async def _analyze_camera_upload(camera: UploadFile):
    """Analyze one optional browser frame; camera failure never blocks audio."""
    try:
        from io import BytesIO
        import numpy as np
        from PIL import Image

        image = Image.open(BytesIO(await camera.read())).convert("RGB")
        return VisualAnalyzer().analyze(np.asarray(image))
    except Exception:
        return None


def _candidate_report(state: PracticeInterviewState) -> dict[str, Any]:
    record = _coach.final_report(state)
    demonstrated = tuple(record.strengths)
    gaps = tuple(record.knowledge_gaps)
    if demonstrated:
        content = f"You demonstrated {', '.join(demonstrated)} across {len(state.answer_reviews)} reviewed answer(s)."
    else:
        content = "Your answers need more specific evidence before the concepts can be confirmed."
    if gaps:
        content += f" The main areas to revisit are {', '.join(gaps)}."
    latest = state.voice_observations[-1] if state.voice_observations else None
    voice = None
    if latest:
        voice = (
            f"Speaking pace: {latest.speech_rate_wpm:.0f} WPM; pitch: "
            f"{_number_text(latest.pitch_mean_hz, 'Hz')}; pitch variation: "
            f"{_number_text(latest.pitch_variation, '')}; volume stability: "
            f"{_number_text(latest.volume_stability, '')}; pauses: "
            f"{latest.pause_count} ({latest.total_pause_duration_seconds:.1f}s total); "
            f"fillers: {latest.filler_count} ({latest.filler_rate:.0%}); "
            f"delivery: {'reliable' if latest.analysis_reliable else 'needs review'}."
        )
    feedback = record.recommendations or ("Continue practicing with concrete examples.",)
    return {
        "overall": f"You reviewed {len(state.answer_reviews)} answer(s) in {state.domain}. This is a practice record for your next improvement step, not a hiring assessment.",
        "answer_content": content,
        "strengths": list(record.strengths),
        "gaps": list(record.knowledge_gaps),
        "voice_delivery": voice,
        "coach_feedback": list(feedback),
        "next_practice": feedback[-1],
    }


def _number_text(value: float | None, suffix: str) -> str:
    return "unavailable" if value is None else f"{value:.2f}{suffix}"


@lru_cache(maxsize=1)
def _processor() -> LiveVoiceProcessor:
    """Keep one local model instance alive after the first submitted answer."""
    return LiveVoiceProcessor()


app = create_app()
