"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import AgentTrace from "../../components/AgentTrace";
import CameraPanel, { type VisualSignalCapture } from "../../components/CameraPanel";
import VoiceInput from "../../components/VoiceInput";

interface AnswerRecord {
  question: string;
  answer: string;
  skill: string | null;
}

interface PlannedStage {
  stage_name: string;
  difficulty: string;
  focus_skills: string[];
  question_count: number;
  resume_reference?: string | null;
  job_reference?: string | null;
}

interface InterviewPlan {
  role_title: string;
  tech_stack: string[];
  company_focus: string;
  stages: PlannedStage[];
  total_questions: number;
  planned_summary: string;
}

interface HRCompetencyGrade {
  category: string;
  grade: string;
  score: number;
  feedback: string;
}

interface HREvaluation {
  overall_grade: string;
  overall_score: number;
  hiring_recommendation: string;
  candidate_summary: string;
  intro_grade: string;
  skills_grade: string;
  behavioral_grade: string;
  competencies: HRCompetencyGrade[];
}

interface InterviewState {
  interview_id: string;
  candidate_name: string;
  goal: string;
  duration_minutes: number;
  status: string;
  current_question: string | null;
  current_skill: string | null;
  question_number: number;
  answers: AnswerRecord[];
  evidence: string[];
  evidence_gap: string | null;
  next_action: string | null;
  current_difficulty?: string | null;
  company_name?: string | null;
  company_needs?: string | null;
  job_title?: string | null;
  ai_powered?: boolean;
  interview_plan?: InterviewPlan | null;
  hr_evaluation?: HREvaluation | null;
}

