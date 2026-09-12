"""
Report Generator for InterviewOne AI (Person 3).
Transforms the structured FinalAssessmentReport into executive-ready
Markdown and HTML hiring dossiers.
"""

import json
from pathlib import Path
from typing import Tuple
from .schemas import FinalAssessmentReport, EvidenceStatus


class ReportGenerator:
    """Generates auditable, evidence-backed hiring reports in Markdown and HTML."""

    @staticmethod
    def generate_markdown(report: FinalAssessmentReport) -> str:
        """Produces a comprehensive Markdown hiring assessment."""
        verdict_badge = {
            "Strong Hire": "🟢 **STRONG HIRE**",
            "Hire": "🟢 **HIRE**",
            "Lean Hire": "🟡 **LEAN HIRE**",
            "Lean Reject": "🟠 **LEAN REJECT**",
            "Reject": "🔴 **REJECT**",
        }.get(report.overall_recommendation, f"⚪ **{report.overall_recommendation}**")

        guardrail_notice = ""
        if report.unsupported_score_prevention_applied:
            guardrail_notice = (
                "> [!NOTE]\n"
                "> **Integrity Guardrail Applied:** One or more scores were capped because the candidate "
                "lacked verified intermediate/advanced evidence to justify an advanced rating.\n\n"
            )

        # Build Competency Table
        comp_rows = []
        for name, comp in report.competency_breakdown.items():
            status_emoji = "✅" if comp.status == EvidenceStatus.WELL_TESTED else "🟡" if comp.status == EvidenceStatus.PARTIALLY_TESTED else "⚠️"
            evidence_snippets = "<br>".join([f"• {e.demonstrated_fact} (depth: *{e.depth_level.value}*)" for e in comp.evidence_list[:2]]) or "*No evidence demonstrated*"
            comp_rows.append(
                f"| **{name}** | {comp.priority:.1f} | **{comp.score:.1f} / 5.0** | {comp.confidence:.2f} | {status_emoji} {comp.status.value.replace('_', ' ').title()} | {evidence_snippets} |"
            )
        comp_table = "\n".join(comp_rows)

        # Build Strengths & Gaps
        strengths_list = "\n".join([f"- {s}" for s in report.key_strengths])
        gaps_list = "\n".join([f"- {g}" for g in report.critical_gaps])

        # Build Contradictions & Claims section
        claims_summary = (
            f"- **Verified Claims:** {report.verified_claims_count}\n"
            f"- **Unverified / Disputed Claims:** {report.unverified_claims_count}\n"
        )

        contradictions_section = "None detected during interview session."
        if report.contradictions_found:
            c_items = []
            for c in report.contradictions_found:
                severity_badge = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(c.severity, "⚪")
                resolved_label = "✅ Resolved" if c.resolved else "❌ Unresolved"
                c_items.append(
                    f"#### {severity_badge} Discrepancy — {c.severity} Severity ({resolved_label})\n"
                    f"- **Source A (Resume/Prior Turn):** *\"{c.source_a}\"*\n"
                    f"- **Source B (Candidate Answer):** *\"{c.source_b}\"*\n"
                    f"- **Analysis:** {c.description}\n"
                    f"- **Clarification Question Asked:** *{c.clarification_question}*\n"
                )
            contradictions_section = "\n".join(c_items)

        # Build Audit Trail
        audit_rows = []
        for a in report.audit_trail:
            audit_rows.append(
                f"| Turn {a.get('turn')} | **{a.get('competency', 'N/A')}** | `{a.get('action')}` | {a.get('reason', '')} |"
            )
        audit_table = "\n".join(audit_rows)

        duration_str = ""
        if report.interview_duration_seconds is not None:
            mins, secs = divmod(report.interview_duration_seconds, 60)
            duration_str = f"  \n**Interview Duration:** {mins}m {secs}s"

        mode_labels = {
            "assessment": "🎯 Assessment",
            "practice": "📚 Practice",
            "confidence_coach": "🧠 Confidence Coach",
        }
        mode_badge = mode_labels.get(report.interview_mode.value, report.interview_mode.value)
        coaching_notice = ""
        if report.support_interventions_count > 0 or report.interview_mode.value != "assessment":
            coaching_notice = (
                "> [!WARNING]\n"
                f"> **Interview Mode: {mode_badge}** — "
                f"{report.support_interventions_count} support intervention(s) were provided. "
                "Coached answers may not reflect raw unaided performance.\n\n"
            )
        answer_change_notice = ""
        if report.answer_changes_detected > 0:
            answer_change_notice = (
                "> [!NOTE]\n"
                f"> **Candidate self-corrected {report.answer_changes_detected} time(s)** during the interview. "
                "Corrected answers were flagged and re-evaluated.\n\n"
            )

        md = f"""# InterviewOne AI — Candidate Assessment Dossier

**Interview ID:** `{report.interview_id}`  
**Candidate Name:** {report.candidate_name}  
**Target Role:** {report.job_title}  
**Interview Mode:** {mode_badge}  
**Generated At:** {report.generated_at}{duration_str}

---

## 🎯 Executive Hiring Decision

| Overall Recommendation | Overall Score | Confidence Level |
|:---:|:---:|:---:|
| {verdict_badge} | **{report.overall_score:.2f} / 5.0** | **{report.overall_confidence:.2f}** |

{guardrail_notice}{coaching_notice}{answer_change_notice}### Summary Rationale
{report.summary_rationale}

---

## 📊 Live Competency Scorecard

| Competency | Priority | Score | Confidence | Status | Demonstrated Evidence |
|:---|:---:|:---:|:---:|:---:|:---|
{comp_table}

---

## 🔍 Trust & Verification Summary

### Claims Verification
{claims_summary}

### Contradictions & Discrepancies
{contradictions_section}

---

## 💡 Key Assessment Highlights

### Strengths Demonstrated
{strengths_list}

### Remaining Evidence Gaps
{gaps_list}

---

## 📜 Interview Audit Trail

| Turn | Competency | Action Selected | Decision Rationale |
|:---:|:---|:---:|:---|
{audit_table}

---
*Generated by InterviewOne AI Assessment Engine (Person 3 — Evidence + Evaluation)*
"""
        return md

    @staticmethod
    def save_report(
        report: FinalAssessmentReport,
        output_dir: str = ".",
        filename_prefix: str = "assessment_report",
    ) -> Tuple[str, str]:
        """Saves the report as both Markdown and JSON files."""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        md_content = ReportGenerator.generate_markdown(report)
        md_file = out_path / f"{filename_prefix}.md"
        md_file.write_text(md_content, encoding="utf-8")

        json_file = out_path / f"{filename_prefix}.json"
        json_file.write_text(report.model_dump_json(indent=2), encoding="utf-8")

        return str(md_file), str(json_file)
