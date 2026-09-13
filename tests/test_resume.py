from pathlib import Path

import pytest

from multimodal.resume_analyzer import ResumeAnalysisError, ResumeAnalyzer


def test_resume_sections_and_technologies_are_structured(tmp_path: Path):
    path = tmp_path / "resume.txt"
    path.write_text(
        "Skills\nPython, SQL\nEducation\nBSc Computer Science\nProjects\nNotification API\n"
        "Experience\nBackend Intern\nAchievements\nDean's list\nBuilt with FastAPI and PostgreSQL",
        encoding="utf-8",
    )
    profile = ResumeAnalyzer()._extract(path.read_text(encoding="utf-8"))
    assert profile.skills == ("Python, SQL",)
    assert profile.education == ("BSc Computer Science",)
    assert profile.projects == ("Notification API",)
    assert profile.experience == ("Backend Intern",)
    assert profile.technologies == ("Python", "FastAPI", "SQL", "PostgreSQL")


def test_resume_rejects_unsupported_format(tmp_path: Path):
    path = tmp_path / "resume.txt"
    path.write_text("text", encoding="utf-8")
    with pytest.raises(ResumeAnalysisError):
        ResumeAnalyzer().analyze(path)