export default function InterviewPage() {
  const [interview, setInterview] = useState<InterviewState | null>(null);
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [isEnding, setIsEnding] = useState(false);
  const [timeLeft, setTimeLeft] = useState(30 * 60);

  // Question transition animation state
  const [questionVisible, setQuestionVisible] = useState(true);
  const [questionKey, setQuestionKey] = useState(0);
  const [showNewBadge, setShowNewBadge] = useState(false);

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const cameraCaptureRef = useRef<(() => VisualSignalCapture | null) | null>(null);

  const handleVoiceTranscript = (text: string) => {
    setAnswer(text);
  };

  const endInterview = useCallback(async (iv: InterviewState) => {
    if (isEnding) return;
    setIsEnding(true);

    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/interviews/${iv.interview_id}/end`,
        { method: "POST" }
      );

      if (!response.ok) {
        throw new Error("Failed to end interview");
      }

      window.location.href = "/report?completed=true";
    } catch (err) {
      console.error("Error ending interview:", err);
      setError("Unable to end the interview. Please try again.");
      setIsEnding(false);
    }
  }, [isEnding]);

  useEffect(() => {
    const storedInterview = sessionStorage.getItem("interview");

    if (!storedInterview) {
      setError("No active interview found.");
      return;
    }

    try {
      const parsedInterview = JSON.parse(storedInterview);
      setInterview(parsedInterview);
      setTimeLeft(parsedInterview.duration_minutes * 60);
    } catch {
      setError("Could not load interview data.");
    }
  }, []);

  useEffect(() => {
    if (!interview) return;

    timerRef.current = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timerRef.current!);
          timerRef.current = null;
          endInterview(interview);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [interview?.interview_id, endInterview, interview]);

  const formatTime = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${String(minutes).padStart(2, "0")}:${String(
      remainingSeconds
    ).padStart(2, "0")}`;
  };

  const submitAnswer = async () => {
    if (!interview || !answer.trim()) return;

    setLoading(true);
    setError("");

    const visualSignal = cameraCaptureRef.current?.() ?? null;

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/interviews/${interview.interview_id}/answer`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            answer,
            visual_signal: visualSignal,
          }),
        }
      );

      if (!response.ok) {
        throw new Error("Failed to submit answer");
      }

      const updatedInterview: InterviewState = await response.json();

      if (updatedInterview.question_number > 20 || (updatedInterview.answers && updatedInterview.answers.length >= 20)) {
        await endInterview(updatedInterview);
        return;
      }

      setQuestionVisible(false);
      await new Promise((r) => setTimeout(r, 300));

      setInterview(updatedInterview);
      sessionStorage.setItem("interview", JSON.stringify(updatedInterview));
      setAnswer("");

      setQuestionKey((k) => k + 1);
      setQuestionVisible(true);

      setShowNewBadge(true);
      setTimeout(() => setShowNewBadge(false), 2500);

    } catch (err) {
      console.error(err);
      setError("Could not submit your answer. Please check your connection and try again.");
      setQuestionVisible(true);
    } finally {
      setLoading(false);
    }
  };

  if (error && !interview) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-950 px-6 text-white">
        <div className="text-center">
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-8">
            <h1 className="text-2xl font-semibold">Interview Error</h1>
            <p className="mt-3 text-slate-400">{error}</p>
          </div>
          <a
            href="/"
            className="mt-6 inline-block rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold hover:bg-blue-500 transition"
          >
            ← Back to Setup
          </a>
        </div>
      </main>
    );
  }

  if (!interview) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-950 text-white">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-700 border-t-blue-400" />
          <p className="text-slate-400">Loading interview session...</p>
        </div>
      </main>
    );
  }

  const isTimeLow = timeLeft <= 120;
  const qNum = interview.question_number;
  const currentStageIndex = qNum <= 10 ? 0 : qNum <= 15 ? 1 : 2;
  const currentStage = interview.interview_plan?.stages[currentStageIndex];

  return (
    <main className="min-h-screen bg-slate-950 text-white">

      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-20">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3.5">

          <div className="flex items-center gap-4">
            <img
              src="/logo.png"
              alt="InterviewOne AI Logo"
              className="h-9 w-9 rounded-xl border border-slate-700/80 shadow-md object-cover"
            />
            <div>
              <h1 className="text-lg font-bold leading-tight">
                InterviewOne <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-indigo-400">AI</span>
              </h1>
              <p className="text-xs text-slate-400 flex items-center gap-1.5">
                <span>{interview.interview_plan?.role_title || interview.job_title || "Software Engineer"}</span>
                {interview.company_name && (
                  <span className="text-blue-300 font-medium">@ {interview.company_name}</span>
                )}
              </p>
            </div>

            {/* AI Engine Badge */}
            <div className="hidden sm:flex items-center gap-1.5 rounded-full border border-purple-500/30 bg-purple-500/10 px-3 py-1 text-xs text-purple-300 font-medium">
              <span>✨</span>
              <span>Gemini 2.0 Flash Active</span>
            </div>
          </div>

          <div className="flex items-center gap-5">
            <div className="text-right hidden md:block">
              <p className="text-[11px] text-slate-500">Candidate</p>
              <p className="text-sm font-semibold text-slate-200">{interview.candidate_name}</p>
            </div>

            {/* Timer */}
            <div className={`rounded-xl border px-3.5 py-1.5 transition ${
              isTimeLow
                ? "border-red-500/40 bg-red-500/10"
                : "border-slate-700 bg-slate-950"
            }`}>
              <p className="text-[10px] text-slate-500">Remaining</p>
              <p className={`font-mono text-base font-bold ${
                isTimeLow ? "text-red-400 animate-pulse" : "text-blue-400"
              }`}>
                {formatTime(timeLeft)}
              </p>
            </div>
          </div>

        </div>
      </header>

      {/* Main Content */}
      <div className="mx-auto max-w-7xl px-6 py-7">

        {/* 3-Stage Curriculum Progress Banner */}
        <div className="mb-6 rounded-2xl border border-slate-800 bg-slate-900/90 p-4 shadow-xl">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-2.5">
            <div>
              <div className="flex items-center gap-2">
                <p className="text-xs font-semibold uppercase tracking-wider text-blue-400">
                  {currentStage?.stage_name || `Stage ${currentStageIndex + 1} of 3`}
                </p>
                <span className="rounded bg-blue-500/20 px-2 py-0.5 text-[10px] font-bold text-blue-300">
                  {currentStageIndex === 0 ? "10 Qs (1–10)" : currentStageIndex === 1 ? "5 Qs (11–15)" : "5 Qs (16–20)"}
                </span>
              </div>
              <p className="text-lg font-bold text-white mt-0.5">
                Question {interview.question_number} <span className="text-xs font-normal text-slate-500">/ 20 Total</span>
              </p>
            </div>

            {/* 3 Stage Step Indicators */}
            <div className="flex items-center gap-2">
              {[
                { stage: 1, name: "HR Intro & Skills", range: "1–10" },
                { stage: 2, name: "Architecture", range: "11–15" },
                { stage: 3, name: "Culture Fit (STAR)", range: "16–20" },
              ].map((s, idx) => {
                const isCurrent = currentStageIndex === idx;
                const isDone = currentStageIndex > idx;
                return (
                  <div
                    key={s.stage}
                    className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs transition ${
                      isCurrent
                        ? "border-blue-500/60 bg-blue-500/20 text-blue-200 font-semibold ring-1 ring-blue-500/30"
                        : isDone
                        ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                        : "border-slate-800 bg-slate-950 text-slate-500"
                    }`}
                  >
                    <span>{isDone ? "✓" : isCurrent ? "▶" : "○"}</span>
                    <span className="hidden sm:inline">{s.name}</span>
                    <span className="text-[10px] opacity-75">({s.range})</span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-blue-500 via-indigo-500 to-emerald-500 transition-all duration-500"
              style={{ width: `${Math.min(100, Math.max(5, Math.round((interview.question_number / 20) * 100)))}%` }}
            />
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">

          {/* Main Question & Answer Panel */}
          <section className="lg:col-span-2 space-y-6">

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-7 sm:p-8 shadow-2xl">

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/20 text-blue-400 font-bold">
                    HR
                  </div>
                  <div>
                    <p className="font-semibold text-white">Agentic HR Talent Partner</p>
                    <p className="text-xs text-slate-400">
                      Warm introduction, resume verification & candidate scorecard
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {interview.current_skill && (
                    <span className="rounded-full bg-slate-800 border border-slate-700 px-3 py-1 text-xs text-slate-300 font-medium">
                      🎯 {interview.current_skill}
                    </span>
                  )}
                </div>
              </div>

              {/* Question Box */}
              <div
                key={questionKey}
                className="mt-6 rounded-2xl border border-blue-500/25 bg-blue-500/5 p-6 transition-all duration-300"
                style={{
                  opacity: questionVisible ? 1 : 0,
                  transform: questionVisible ? "translateY(0)" : "translateY(-6px)",
                }}
              >
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold text-blue-400">
                    Question {interview.question_number} of 20
                  </span>

                  {interview.current_difficulty && (
                    <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold border ${
                      interview.current_difficulty === "easy"
                        ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                        : interview.current_difficulty === "moderate"
                        ? "bg-amber-500/10 border-amber-500/30 text-amber-400"
                        : "bg-rose-500/10 border-rose-500/30 text-rose-400"
                    }`}>
                      {interview.current_difficulty === "easy"
                        ? "🟢 Easy / Logic Baseline"
                        : interview.current_difficulty === "moderate"
                        ? "🟡 Moderate / Architecture"
                        : "🔴 Tricky / Edge Case"}
                    </span>
                  )}

                  {showNewBadge && (
                    <span className="animate-pulse rounded-full bg-emerald-500/20 border border-emerald-500/30 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-400">
                      ✨ New Question Loaded
                    </span>
                  )}
                </div>

                <h2 className="text-xl sm:text-2xl font-bold leading-relaxed whitespace-pre-wrap text-slate-100">
                  {interview.current_question ?? "Generating personalized question..."}
                </h2>

                {currentStage?.resume_reference && (
                  <p className="mt-3 text-xs text-slate-400 border-t border-slate-800/80 pt-2 flex items-center gap-1.5">
                    <span>📄</span>
                    <span>Investigating resume claim: <strong className="text-slate-300">{currentStage.resume_reference}</strong></span>
                  </p>
                )}
              </div>

              {/* Answer Input */}
              <div className="mt-6">
                <div className="mb-2 flex items-center justify-between">
                  <label className="text-sm font-semibold text-slate-200">
                    Your Response
                  </label>
                  <span className="text-xs text-slate-500">
                    Provide concrete code examples, trade-offs, and design rationale
                  </span>
                </div>

                <div className="mb-3">
                  <VoiceInput onTranscript={handleVoiceTranscript} />
                </div>

                <textarea
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  onKeyDown={(e) => {
                    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
                      e.preventDefault();
                      submitAnswer();
                    }
                  }}
                  placeholder="Type your technical response here, or use the voice button above... (Press Ctrl+Enter to submit)"
                  className="min-h-44 w-full rounded-xl border border-slate-700 bg-slate-950 p-4 text-sm text-white outline-none placeholder:text-slate-500 focus:border-blue-500 font-sans leading-relaxed"
                />

                <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                  <span>{answer.trim().split(/\s+/).filter(Boolean).length} words</span>
                  <span>Shortcut: <kbd className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-300 font-mono">Ctrl+Enter</kbd></span>
                </div>
              </div>

              {error && (
                <div className="mt-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
                  ⚠ {error}
                </div>
              )}

              {/* Action Buttons */}
              <button
                id="submit-answer-button"
                onClick={submitAnswer}
                disabled={loading || !answer.trim()}
                className="mt-5 w-full rounded-xl bg-blue-600 px-6 py-4 font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-40 shadow-lg shadow-blue-500/20"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                    Evaluating Technical Depth...
                  </span>
                ) : (
                  "Submit Answer & Proceed →"
                )}
              </button>

              <button
                type="button"
                disabled={isEnding}
                onClick={() => endInterview(interview)}
                className="mt-3 w-full rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-3 text-xs font-semibold text-red-400 transition hover:bg-red-500/20 disabled:opacity-50"
              >
                {isEnding ? "Ending Interview..." : "End Interview & View Final Report"}
              </button>

            </div>
          </section>

          {/* Right Column: Agent Trace, Plan, Camera, Evidence */}
          <aside className="space-y-6">

            {/* Generated Interview Plan Card */}
            {interview.interview_plan && (
              <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-xl">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
                  <div>
                    <h3 className="text-sm font-bold text-white">Agent Interview Plan</h3>
                    <p className="text-[11px] text-slate-400">Derived from Resume & Role</p>
                  </div>
                  <span className="rounded bg-blue-500/20 text-blue-300 px-2 py-0.5 text-[10px] font-semibold">
                    20 Qs
                  </span>
                </div>

                {/* Tech Stack Pills */}
                {interview.interview_plan.tech_stack.length > 0 && (
                  <div className="mb-4">
                    <p className="text-[11px] text-slate-500 uppercase font-semibold mb-1.5">Target Stack</p>
                    <div className="flex flex-wrap gap-1.5">
                      {interview.interview_plan.tech_stack.map((t, idx) => (
                        <span key={idx} className="rounded-md bg-slate-800 px-2 py-0.5 text-[11px] font-medium text-slate-300 border border-slate-700">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Stages List */}
                <div className="space-y-2.5">
                  {interview.interview_plan.stages.map((stage, sIdx) => {
                    const isCurrent = currentStageIndex === sIdx;
                    const isDone = currentStageIndex > sIdx;
                    return (
                      <div
                        key={sIdx}
                        className={`rounded-xl border p-3 text-xs transition ${
                          isCurrent
                            ? "border-blue-500/50 bg-blue-500/10 text-white"
                            : isDone
                            ? "border-emerald-500/30 bg-emerald-500/5 text-slate-300"
                            : "border-slate-800/80 bg-slate-950/60 text-slate-500"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold">{stage.stage_name}</span>
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            isDone ? "bg-emerald-500/20 text-emerald-400" : isCurrent ? "bg-blue-500/20 text-blue-400" : "bg-slate-800 text-slate-500"
                          }`}>
                            {stage.question_count} Qs
                          </span>
                        </div>
                        {stage.focus_skills.length > 0 && (
                          <p className="mt-1 text-[11px] text-slate-400">
                            Focus: {stage.focus_skills.slice(0, 3).join(", ")}
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Agent State Card */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-xl">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
                <h3 className="text-sm font-semibold text-white">Agent Action</h3>
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              </div>
              <p className="text-xs leading-relaxed text-slate-300 font-mono">
                {interview.next_action || "Awaiting candidate response"}
              </p>
            </div>

            {/* Evidence Gap Card */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-xl">
              <p className="text-xs uppercase tracking-wider text-slate-500 font-semibold mb-2">Evidence Target</p>
              <p className="text-xs leading-relaxed text-slate-300">
                {interview.evidence_gap || "Synthesizing baseline evidence across candidate's stack."}
              </p>
            </div>

            {/* Camera Panel */}
            <CameraPanel captureRef={cameraCaptureRef} />

            {/* Agent Trace */}
            <AgentTrace
              goal={interview.goal}
              skill={interview.current_skill}
              questionNumber={interview.question_number}
              evidenceGap={interview.evidence_gap}
              nextAction={interview.next_action}
              hasAnswer={interview.answers.length > 0}
            />

          </aside>

        </div>
      </div>
    </main>
  );
}