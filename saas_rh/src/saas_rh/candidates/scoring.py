import re

from saas_rh.candidates.schemas import CandidateParseEvidence

CRITERIA_COUNT = 9
MINIMUM_RELEVANT_EXPERIENCE_YEARS = 5


def calculate_match_score(candidate: CandidateParseEvidence) -> int:
    """Calculate a 0–100 match score from extracted facts using equal weights."""
    skills = [skill.casefold() for skill in candidate.skills]

    criterion_scores = [
        _python_score(skills),
        _has_skill(skills, "fastapi"),
        _has_skill(skills, "pydantic"),
        _rag_score(skills),
        _has_skill(skills, "docker"),
        _has_any_skill(skills, ("chromadb", "qdrant")),
        _has_any_skill(skills, ("openai", "gemini")),
        min(
            candidate.years_of_experience / MINIMUM_RELEVANT_EXPERIENCE_YEARS,
            1.0,
        ),
        float(bool(candidate.leadership_evidence)),
    ]

    return round(sum(criterion_scores) / CRITERIA_COUNT * 100)


def _python_score(skills: list[str]) -> float:
    python_skills = [skill for skill in skills if re.search(r"\bpython\b", skill)]
    if not python_skills:
        return 0.0

    if any(
        re.search(r"\bpython\s*3\.(?:1[1-9]|[2-9]\d)\b", skill)
        for skill in python_skills
    ):
        return 1.0
    if any(
        not re.search(r"\b(?:notion|notions|base|bases|débutant|débutante)\b", skill)
        for skill in python_skills
    ):
        return 0.9
    return 0.25


def _has_skill(skills: list[str], term: str) -> float:
    return float(any(_has_term(skill, term) for skill in skills))


def _has_any_skill(skills: list[str], terms: tuple[str, ...]) -> float:
    return float(any(_has_term(skill, term) for skill in skills for term in terms))


def _has_term(skill: str, term: str) -> bool:
    """Match a term as a phrase instead of accepting arbitrary substrings."""
    return re.search(rf"\b{re.escape(term)}\b", skill) is not None


def _rag_score(skills: list[str]) -> float:
    if _has_any_skill(
        skills,
        ("rag", "retrieval augmented generation", "retrieval-augmented generation"),
    ):
        return 1.0
    if _has_any_skill(skills, ("llm", "large language model")) and _has_any_skill(
        skills, ("chromadb", "qdrant")
    ):
        return 0.75
    return 0.0
