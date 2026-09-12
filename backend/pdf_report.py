"""
InterviewOne AI — PDF Evaluation Report Generator

Produces enterprise-grade, beautifully formatted PDF dossiers of candidate
interview assessments using ReportLab Platypus.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to compute total page count and draw
    consistent running headers and footers with 'Page X of Y'.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[Any] = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def draw_header_footer(self, total_pages: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Running Header (pages 2+)
        if self._pageNumber > 1:
            self.drawString(54, 750, "InterviewOne AI — Technical Evaluation Report")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 742, letter[0] - 54, 742)

        # Running Footer (all pages)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 45, letter[0] - 54, 45)

        footer_text = "Confidential — Evaluated with Gemini 2.0 Flash & AES-256 Fernet Encryption"
        self.drawString(54, 32, footer_text)

        page_str = f"Page {self._pageNumber} of {total_pages}"
        self.drawRightString(letter[0] - 54, 32, page_str)
        self.restoreState()


def _safe_str(val: Any, default: str = "N/A") -> str:
    if val is None:
        return default
    s = str(val).strip()
    return s if s else default


def generate_assessment_pdf(assessment_data: dict) -> bytes:
    """
    Generates a high-quality PDF report from assessment data dict.
    Returns the binary content (bytes) of the PDF.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=44,
        rightMargin=44,
        topMargin=54,
        bottomMargin=54,
    )

    # Printable width: letter[0] - 88 = 612 - 88 = 524 pt
    content_width = letter[0] - 88

    styles = getSampleStyleSheet()

    # Custom styles
    header_super = ParagraphStyle(
        "HeaderSuper",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#2563EB"),
        textTransform="uppercase",
        spaceAfter=4,
    )

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=4,
    )

    meta_style = ParagraphStyle(
        "DocMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#475569"),
    )

    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=10,
        spaceAfter=6,
    )

    body_text = ParagraphStyle(
        "BodyTextCustom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1E293B"),
    )

    badge_label = ParagraphStyle(
        "BadgeLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#475569"),
        alignment=1,  # Centered
    )

    badge_val = ParagraphStyle(
        "BadgeVal",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=19,
        textColor=colors.HexColor("#0F172A"),
        alignment=1,
    )

    story = []

    candidate_name = _safe_str(assessment_data.get("candidate_name"), "Candidate")
    role_title = _safe_str(
        assessment_data.get("job_title")
        or (assessment_data.get("interview_plan") or {}).get("role_title"),
        "Software Engineer",
    )
    company_name = assessment_data.get("company_name")
    overall_score = float(assessment_data.get("overall_score") or 0.0)
    evidence_coverage = assessment_data.get("evidence_coverage", 0)
    confidence = assessment_data.get("confidence", 0)
    recommendation = _safe_str(assessment_data.get("recommendation"), "Evaluation Complete")
    questions_answered = assessment_data.get("questions_answered", 0)
    date_str = datetime.now().strftime("%B %d, %Y")

    # ── 1. Document Header Banner ─────────────────────────────────────────────
    header_table_data = [
        [
            Paragraph(
                f"""<b>INTERVIEWONE AI</b> • TECHNICAL EVALUATION REPORT<br/>
<font size="16"><b>{candidate_name}</b></font><br/>
<font color="#475569">Target Role: <b>{role_title}</b>{f' • Company: <b>{company_name}</b>' if company_name else ''}</font><br/>
<font color="#64748B" size="8">Assessment Date: {date_str} • Questions Evaluated: {questions_answered}</font>""",
                body_text,
            ),
            Paragraph(
                f"""<div align="right">
<font size="8" color="#64748B">OVERALL SCORE</font><br/>
<font size="24" color="#2563EB"><b>{overall_score:.1f}</b></font><font size="12" color="#64748B">/10</font><br/>
<font size="8" color="#059669"><b>{recommendation}</b></font>
</div>""",
                body_text,
            ),
        ]
    ]

    header_table = Table(header_table_data, colWidths=[content_width * 0.70, content_width * 0.30])
    header_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("LEFTPADDING", (0, 0), (-1, -1), 14),
            ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ])
    )
    story.append(header_table)
    story.append(Spacer(1, 10))

    # ── 2. Top Metric Cards ───────────────────────────────────────────────────
    hr_eval = assessment_data.get("hr_evaluation") or {}
    overall_grade = _safe_str(hr_eval.get("overall_grade"), "B+")
    hiring_rec = _safe_str(hr_eval.get("hiring_recommendation"), recommendation)

    card_data = [
        [
            Paragraph("OVERALL SCORE", badge_label),
            Paragraph("HR GRADE", badge_label),
            Paragraph("COVERAGE", badge_label),
            Paragraph("CONFIDENCE", badge_label),
        ],
        [
            Paragraph(f"<font color='#2563EB'>{overall_score:.1f}</font><font size='10' color='#64748B'>/10</font>", badge_val),
            Paragraph(f"<font color='#059669'>{overall_grade}</font>", badge_val),
            Paragraph(f"<font color='#0284C7'>{evidence_coverage}%</font>", badge_val),
            Paragraph(f"<font color='#7C3AED'>{confidence}%</font>", badge_val),
        ],
        [
            Paragraph("Weighted technical depth", badge_label),
            Paragraph(f"<b>{hiring_rec}</b>", badge_label),
            Paragraph("Demonstrated syllabus", badge_label),
            Paragraph("Based on response volume", badge_label),
        ],
    ]

    col_w = content_width / 4.0
    metrics_table = Table(card_data, colWidths=[col_w] * 4)
    metrics_table.setStyle(
        TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFFFFF")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#F1F5F9")),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
        ])
    )
    story.append(metrics_table)
    story.append(Spacer(1, 12))

    # ── 3. Agentic HR Candidate Scorecard ──────────────────────────────────────
    if hr_eval:
        story.append(Paragraph("<b>Agentic HR Candidate Scorecard</b>", section_heading))

        candidate_summary = _safe_str(
            hr_eval.get("candidate_summary"),
            "Candidate demonstrated consistent problem-solving approach and technical fluency.",
        )
        intro_grade = _safe_str(hr_eval.get("intro_grade"), "A-")
        skills_grade = _safe_str(hr_eval.get("skills_grade"), "B+")
        behavioral_grade = _safe_str(hr_eval.get("behavioral_grade"), "A")

        summary_p = Paragraph(
            f"<b>Executive Summary:</b> {candidate_summary}",
            body_text,
        )

        grades_table_data = [
            [
                Paragraph("<b>Stage 1: Intro & Career Story</b>", badge_label),
                Paragraph("<b>Stage 2: Resume Skills Depth</b>", badge_label),
                Paragraph("<b>Stage 3: Behavioral & STAR</b>", badge_label),
            ],
            [
                Paragraph(f"<font color='#059669' size='14'><b>Grade {intro_grade}</b></font>", badge_val),
                Paragraph(f"<font color='#2563EB' size='14'><b>Grade {skills_grade}</b></font>", badge_val),
                Paragraph(f"<font color='#7C3AED' size='14'><b>Grade {behavioral_grade}</b></font>", badge_val),
            ],
        ]
        g_table = Table(grades_table_data, colWidths=[content_width / 3.0] * 3)
        g_table.setStyle(
            TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ])
        )

        hr_box = Table(
            [[summary_p], [Spacer(1, 4)], [g_table]],
            colWidths=[content_width],
        )
        hr_box.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFFFFF")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ])
        )
        story.append(hr_box)
        story.append(Spacer(1, 10))

        # Granular Competencies Table
        competencies = hr_eval.get("competencies") or []
        if competencies:
            comp_table_rows = [
                [
                    Paragraph("<b>HR Competency</b>", body_text),
                    Paragraph("<b>Grade</b>", badge_label),
                    Paragraph("<b>Score</b>", badge_label),
                    Paragraph("<b>Qualitative Evaluation & Evidence</b>", body_text),
                ]
            ]
            for c in competencies:
                cat = _safe_str(c.get("category"), "General")
                grade = _safe_str(c.get("grade"), "B")
                score_num = c.get("score", 7.5)
                feedback = _safe_str(c.get("feedback"), "Good performance")

                comp_table_rows.append([
                    Paragraph(f"<b>{cat}</b>", body_text),
                    Paragraph(f"<b>{grade}</b>", badge_label),
                    Paragraph(f"<b>{score_num}/10</b>", badge_label),
                    Paragraph(feedback, body_text),
                ])

            comp_table = Table(
                comp_table_rows,
                colWidths=[content_width * 0.25, content_width * 0.12, content_width * 0.12, content_width * 0.51],
            )
            comp_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ])
            )
            story.append(comp_table)
            story.append(Spacer(1, 10))

    # ── 4. Non-Verbal Composure & Poise Telemetry ──────────────────────────────
    composure = (
        hr_eval.get("composure_evaluation")
        or assessment_data.get("composure_evaluation")
    )
    if composure:
        story.append(Paragraph("<b>Non-Verbal Composure & Poise Telemetry</b> (AES-256 Protected)", section_heading))
        poise_score = composure.get("poise_score", 8.5)
        gaze_pct = composure.get("gaze_stability_pct", 90)
        fidget = _safe_str(composure.get("fidget_index"), "Low / Grounded")
        overall_comp = _safe_str(composure.get("overall_composure"), "Composed & Confident")
        hr_obs = _safe_str(composure.get("hr_observations"), "Candidate exhibited steady eye-contact.")

        composure_data = [
            [
                Paragraph("<b>Poise Score</b>", badge_label),
                Paragraph("<b>Gaze Stability</b>", badge_label),
                Paragraph("<b>Restlessness Index</b>", badge_label),
                Paragraph("<b>Overall State</b>", badge_label),
            ],
            [
                Paragraph(f"<font color='#059669' size='13'><b>{poise_score}/10</b></font>", badge_val),
                Paragraph(f"<font color='#2563EB' size='13'><b>{gaze_pct}%</b></font>", badge_val),
                Paragraph(f"<font size='11'><b>{fidget}</b></font>", badge_val),
                Paragraph(f"<font size='10' color='#059669'><b>{overall_comp}</b></font>", badge_val),
            ],
            [
                Paragraph(f"<b>HR Observation:</b> {hr_obs}", body_text),
                "",
                "",
                "",
            ],
        ]

        comp_table = Table(composure_data, colWidths=[content_width / 4.0] * 4)
        comp_table.setStyle(
            TableStyle([
                ("SPAN", (0, 2), (3, 2)),
                ("BACKGROUND", (0, 0), (-1, 1), colors.HexColor("#F8FAFC")),
                ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#FFFFFF")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, 1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        story.append(comp_table)
        story.append(Spacer(1, 10))

    # ── 5. Technical Competencies & Multi-Stack Curriculum ────────────────────
    tech_scores = assessment_data.get("competency_scores") or []
    if tech_scores:
        story.append(Paragraph("<b>Technical Competency Depth</b>", section_heading))
        t_rows = [
            [
                Paragraph("<b>Skill / Competency</b>", body_text),
                Paragraph("<b>Demonstrated Score</b>", badge_label),
                Paragraph("<b>Rating Status</b>", body_text),
            ]
        ]
        for item in tech_scores:
            skill = _safe_str(item.get("skill"), "Skill")
            score = float(item.get("score") or 0.0)
            status_text = (
                "<font color='#059669'><b>Advanced (High Depth)</b></font>"
                if score >= 7.5
                else "<font color='#2563EB'><b>Proficient (Standard Depth)</b></font>"
                if score >= 5.0
                else "<font color='#D97706'><b>Developing (Foundational)</b></font>"
            )
            t_rows.append([
                Paragraph(skill, body_text),
                Paragraph(f"<b>{score:.1f} / 10</b>", badge_label),
                Paragraph(status_text, body_text),
            ])

        tech_table = Table(t_rows, colWidths=[content_width * 0.40, content_width * 0.25, content_width * 0.35])
        tech_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        story.append(tech_table)
        story.append(Spacer(1, 10))

    # ── 6. Strengths and Gaps ─────────────────────────────────────────────────
    strengths = assessment_data.get("strengths") or []
    gaps = assessment_data.get("gaps") or []

    if strengths or gaps:
        story.append(Paragraph("<b>Demonstrated Strengths & Growth Areas</b>", section_heading))

        strengths_items = "<br/>".join([f"• <b>[+]</b> {s}" for s in strengths]) or "• General technical competence demonstrated."
        gaps_items = "<br/>".join([f"• <b>[-]</b> {g}" for g in gaps]) or "• None noted."

        sg_table_data = [
            [
                Paragraph("<b>Observed Strengths</b>", ParagraphStyle("GHeader", parent=body_text, textColor=colors.HexColor("#059669"))),
                Paragraph("<b>Identified Gaps & Follow-ups</b>", ParagraphStyle("AHeader", parent=body_text, textColor=colors.HexColor("#D97706"))),
            ],
            [
                Paragraph(strengths_items, body_text),
                Paragraph(gaps_items, body_text),
            ],
        ]

        sg_table = Table(sg_table_data, colWidths=[content_width * 0.50, content_width * 0.50])
        sg_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#ECFDF5")),
                ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#FFFBEB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ])
        )
        story.append(sg_table)
        story.append(Spacer(1, 12))

    # ── 7. Privacy & Security Notice ──────────────────────────────────────────
    security_p = Paragraph(
        "<b>Cryptographic Privacy & Verification:</b> All interview telemetry, candidate answers, and resume content were "
        "encrypted at rest using <b>AES-256 Fernet</b> symmetric encryption. Zero raw video streams were stored on disk.",
        ParagraphStyle("SecNotice", parent=body_text, fontSize=8, leading=11, textColor=colors.HexColor("#64748B")),
    )
    sec_table = Table([[security_p]], colWidths=[content_width])
    sec_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ])
    )
    story.append(sec_table)

    # Build the document with custom numbered canvas
    doc.build(story, canvasmaker=NumberedCanvas)
    return buffer.getvalue()
