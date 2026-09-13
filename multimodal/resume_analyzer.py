"""Local resume extraction with a small, structured contract.

Parsing is intentionally deterministic and does not invent candidate facts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import re
from typing import Any


@dataclass(frozen=True)
class ResumeProfile:
    skills: tuple[str, ...] = ()
    education: tuple[str, ...] = ()
    projects: tuple[str, ...] = ()
    experience: tuple[str, ...] = ()
    technologies: tuple[str, ...] = ()
    achievements: tuple[str, ...] = ()
    other_details: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ResumeAnalysisError(ValueError):
    """Raised when a resume cannot be parsed or has an unsupported format."""


class ResumeAnalyzer:
    """Extract section-based resume facts from PDF or DOCX files."""

    _sections = {
        "skills": {"skills", "technical skills", "skill set"},
        "education": {"education", "academic background"},
        "projects": {"projects", "personal projects", "academic projects"},
        "experience": {"experience", "work experience", "employment", "internships", "internship"},
        "achievements": {"achievements", "awards", "certifications", "accomplishments"},
    }

    def analyze(self, path: str | Path) -> ResumeProfile:
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"Resume does not exist: {file_path}")
        suffix = file_path.suffix.lower()
        text = self.extract_text(file_path)
        if not text.strip():
            raise ResumeAnalysisError("Resume contains no readable text")
        return self._extract(text)

    def extract_text(self, path: str | Path) -> str:
        file_path = Path(path)
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            return self._pdf_text(file_path)
        if suffix == ".docx":
            return self._docx_text(file_path)
        raise ResumeAnalysisError("Resume must be a PDF or DOCX file")

    @staticmethod
    def _pdf_text(path: Path) -> str:
        try:
            # pypdf is a declared dependency (requirements.txt) but is an OPTIONAL
            # runtime feature; failure is surfaced as ResumeAnalysisError below.
            # pyrefly: ignore[missing-import]
            from pypdf import PdfReader
            return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
        except Exception as exc:
            raise ResumeAnalysisError(f"Could not read PDF resume: {exc}") from exc

    @staticmethod
    def _docx_text(path: Path) -> str:
        try:
            from docx import Document
            document = Document(str(path))
            return "\n".join(paragraph.text for paragraph in document.paragraphs)
        except Exception as exc:
            raise ResumeAnalysisError(f"Could not read DOCX resume: {exc}") from exc

    def _extract(self, text: str) -> ResumeProfile:
        sections: dict[str, list[str]] = {name: [] for name in self._sections}
        current: str | None = None
        for raw_line in text.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip(" -\t")
            if not line:
                continue
            heading = line.lower().rstrip(":")
            matched = next((name for name, headings in self._sections.items() if heading in headings), None)
            if matched:
                current = matched
                continue
            if current:
                sections[current].append(line)
        skills = _clean_items(sections["skills"])
        technologies = _technology_terms(text)
        return ResumeProfile(
            skills=skills,
            education=_clean_items(sections["education"]),
            projects=_clean_items(sections["projects"]),
            experience=_clean_items(sections["experience"]),
            technologies=technologies,
            achievements=_clean_items(sections["achievements"]),
            other_details=tuple(),
        )


def _clean_items(items: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item for item in items if len(item) > 1))


def _technology_terms(text: str) -> tuple[str, ...]:
    known = ("Python", "Java", "JavaScript", "TypeScript", "React", "FastAPI", "Django", "SQL", "PostgreSQL", "Redis", "AWS", "Azure", "Docker", "Kubernetes", "TensorFlow", "PyTorch", "Git")
    lowered = text.lower()
    return tuple(term for term in known if re.search(r"\b" + re.escape(term.lower()) + r"\b", lowered))