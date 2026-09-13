from pydantic import BaseModel, Field
from typing import Optional, List


class AnswerRecord(BaseModel):
    question: str
    answer: str
    encrypted_answer: Optional[str] = None     # Fernet AES-256 encrypted answer text
    skill: Optional[str] = None
    depth: Optional[str] = None               # shallow / surface / intermediate / deep
    agent_action: Optional[str] = None         # PROBE_DEEPER / INVESTIGATE_FUNDAMENTALS etc.


class VisualSignal(BaseModel):
    """Observable camera signals and composure indicators for a single answer turn."""
    face_detected: Optional[bool] = None
    gaze_direction: Optional[str] = None       # forward / left / right / down / up
    head_orientation: Optional[str] = None     # centered / tilted / turned
    motion_level: Optional[float] = None       # 0–1 movement magnitude
    lighting_quality: Optional[float] = None   # 0–1 lighting score
    note: Optional[str] = None                 # Human-readable summary

    # HR Non-Verbal Composure & Tension Metrics
    composure_state: Optional[str] = None      # "composed", "mild_tension", "elevated_anxiety"
    tension_score: Optional[float] = None      # 0.0 (calm) to 1.0 (high stress)
    fidget_level: Optional[float] = None       # 0.0 (grounded) to 1.0 (restless)
    gaze_stability: Optional[float] = None     # 0.0 to 1.0 (steady eye contact)
    blink_rate_indicator: Optional[str] = None # "normal", "elevated", "rapid"
    encrypted_telemetry: Optional[str] = None  # Fernet AES-256 encrypted raw biometric metrics


class HRComposureEvaluation(BaseModel):
    """Aggregate HR evaluation of candidate non-verbal composure, poise, and stress control."""
    overall_composure: str = "Composed & Confident"  # "Composed & Confident", "Mild Tension / Processing", "Elevated Anxiety / Restless"
    poise_score: float = 8.5                        # 0.0 - 10.0
    gaze_stability_pct: int = 85                    # 0 - 100%
    fidget_index: str = "Low / Grounded"            # "Low / Grounded", "Moderate", "High Restlessness"
    stress_indicators: List[str] = Field(default_factory=list)
    hr_observations: str = "Maintained excellent composure and steady focus throughout technical questioning."
    encryption_status: str = "AES-256 Encrypted at Rest (Zero Raw Video Stored)"


class ResumeProfile(BaseModel):
    """Extracted resume facts used to personalise question selection."""
    skills: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    experience: List[str] = Field(default_factory=list)
    projects: List[str] = Field(default_factory=list)
    education: List[str] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)


class PlannedStage(BaseModel):
    stage_name: str                            # e.g. "Fundamentals & Logic", "System Architecture", "Tricky Edge Cases"
    difficulty: str                            # easy / moderate / tricky
    focus_skills: List[str] = Field(default_factory=list)
    question_count: int = 5
    resume_reference: Optional[str] = None     # Specific resume project/claim to investigate
    job_reference: Optional[str] = None        # Matching job description requirement


class InterviewPlan(BaseModel):
    role_title: str = "Software Engineer"
    tech_stack: List[str] = Field(default_factory=list)
    company_focus: str = "Technical Depth & Engineering Judgment"
    stages: List[PlannedStage] = Field(default_factory=list)
    total_questions: int = 20
    planned_summary: str = "Personalized interview plan generated from resume and job details"


class HRCompetencyGrade(BaseModel):
    category: str                               # e.g. "Introduction & Communication", "Resume Claim Verification", "Technical Competency", "Behavioral & Culture Fit", "Ownership & Leadership"
    grade: str                                  # A+, A, B+, B, C, D
    score: float                                # 0.0 - 10.0
    feedback: str                               # HR observation / feedback


class HREvaluation(BaseModel):
    overall_grade: str                          # A+, A, B+, B, C, D
    overall_score: float                        # 0.0 - 10.0
    hiring_recommendation: str                  # "Strong Hire - Fast-track to Final Rounds", "Hire", "Lean Hire", "No Hire"
    candidate_summary: str                      # Executive HR summary of the candidate
    intro_grade: str = "A"                      # Grade for self-introduction & communication
    skills_grade: str = "B+"                    # Grade for resume skills & technical depth
    behavioral_grade: str = "A"                 # Grade for culture fit, teamwork & ownership
    competencies: List[HRCompetencyGrade] = Field(default_factory=list)
    composure_evaluation: Optional[HRComposureEvaluation] = None


class InterviewState(BaseModel):
    interview_id: str
    candidate_name: str                         # Stored encrypted at rest (see interviews.py)

    goal: str = "Full Evaluation"
    duration_minutes: int = 30

    status: str = "created"

    current_question: Optional[str] = None
    current_skill: Optional[str] = None
    current_difficulty: Optional[str] = None   # easy / moderate / tricky

    question_number: int = 0

    answers: List[AnswerRecord] = Field(default_factory=list)

    evidence: List[str] = Field(default_factory=list)
    evidence_gap: Optional[str] = None
    next_action: Optional[str] = None

    # Resume-based personalisation
    resume_profile: Optional[ResumeProfile] = None
    resume_available: bool = False

    # Visual signals logged per answer turn
    visual_signals: List[VisualSignal] = Field(default_factory=list)

    # Encrypted PII fields (Fernet-encrypted, base64 strings)
    encrypted_name: Optional[str] = None       # encrypted candidate_name
    encrypted_resume_text: Optional[str] = None  # encrypted raw resume text

    # Company, Role, and Job Description context
    company_name: Optional[str] = None
    company_needs: Optional[str] = None
    job_title: Optional[str] = None
    job_description: Optional[str] = None

    # AI engine configuration & generated plan
    gemini_api_key: Optional[str] = None
    ai_powered: bool = False
    interview_plan: Optional[InterviewPlan] = None

    # HR Talent Partner Assessment & Scorecard
    hr_evaluation: Optional[HREvaluation] = None
    composure_evaluation: Optional[HRComposureEvaluation] = None
    interview_type: str = "hr_technical"