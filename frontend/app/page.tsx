"use client";

import { useState } from "react";

type UploadStep =
  | "idle"
  | "creating"
  | "uploading-resume"
  | "uploading-jd"
  | "planning"
  | "starting"
  | "done";

export default function Home() {
  const [candidateName, setCandidateName] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [companyNeeds, setCompanyNeeds] = useState("");
  const [goal, setGoal] = useState("Full Evaluation");
  const [duration, setDuration] = useState("30");
  const [geminiApiKey, setGeminiApiKey] = useState("");
  const [showKeyInput, setShowKeyInput] = useState(false);

  // Resume state (REQUIRED)
  const [resumeFile, setResumeFile] = useState<File | null>(null);

  // Job description state (File or Text)
  const [jdMode, setJdMode] = useState<"file" | "text">("text");
  const [jobDescFile, setJobDescFile] = useState<File | null>(null);
  const [jobDescText, setJobDescText] = useState("");

  // Resume parsing feedback
  const [resumeSkills, setResumeSkills] = useState<string[]>([]);
  const [resumeTech, setResumeTech] = useState<string[]>([]);

  const [error, setError] = useState("");
  const [step, setStep] = useState<UploadStep>("idle");

  const isLoading = step !== "idle" && step !== "done";

  const stepLabel: Record<UploadStep, string> = {
    idle: "",
    creating: "Creating secure interview session...",
    "uploading-resume": "Parsing & encrypting resume...",
    "uploading-jd": "Syncing role & company requirements...",
    planning: "Agent synthesizing 3-stage curriculum plan...",
    starting: "Launching adaptive interview...",
    done: "Redirecting...",
  };

  const startInterview = async () => {
    setError("");

    if (!candidateName.trim()) {
      setError("Please enter your name to continue.");
      return;
    }

    // MANDATORY resume check
    if (!resumeFile) {
      setError("A resume is required. Please upload your PDF or DOCX resume.");
      return;
    }

    try {
      // ── Step 1: Create interview session ───────────────────────────
      setStep("creating");
      const params = new URLSearchParams({
        candidate_name: candidateName.trim(),
        goal,
        duration_minutes: duration,
      });
      if (companyName.trim()) params.append("company_name", companyName.trim());
      if (companyNeeds.trim()) params.append("company_needs", companyNeeds.trim());
      if (jobTitle.trim()) params.append("job_title", jobTitle.trim());
      if (geminiApiKey.trim()) params.append("gemini_api_key", geminiApiKey.trim());

      const createRes = await fetch(`http://127.0.0.1:8000/interviews/?${params.toString()}`, {
        method: "POST",
      });

      if (!createRes.ok) {
        throw new Error("Failed to create interview session.");
      }
      const interview = await createRes.json();
      const interviewId = interview.interview_id;

      // ── Step 2: Upload and parse resume (REQUIRED) ────────────────
      setStep("uploading-resume");
      const resumeFormData = new FormData();
      resumeFormData.append("file", resumeFile);

      const resumeRes = await fetch(
        `http://127.0.0.1:8000/interviews/${interviewId}/resume`,
        { method: "POST", body: resumeFormData }
      );

      if (!resumeRes.ok) {
        const detail = await resumeRes.json().catch(() => ({}));
        throw new Error(
          detail?.detail ?? "Resume upload failed. Please upload a valid PDF or DOCX file."
        );
      }

      const resumeData = await resumeRes.json();
      setResumeSkills(resumeData.skills_detected ?? []);
      setResumeTech(resumeData.technologies_detected ?? []);

      // ── Step 3: Attach Job Description & Company Details ──────────
      if (jobDescFile || jobDescText.trim() || companyName.trim() || companyNeeds.trim() || jobTitle.trim()) {
        setStep("uploading-jd");
        const jdFormData = new FormData();
        if (jdMode === "file" && jobDescFile) {
          jdFormData.append("file", jobDescFile);
        } else if (jdMode === "text" && jobDescText.trim()) {
          jdFormData.append("text", jobDescText.trim());
        }
        if (jobTitle.trim()) jdFormData.append("job_title", jobTitle.trim());
        if (companyName.trim()) jdFormData.append("company_name", companyName.trim());
        if (companyNeeds.trim()) jdFormData.append("company_needs", companyNeeds.trim());

        await fetch(`http://127.0.0.1:8000/interviews/${interviewId}/job-description`, {
          method: "POST",
          body: jdFormData,
        }).catch((e) => console.warn("Job description attachment notice:", e));
      }

      // ── Step 4: Start interview & trigger autonomous curriculum planning ───
      setStep("planning");
      await new Promise((r) => setTimeout(r, 600));

      setStep("starting");
      const startRes = await fetch(
        `http://127.0.0.1:8000/interviews/${interviewId}/start`,
        { method: "POST" }
      );

      if (!startRes.ok) {
        const detail = await startRes.json().catch(() => ({}));
        throw new Error(detail?.detail ?? "Failed to start interview.");
      }

      const startedInterview = await startRes.json();
      sessionStorage.setItem("interview", JSON.stringify(startedInterview));

      setStep("done");
      window.location.href = "/interview";
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Could not connect to the backend server.";
      setError(message);
      setStep("idle");
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <div className="mx-auto max-w-7xl px-6 py-12">
        <div className="grid w-full gap-12 lg:grid-cols-12">

          {/* ── Left Column: Platform Overview & 3-Stage Curriculum ── */}
          <div className="flex flex-col justify-center lg:col-span-5">
            <div className="mb-6 flex items-center gap-3.5">
              <img
                src="/logo.png"
                alt="InterviewOne AI Logo"
                className="h-14 w-14 rounded-2xl border border-slate-700/80 shadow-lg shadow-indigo-500/10 object-cover"
              />
              <div>
                <div className="inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-xs font-semibold text-blue-300">
                  <span className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse" />
                  Agentic Talent Partner
                </div>
                <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight mt-1">
                  InterviewOne <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-400">AI</span>
                </h1>
              </div>
            </div>

            <p className="mt-4 text-base sm:text-lg leading-relaxed text-slate-300">
              An intelligent Agentic HR Interviewer that reviews your resume and conducts an authentic, structured talent screening. Starts with a warm candidate introduction, explores your key resume skills, assesses behavioral & culture fit (STAR method), and generates an official HR Candidate Grading Scorecard.
            </p>

            <p className="mt-2 text-sm text-slate-400">
              Adapts dynamically to candidate resume & role requirements across any tech stack — not just Python.
            </p>

            {/* Feature Badges */}
            <div className="mt-6 grid grid-cols-3 gap-3">
              <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3.5 text-center">
                <p className="text-xl font-bold text-blue-400">Grade A–D</p>
                <p className="mt-1 text-[11px] text-slate-400 font-medium">HR Scorecard</p>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3.5 text-center">
                <p className="text-xl font-bold text-emerald-400">🤝 Intro</p>
                <p className="mt-1 text-[11px] text-slate-400 font-medium">Simpler Start</p>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3.5 text-center">
                <p className="text-xl font-bold text-purple-400">🔒 AES-256</p>
                <p className="mt-1 text-[11px] text-slate-400 font-medium">Encrypted PII</p>
              </div>
            </div>

            {/* 3-Stage Curriculum Blueprint */}
            <div className="mt-8 space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Agentic HR Interview Methodology
              </p>

              <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-emerald-400">Stage 1: HR Welcome & Career Intro (Simpler Start)</span>
                  <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-[10px] font-semibold text-emerald-300">10 Questions</span>
                </div>
                <p className="mt-1.5 text-xs text-slate-400 leading-relaxed">
                  Warm candidate introduction, career story walkthrough, role motivation, and core technical mechanics baseline in your stack.
                </p>
              </div>

              <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-amber-400">Stage 2: Resume Skills & Architecture Tradeoffs</span>
                  <span className="rounded bg-amber-500/20 px-2 py-0.5 text-[10px] font-semibold text-amber-300">5 Questions</span>
                </div>
                <p className="mt-1.5 text-xs text-slate-400 leading-relaxed">
                  Hands-on verification of specific claims, projects, achievements, and technical decisions highlighted on your resume.
                </p>
              </div>

              <div className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-3.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-rose-400">Stage 3: Behavioral, Ownership & Culture Fit (STAR)</span>
                  <span className="rounded bg-rose-500/20 px-2 py-0.5 text-[10px] font-semibold text-rose-300">5 Questions</span>
                </div>
                <p className="mt-1.5 text-xs text-slate-400 leading-relaxed">
                  Cross-functional teamwork, conflict resolution, handling tight deadlines or outages, and long-term organizational alignment.
                </p>
              </div>
            </div>

            {/* AI Engine Status indicator */}
            <div className="mt-6 flex items-center gap-2.5 rounded-xl border border-slate-800 bg-slate-900/50 px-4 py-3 text-xs text-slate-400">
              <span className="text-base">✨</span>
              <span>
                <strong className="text-slate-200">Google Gemini 2.0 Flash</strong> connected. Evaluates candidate depth and adjusts questions dynamically.
              </span>
            </div>
          </div>

          {/* ── Right Column: Interactive Setup Form ── */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-7 sm:p-9 shadow-2xl lg:col-span-7">
            <div className="flex items-center justify-between border-b border-slate-800 pb-5">
              <div>
                <h2 className="text-2xl font-bold text-white">Interview Configuration</h2>
                <p className="mt-1 text-xs sm:text-sm text-slate-400">
                  Target candidate profile, resume, and role alignment.
                </p>
              </div>
              <span className="rounded-full bg-blue-500/10 border border-blue-500/30 px-3 py-1 text-xs font-semibold text-blue-400">
                Setup
              </span>
            </div>

            {/* Error Banner */}
            {error && (
              <div className="mt-5 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3.5 text-sm text-red-300 flex items-start gap-2.5">
                <span className="text-base">⚠</span>
                <span>{error}</span>
              </div>
            )}

            {/* Progress Step Banner */}
            {isLoading && (
              <div className="mt-5 flex items-center gap-3 rounded-xl border border-blue-500/30 bg-blue-500/10 px-4 py-3.5">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-600 border-t-blue-400 shrink-0" />
                <p className="text-sm font-medium text-blue-300">{stepLabel[step]}</p>
              </div>
            )}

            <div className="mt-6 space-y-5">

              {/* Candidate Full Name */}
              <div>
                <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Candidate Name <span className="text-red-400">*</span>
                </label>
                <input
                  id="candidate-name"
                  type="text"
                  value={candidateName}
                  onChange={(e) => {
                    setCandidateName(e.target.value);
                    if (error) setError("");
                  }}
                  placeholder="e.g. Alex Morgan"
                  disabled={isLoading}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm outline-none transition focus:border-blue-500 disabled:opacity-50"
                />
              </div>

              {/* Target Job Title / Role */}
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-slate-300">
                    Target Role / Job Title
                  </label>
                  <input
                    id="job-title"
                    type="text"
                    value={jobTitle}
                    onChange={(e) => setJobTitle(e.target.value)}
                    placeholder="e.g. Full Stack Engineer (React/Node)"
                    disabled={isLoading}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm outline-none transition focus:border-blue-500 disabled:opacity-50"
                  />
                </div>

                {/* Company Name */}
                <div>
                  <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-slate-300">
                    Target Company
                  </label>
                  <input
                    id="company-name"
                    type="text"
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    placeholder="e.g. Google / Stripe / Startup"
                    disabled={isLoading}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm outline-none transition focus:border-blue-500 disabled:opacity-50"
                  />
                </div>
              </div>

              {/* Company Architectural Needs */}
              <div>
                <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Company Needs & Architectural Focus <span className="text-xs font-normal text-slate-500">(Optional)</span>
                </label>
                <input
                  id="company-needs"
                  type="text"
                  value={companyNeeds}
                  onChange={(e) => setCompanyNeeds(e.target.value)}
                  placeholder="e.g. High scalability, microservices, 99.999% SLA, low latency checkout"
                  disabled={isLoading}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm outline-none transition focus:border-blue-500 disabled:opacity-50"
                />
              </div>

              {/* Resume Upload — MANDATORY */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                    Candidate Resume <span className="text-red-400">* Required</span>
                  </label>
                  <span className="text-[11px] text-slate-500">PDF or DOCX</span>
                </div>

                <label
                  htmlFor="resume-upload"
                  className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center transition ${
                    resumeFile
                      ? "border-emerald-500/60 bg-emerald-500/10"
                      : "border-slate-700 hover:border-blue-500/60 hover:bg-blue-500/5"
                  } ${isLoading ? "pointer-events-none opacity-50" : ""}`}
                >
                  <span className="text-3xl mb-1.5">{resumeFile ? "✅" : "📄"}</span>
                  <p className="text-sm font-semibold text-slate-200">
                    {resumeFile ? resumeFile.name : "Click to select or drop resume"}
                  </p>
                  <p className="text-xs text-slate-500 mt-1">
                    Questions will be dynamically synthesized from skills and projects in this resume
                  </p>
                  <input
                    id="resume-upload"
                    type="file"
                    accept=".pdf,.doc,.docx"
                    className="hidden"
                    disabled={isLoading}
                    onChange={(e) => {
                      setResumeFile(e.target.files?.[0] ?? null);
                      setResumeSkills([]);
                      setResumeTech([]);
                      if (error) setError("");
                    }}
                  />
                </label>

                {/* Parsed resume preview */}
                {(resumeSkills.length > 0 || resumeTech.length > 0) && (
                  <div className="mt-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3">
                    <p className="text-xs font-semibold text-emerald-400 mb-1.5">✓ Resume Verified & Parsed</p>
                    <div className="flex flex-wrap gap-1.5">
                      {[...resumeSkills, ...resumeTech].slice(0, 10).map((s, i) => (
                        <span key={i} className="rounded-md bg-slate-900 px-2 py-0.5 text-[11px] text-slate-300 border border-slate-700">
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <p className="mt-2 flex items-center gap-1.5 text-[11px] text-slate-500">
                  <span>🔒</span>
                  <span>Candidate name and resume text are encrypted via AES-256 (Fernet) at rest.</span>
                </p>
              </div>

              {/* Job Description (Toggle: Text vs File) */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                    Target Job Description <span className="text-xs font-normal text-slate-500">(Optional)</span>
                  </label>
                  <div className="flex items-center gap-1 rounded-lg border border-slate-800 bg-slate-950 p-0.5 text-[11px]">
                    <button
                      type="button"
                      onClick={() => setJdMode("text")}
                      className={`rounded px-2.5 py-1 transition ${
                        jdMode === "text" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"
                      }`}
                    >
                      Paste Text
                    </button>
                    <button
                      type="button"
                      onClick={() => setJdMode("file")}
                      className={`rounded px-2.5 py-1 transition ${
                        jdMode === "file" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"
                      }`}
                    >
                      Upload File
                    </button>
                  </div>
                </div>

                {jdMode === "text" ? (
                  <textarea
                    id="job-description-text"
                    value={jobDescText}
                    onChange={(e) => setJobDescText(e.target.value)}
                    placeholder="Paste job description requirements, qualifications, or key technologies here..."
                    rows={3}
                    disabled={isLoading}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-xs sm:text-sm text-slate-300 outline-none focus:border-blue-500 disabled:opacity-50"
                  />
                ) : (
                  <div>
                    <input
                      id="job-description-upload"
                      type="file"
                      accept=".pdf,.doc,.docx,.txt,.md"
                      disabled={isLoading}
                      onChange={(e) => setJobDescFile(e.target.files?.[0] ?? null)}
                      className="w-full rounded-xl border border-dashed border-slate-700 bg-slate-950 p-3 text-xs text-slate-400 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-800 file:px-3 file:py-1.5 file:text-xs file:text-white hover:file:bg-slate-700 disabled:opacity-50"
                    />
                    {jobDescFile && (
                      <p className="mt-1 text-xs text-emerald-400">✓ {jobDescFile.name}</p>
                    )}
                  </div>
                )}
              </div>

              {/* Duration and Goal */}
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-slate-300">
                    Evaluation Goal
                  </label>
                  <select
                    value={goal}
                    disabled={isLoading}
                    onChange={(e) => setGoal(e.target.value)}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2.5 text-sm outline-none focus:border-blue-500 disabled:opacity-50"
                  >
                    <option value="Full Evaluation">Full Technical & Architecture</option>
                    <option value="Technical">Technical Depth & Code Trace</option>
                    <option value="System Design">System Design & Edge Cases</option>
                  </select>
                </div>

                <div>
                  <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-slate-300">
                    Session Duration
                  </label>
                  <select
                    value={duration}
                    disabled={isLoading}
                    onChange={(e) => setDuration(e.target.value)}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2.5 text-sm outline-none focus:border-blue-500 disabled:opacity-50"
                  >
                    <option value="15">15 minutes (Express)</option>
                    <option value="30">30 minutes (Standard 20 Qs)</option>
                    <option value="45">45 minutes (In-depth)</option>
                    <option value="60">60 minutes (Comprehensive)</option>
                  </select>
                </div>
              </div>

              {/* Custom Gemini API Key Collapsible (Optional) */}
              <div className="pt-1">
                <button
                  type="button"
                  onClick={() => setShowKeyInput(!showKeyInput)}
                  className="text-xs text-slate-400 hover:text-blue-400 transition flex items-center gap-1.5"
                >
                  <span>⚙</span>
                  <span>{showKeyInput ? "Hide Custom Gemini Key" : "Custom Gemini API Key (Optional Override)"}</span>
                </button>

                {showKeyInput && (
                  <div className="mt-2 rounded-xl border border-slate-800 bg-slate-950/80 p-3">
                    <p className="text-[11px] text-slate-400 mb-2">
                      The server is pre-configured with Gemini 2.0 Flash. Enter a custom key only if you wish to override:
                    </p>
                    <input
                      type="password"
                      value={geminiApiKey}
                      onChange={(e) => setGeminiApiKey(e.target.value)}
                      placeholder="AQ.Ab8RN6Ip... or custom key"
                      className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs font-mono text-slate-200 outline-none focus:border-blue-500"
                    />
                  </div>
                )}
              </div>

              {/* Start Button */}
              <button
                id="start-interview-button"
                onClick={startInterview}
                disabled={isLoading}
                className="mt-6 w-full rounded-xl bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 px-6 py-4 font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50 shadow-lg shadow-blue-500/20"
              >
                {isLoading ? (
                  <span className="flex items-center justify-center gap-2.5">
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                    {stepLabel[step]}
                  </span>
                ) : (
                  "Generate Plan & Start Interview →"
                )}
              </button>

              {!resumeFile && (
                <p className="text-center text-xs text-amber-400 font-medium">
                  ⚠ Resume upload is required so the agent can build your tailored 20-question plan.
                </p>
              )}

            </div>
          </div>

        </div>
      </div>
    </main>
  );
}