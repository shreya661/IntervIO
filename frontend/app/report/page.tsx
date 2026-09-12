"use client";

import { useEffect, useState } from "react";

interface Score {
  skill: string;
  score: number;
}

interface VisualSummary {
  turns_with_camera: number;
  face_detected_turns: number;
  presence_rate: number;
  note: string;
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

interface HRComposureEvaluation {
  overall_composure: string;
  poise_score: number;
  gaze_stability_pct: number;
  fidget_index: string;
  stress_indicators: string[];
  hr_observations: string;
  encryption_status?: string;
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
  composure_evaluation?: HRComposureEvaluation | null;
}

interface Assessment {
  interview_id: string;
  candidate_name: string;
  company_name?: string | null;
  company_needs?: string | null;
  job_title?: string | null;
  ai_powered?: boolean;
  interview_plan?: InterviewPlan | null;
  hr_evaluation?: HREvaluation | null;
  composure_evaluation?: HRComposureEvaluation | null;
  competency_scores: Score[];
  overall_score: number;
  evidence_coverage: number;
  confidence: number;
  strengths: string[];
  gaps: string[];
  unverified_claims: string[];
  recommendation: string;
  visual_summary: VisualSummary | null;
  resume_personalised: boolean;
  questions_answered: number;
}

export default function ReportPage() {
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [downloadError, setDownloadError] = useState("");
  const [isCompletedFromInterview, setIsCompletedFromInterview] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      if (params.get("completed") === "true") {
        setIsCompletedFromInterview(true);
      }
    }
  }, []);

  const handleDownloadPdf = async () => {
    if (!assessment) return;
    setDownloadingPdf(true);
    setDownloadError("");

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/interviews/${assessment.interview_id}/assessment/pdf`
      );

      if (!response.ok) {
        throw new Error(`Failed to generate PDF (HTTP ${response.status})`);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;

      const safeName = (assessment.candidate_name || "Candidate")
        .replace(/[^a-zA-Z0-9_\-]/g, "_");
      link.download = `Technical_Evaluation_Report_${safeName}.pdf`;

      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("PDF download error:", err);
      setDownloadError("Unable to download PDF. Please check backend connection or use Print to save as PDF.");
    } finally {
      setDownloadingPdf(false);
    }
  };

  useEffect(() => {
    async function loadAssessment() {
      try {
        const storedInterview = sessionStorage.getItem("interview");

        if (!storedInterview) {
          setError("No active interview found.");
          setLoading(false);
          return;
        }

        const interview = JSON.parse(storedInterview);

        const response = await fetch(
          `http://127.0.0.1:8000/interviews/${interview.interview_id}/assessment`
        );

        if (!response.ok) {
          throw new Error("Failed to load assessment");
        }

        const data = await response.json();
        setAssessment(data);
      } catch (err) {
        console.error(err);
        setError("Unable to load assessment.");
      } finally {
        setLoading(false);
      }
    }

    loadAssessment();
  }, []);

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-950 p-10 text-white flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-700 border-t-blue-400" />
          <p className="text-slate-400">Synthesizing comprehensive assessment report...</p>
        </div>
      </main>
    );
  }

  if (error || !assessment) {
    return (
      <main className="min-h-screen bg-slate-950 p-10 text-white">
        <div className="mx-auto max-w-5xl">
          <div className="rounded-2xl border border-red-500/20 bg-red-500/10 p-6">
            <p className="text-red-400">{error || "Assessment unavailable"}</p>
          </div>
          <a
            href="/"
            className="mt-4 inline-block rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-semibold hover:bg-blue-500 transition"
          >
            ← Return to Home
          </a>
        </div>
      </main>
    );
  }

  const roleTitle = assessment.interview_plan?.role_title || assessment.job_title || "Software Engineer";

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-10 text-white">
      <div className="mx-auto max-w-5xl">

        {/* Interview Completion Celebration Banner */}
        {isCompletedFromInterview && (
          <div className="mb-6 rounded-2xl border border-emerald-500/40 bg-gradient-to-r from-emerald-950/70 via-slate-900 to-blue-950/70 p-6 shadow-2xl">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500/20 text-2xl text-emerald-400">
                  🎉
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white">Interview Complete! Your Evaluation Report is Ready</h2>
                  <p className="text-xs text-emerald-300/90 mt-0.5">
                    Your answers, technical depth, and non-verbal telemetry have been evaluated and compiled into an official PDF dossier.
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={handleDownloadPdf}
                disabled={downloadingPdf}
                className="flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-3 text-xs font-bold text-white shadow-lg shadow-emerald-600/30 transition hover:bg-emerald-500 disabled:opacity-50"
              >
                {downloadingPdf ? (
                  <>
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                    <span>Generating PDF...</span>
                  </>
                ) : (
                  <>
                    <span>📥</span>
                    <span>Download PDF Report</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* Top Header Card */}
        <div className="mb-8 rounded-2xl border border-slate-800 bg-slate-900 p-8 shadow-2xl">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <img
                src="/logo.png"
                alt="InterviewOne AI Logo"
                className="h-16 w-16 object-contain drop-shadow-lg"
              />
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-blue-400">InterviewOne AI Assessment</p>
                <h1 className="mt-0.5 text-3xl font-extrabold text-white">
                  Technical Evaluation Report
                </h1>
                <p className="mt-1 text-sm text-slate-300">
                  Candidate: <strong className="text-white">{assessment.candidate_name}</strong>
                  <span className="mx-2 text-slate-600">•</span>
                  Role: <strong className="text-blue-300">{roleTitle}</strong>
                  {assessment.company_name && (
                    <>
                      <span className="mx-2 text-slate-600">•</span>
                      Target: <strong className="text-purple-300">{assessment.company_name}</strong>
                    </>
                  )}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2.5">
              <button
                id="download-pdf-btn-top"
                type="button"
                onClick={handleDownloadPdf}
                disabled={downloadingPdf}
                className="flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-xs font-bold text-white shadow-lg shadow-blue-600/25 transition hover:bg-blue-500 disabled:opacity-50"
              >
                {downloadingPdf ? (
                  <>
                    <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                    <span>Generating PDF...</span>
                  </>
                ) : (
                  <>
                    <span>📥</span>
                    <span>Download PDF</span>
                  </>
                )}
              </button>
              <button
                type="button"
                onClick={() => window.print()}
                title="Print using system print dialog"
                className="rounded-xl border border-slate-700 bg-slate-800 px-3.5 py-2.5 text-xs font-semibold text-slate-300 transition hover:bg-slate-700"
              >
                🖨 Print
              </button>
            </div>
          </div>

          {downloadError && (
            <div className="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs text-amber-300">
              ⚠️ {downloadError}
            </div>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-2.5 pt-4 border-t border-slate-800">
            {assessment.resume_personalised && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400">
                📄 Resume Verified & Tailored
              </span>
            )}
            <span className="inline-flex items-center gap-1.5 rounded-full border border-purple-500/30 bg-purple-500/10 px-3 py-1 text-xs font-medium text-purple-300">
              ✨ Gemini 2.0 Flash Evaluator
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-xs font-medium text-blue-400">
              💬 {assessment.questions_answered} Questions Evaluated
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-700 bg-slate-950 px-3 py-1 text-xs font-medium text-slate-400">
              🔒 AES-256 Encrypted PII
            </span>
          </div>
        </div>

        {/* Metric Summary Cards */}
        <div className="mb-6 grid gap-6 md:grid-cols-3">
          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-xl">
            <p className="text-xs uppercase font-semibold text-slate-400 tracking-wider">Overall Score</p>
            <p className="mt-2 text-4xl font-extrabold text-blue-400">
              {assessment.overall_score}<span className="text-xl text-slate-500">/10</span>
            </p>
            <p className="mt-1 text-xs text-slate-500">Weighted across answer depth</p>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-xl">
            <p className="text-xs uppercase font-semibold text-slate-400 tracking-wider">Evidence Coverage</p>
            <p className="mt-2 text-4xl font-extrabold text-emerald-400">
              {assessment.evidence_coverage}%
            </p>
            <p className="mt-1 text-xs text-slate-500">Demonstrated technical coverage</p>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-xl">
            <p className="text-xs uppercase font-semibold text-slate-400 tracking-wider">Evaluation Confidence</p>
            <p className="mt-2 text-4xl font-extrabold text-purple-400">
              {assessment.confidence}%
            </p>
            <p className="mt-1 text-xs text-slate-500">Confidence based on answer volume</p>
          </div>
        </div>

        {/* ── Agentic HR Candidate Evaluation Scorecard ── */}
        {assessment.hr_evaluation && (
          <section className="mb-6 rounded-2xl border border-indigo-500/30 bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950/40 p-7 shadow-2xl">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-5 mb-5">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xl">🤝</span>
                  <h2 className="text-xl font-bold text-white">Agentic HR Candidate Scorecard</h2>
                </div>
                <p className="mt-1 text-xs text-slate-400">
                  Official Talent Partner evaluation derived from resume verification, candidate self-introduction, and behavioral alignment.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <div className="text-right">
                  <p className="text-[10px] uppercase font-bold text-slate-400">Overall Grade</p>
                  <p className={`text-3xl font-extrabold ${
                    assessment.hr_evaluation.overall_grade.startsWith("A")
                      ? "text-emerald-400"
                      : assessment.hr_evaluation.overall_grade.startsWith("B")
                      ? "text-blue-400"
                      : "text-amber-400"
                  }`}>
                    {assessment.hr_evaluation.overall_grade}
                  </p>
                </div>
                <span className={`rounded-xl px-3 py-1.5 text-xs font-bold border ${
                  assessment.hr_evaluation.overall_grade.startsWith("A")
                    ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-300"
                    : assessment.hr_evaluation.overall_grade.startsWith("B")
                    ? "bg-blue-500/15 border-blue-500/30 text-blue-300"
                    : "bg-amber-500/15 border-amber-500/30 text-amber-300"
                }`}>
                  {assessment.hr_evaluation.hiring_recommendation}
                </span>
              </div>
            </div>

            {/* Candidate Executive Summary */}
            <div className="mb-5 rounded-xl border border-slate-800 bg-slate-950/70 p-4">
              <p className="text-xs font-semibold uppercase text-slate-400 tracking-wider mb-1.5">Executive HR Summary</p>
              <p className="text-sm text-slate-200 leading-relaxed">
                {assessment.hr_evaluation.candidate_summary}
              </p>
            </div>

            {/* Stage Quick Grades */}
            <div className="grid gap-3 sm:grid-cols-3 mb-5">
              <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3.5">
                <p className="text-xs text-slate-400">🎤 Intro & Career Story</p>
                <p className="mt-1 text-xl font-bold text-emerald-400">Grade {assessment.hr_evaluation.intro_grade}</p>
                <p className="text-[11px] text-slate-500 mt-0.5">Communication clarity & motivation</p>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3.5">
                <p className="text-xs text-slate-400">📄 Resume Skills Depth</p>
                <p className="mt-1 text-xl font-bold text-blue-400">Grade {assessment.hr_evaluation.skills_grade}</p>
                <p className="text-[11px] text-slate-500 mt-0.5">Hands-on claim verification</p>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3.5">
                <p className="text-xs text-slate-400">🤝 Behavioral & Culture Fit</p>
                <p className="mt-1 text-xl font-bold text-purple-400">Grade {assessment.hr_evaluation.behavioral_grade}</p>
                <p className="text-[11px] text-slate-500 mt-0.5">Teamwork, ownership & STAR answers</p>
              </div>
            </div>

            {/* Granular Competencies Scorecard */}
            {assessment.hr_evaluation.competencies.length > 0 && (
              <div>
                <p className="text-xs font-semibold uppercase text-slate-400 tracking-wider mb-3">
                  HR Competency Assessment Breakdown
                </p>
                <div className="space-y-3">
                  {assessment.hr_evaluation.competencies.map((comp, cIdx) => (
                    <div key={cIdx} className="rounded-xl border border-slate-800 bg-slate-950/60 p-3.5">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs sm:text-sm font-semibold text-slate-200">{comp.category}</span>
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-0.5 rounded text-[11px] font-bold border ${
                            comp.grade.startsWith("A")
                              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                              : comp.grade.startsWith("B")
                              ? "bg-blue-500/10 border-blue-500/30 text-blue-400"
                              : "bg-amber-500/10 border-amber-500/30 text-amber-400"
                          }`}>
                            Grade {comp.grade}
                          </span>
                          <span className="text-xs font-bold text-slate-300">{comp.score}/10</span>
                        </div>
                      </div>
                      <p className="text-xs text-slate-400 leading-relaxed">{comp.feedback}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ── Non-Verbal Composure & Poise Telemetry Card ── */}
            {(assessment.hr_evaluation.composure_evaluation || assessment.composure_evaluation) && (
              <div className="mt-5 rounded-xl border border-slate-800 bg-slate-950/70 p-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xl">👁️</span>
                    <div>
                      <h4 className="text-sm font-bold text-white flex items-center gap-2">
                        <span>Non-Verbal Composure & Poise Telemetry</span>
                        <span className="rounded bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 text-[10px] font-semibold text-emerald-400">
                          🔒 AES-256 Encrypted
                        </span>
                      </h4>
                      <p className="text-[11px] text-slate-400">
                        In-memory biometric telemetry measuring poise, eye contact, and emotional composure
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className={`px-2.5 py-1 rounded-lg text-xs font-bold border ${
                      ((assessment.hr_evaluation.composure_evaluation?.overall_composure || assessment.composure_evaluation?.overall_composure) || "").includes("Composed")
                        ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-300"
                        : ((assessment.hr_evaluation.composure_evaluation?.overall_composure || assessment.composure_evaluation?.overall_composure) || "").includes("Mild")
                        ? "bg-amber-500/15 border-amber-500/30 text-amber-300"
                        : "bg-rose-500/15 border-rose-500/30 text-rose-300"
                    }`}>
                      {assessment.hr_evaluation.composure_evaluation?.overall_composure || assessment.composure_evaluation?.overall_composure}
                    </span>
                  </div>
                </div>

                {/* Metrics Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
                  <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
                    <p className="text-[11px] text-slate-400">Poise Score</p>
                    <p className="text-lg font-bold text-emerald-400">
                      {assessment.hr_evaluation.composure_evaluation?.poise_score ?? assessment.composure_evaluation?.poise_score ?? 8.5}/10
                    </p>
                    <p className="text-[10px] text-slate-500">Executive confidence rating</p>
                  </div>
                  <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
                    <p className="text-[11px] text-slate-400">Eye-Contact & Gaze Focus</p>
                    <p className="text-lg font-bold text-blue-400">
                      {assessment.hr_evaluation.composure_evaluation?.gaze_stability_pct ?? assessment.composure_evaluation?.gaze_stability_pct ?? 90}%
                    </p>
                    <p className="text-[10px] text-slate-500">Forward focus vs. darting</p>
                  </div>
                  <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
                    <p className="text-[11px] text-slate-400">Physical Restlessness</p>
                    <p className="text-lg font-bold text-purple-400">
                      {assessment.hr_evaluation.composure_evaluation?.fidget_index || assessment.composure_evaluation?.fidget_index || "Low / Grounded"}
                    </p>
                    <p className="text-[10px] text-slate-500">Micro-motion & posture stability</p>
                  </div>
                </div>

                {/* HR Recruiter Observations */}
                <div className="rounded-lg border border-slate-800/80 bg-slate-900/40 p-3">
                  <p className="text-xs text-slate-300 leading-relaxed">
                    <strong className="text-slate-200">HR Observation: </strong>
                    {assessment.hr_evaluation.composure_evaluation?.hr_observations || assessment.composure_evaluation?.hr_observations}
                  </p>
                  {((assessment.hr_evaluation.composure_evaluation?.stress_indicators || assessment.composure_evaluation?.stress_indicators) ?? []).length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {(assessment.hr_evaluation.composure_evaluation?.stress_indicators || assessment.composure_evaluation?.stress_indicators || []).map((indicator, iIdx) => (
                        <span key={iIdx} className="rounded-md bg-slate-800/80 px-2 py-0.5 text-[10px] text-slate-300 border border-slate-700">
                          ✓ {indicator}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Privacy compliance tag */}
                <p className="mt-2.5 text-[10px] text-slate-500 flex items-center gap-1.5">
                  <span>🛡️ Privacy Protection:</span>
                  <span>Zero raw video is recorded or retained. Biometric composure telemetry is encrypted at rest using AES-256 Fernet in compliance with global data protection standards.</span>
                </p>
              </div>
            )}
          </section>
        )}

        {/* ── Interview Plan & Curriculum Execution Card ── */}
        {assessment.interview_plan && (
          <section className="mb-6 rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <span>🗺</span>
                  <span>Agent Interview Plan & Curriculum Execution</span>
                </h2>
                <p className="text-xs text-slate-400 mt-1">
                  Structured 3-stage curriculum planned from resume & role specifications
                </p>
              </div>
              <span className="rounded-full bg-blue-500/10 border border-blue-500/30 px-3 py-1 text-xs font-semibold text-blue-400">
                3-Stage Curriculum
              </span>
            </div>

            {/* Target Tech Stack */}
            {assessment.interview_plan.tech_stack.length > 0 && (
              <div className="mb-4 rounded-xl border border-slate-800 bg-slate-950 p-3.5">
                <p className="text-xs font-semibold uppercase text-slate-400 tracking-wider mb-2">
                  Multi-Stack Focus Areas Evaluated:
                </p>
                <div className="flex flex-wrap gap-2">
                  {assessment.interview_plan.tech_stack.map((t, idx) => (
                    <span key={idx} className="rounded-lg bg-blue-500/15 border border-blue-500/30 px-2.5 py-1 text-xs font-medium text-blue-300">
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Stages Grid */}
            <div className="grid gap-3.5 sm:grid-cols-3">
              {assessment.interview_plan.stages.map((stage, idx) => (
                <div key={idx} className="rounded-xl border border-slate-800 bg-slate-950 p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-slate-200">{stage.stage_name}</span>
                    <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] font-semibold text-slate-300">
                      {stage.question_count} Qs
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    Target: {stage.focus_skills.join(", ") || "Stack fundamentals"}
                  </p>
                  {stage.resume_reference && (
                    <p className="mt-2 text-[11px] text-slate-500 border-t border-slate-800/80 pt-1.5">
                      Investigated: {stage.resume_reference}
                    </p>
                  )}
                </div>
              ))}
            </div>

            {/* Company Needs Note */}
            {assessment.company_needs && (
              <div className="mt-4 rounded-xl border border-purple-500/20 bg-purple-500/5 p-3.5 text-xs text-purple-200">
                🏢 <strong className="text-white">Target Company Focus:</strong> {assessment.company_needs}
              </div>
            )}
          </section>
        )}

        {/* Competency Scores Breakdown */}
        <section className="mb-6 rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-xl">
          <h2 className="mb-4 text-xl font-bold text-white">Competency Breakdown</h2>

          {assessment.competency_scores.length === 0 ? (
            <p className="text-sm text-slate-400">No competency scores recorded.</p>
          ) : (
            <div className="space-y-4">
              {assessment.competency_scores.map((item) => (
                <div key={item.skill}>
                  <div className="mb-1.5 flex justify-between text-sm">
                    <span className="font-semibold text-slate-300">{item.skill}</span>
                    <span className={`font-bold ${
                      item.score >= 7.5 ? "text-emerald-400" : item.score >= 5.0 ? "text-blue-400" : "text-amber-400"
                    }`}>
                      {item.score}/10
                    </span>
                  </div>
                  <div className="h-2.5 overflow-hidden rounded-full bg-slate-800">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${
                        item.score >= 7.5 ? "bg-emerald-500" : item.score >= 5.0 ? "bg-blue-500" : "bg-amber-500"
                      }`}
                      style={{ width: `${Math.min(100, item.score * 10)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Strengths & Gaps */}
        <div className="grid gap-6 md:grid-cols-2">
          <section className="rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-xl">
            <h2 className="mb-4 text-lg font-bold text-emerald-400 flex items-center gap-2">
              <span>✓</span>
              <span>Observed Strengths</span>
            </h2>
            <ul className="space-y-2.5">
              {assessment.strengths.map((s, idx) => (
                <li key={idx} className="rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-3 text-xs sm:text-sm text-emerald-300">
                  ✓ {s}
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-xl">
            <h2 className="mb-4 text-lg font-bold text-amber-400 flex items-center gap-2">
              <span>⚠</span>
              <span>Identified Gaps & Follow-ups</span>
            </h2>
            <ul className="space-y-2.5">
              {assessment.gaps.map((g, idx) => (
                <li key={idx} className="rounded-xl bg-amber-500/10 border border-amber-500/20 p-3 text-xs sm:text-sm text-amber-300">
                  ⚠ {g}
                </li>
              ))}
            </ul>
          </section>
        </div>

        {/* Recommendation Box */}
        <section className="mt-6 rounded-2xl border border-blue-500/30 bg-blue-500/10 p-6 shadow-xl">
          <p className="text-xs uppercase font-bold tracking-wider text-blue-400">Agent Recommendation</p>
          <h2 className="mt-1 text-2xl font-extrabold text-white">
            {assessment.recommendation}
          </h2>
        </section>

        {/* Visual & Engagement Signals */}
        <section className="mt-6 rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-xl">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <span>📹</span>
                <span>Visual & Facial Expression Verification</span>
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Observable engagement signals captured during candidate responses
              </p>
            </div>
            <span className="rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-xs text-blue-400 font-medium">
              Multimodal
            </span>
          </div>

          {assessment.visual_summary && assessment.visual_summary.turns_with_camera > 0 ? (
            <div>
              <div className="grid gap-4 sm:grid-cols-3 mb-4">
                <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
                  <p className="text-xs text-slate-400">Presence & Focus Rate</p>
                  <p className="mt-1 text-2xl font-bold text-emerald-400">
                    {assessment.visual_summary.presence_rate}%
                  </p>
                  <p className="text-[11px] text-slate-500 mt-1">Face present in frame</p>
                </div>

                <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
                  <p className="text-xs text-slate-400">Monitored Answer Turns</p>
                  <p className="mt-1 text-2xl font-bold text-blue-400">
                    {assessment.visual_summary.face_detected_turns} / {assessment.visual_summary.turns_with_camera}
                  </p>
                  <p className="text-[11px] text-slate-500 mt-1">Turns with confirmed presence</p>
                </div>

                <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
                  <p className="text-xs text-slate-400">Visual Engagement</p>
                  <p className="mt-1 text-lg font-bold text-slate-200">
                    {assessment.visual_summary.presence_rate >= 80
                      ? "High Engagement"
                      : assessment.visual_summary.presence_rate >= 50
                      ? "Moderate Engagement"
                      : "Low / Periodic Presence"}
                  </p>
                  <p className="text-[11px] text-emerald-400/80 mt-1">✓ Stable camera feed</p>
                </div>
              </div>

              <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-400 leading-relaxed">
                💡 <strong className="text-slate-300">Responsible AI Notice:</strong> {assessment.visual_summary.note}
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-slate-800/80 bg-slate-950/50 p-4 text-center">
              <p className="text-sm text-slate-300">Camera feed was not active during this interview session</p>
              <p className="mt-1 text-xs text-slate-500">
                Technical depth and problem-solving ability were verified via textual and voice answers.
              </p>
            </div>
          )}
        </section>

        {/* Security & Encryption Banner */}
        <section className="mt-6 rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-6">
          <div className="flex items-start gap-3">
            <span className="text-2xl">🔒</span>
            <div>
              <h3 className="text-base font-semibold text-emerald-300">
                End-to-End Cryptographic Security & Privacy
              </h3>
              <p className="mt-1 text-xs text-slate-400 leading-relaxed">
                Candidate identity and resume contents were encrypted using <strong className="text-slate-300">AES-256 (Fernet)</strong> symmetric encryption at rest.
                No unencrypted resume files or personally identifiable information (PII) were stored on disk.
              </p>
            </div>
          </div>
        </section>

        {/* Navigation Footer */}
        <div className="mt-8 flex flex-wrap items-center gap-4">
          <a
            href="/"
            className="rounded-xl border border-slate-700 bg-slate-900 px-6 py-3 font-semibold text-slate-300 transition hover:bg-slate-800"
          >
            ← Start New Evaluation
          </a>
          <button
            id="download-pdf-btn-bottom"
            type="button"
            onClick={handleDownloadPdf}
            disabled={downloadingPdf}
            className="flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white shadow-lg shadow-blue-600/30 transition hover:bg-blue-500 disabled:opacity-50"
          >
            {downloadingPdf ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                <span>Generating PDF...</span>
              </>
            ) : (
              <>
                <span>📥</span>
                <span>Download Official PDF Report</span>
              </>
            )}
          </button>
          <button
            type="button"
            onClick={() => window.print()}
            className="rounded-xl border border-slate-700 bg-slate-900 px-5 py-3 text-sm font-semibold text-slate-400 transition hover:bg-slate-800"
          >
            🖨 Print
          </button>
        </div>

      </div>
    </main>
  );
}