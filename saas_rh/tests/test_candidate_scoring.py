from saas_rh.candidates.schemas import CandidateParseEvidence
from saas_rh.candidates.scoring import calculate_match_score


def test_candidate_with_indirect_rag_evidence_and_no_leadership_scores_85() -> None:
    candidate = CandidateParseEvidence(
        skills=[
            "Python",
            "FastAPI",
            "Pydantic",
            "Docker",
            "ChromaDB",
            "OpenAI API",
            "LLM",
        ],
        years_of_experience=6,
        education_level="Master en Informatique",
        warning_points=["Le CV ne précise pas la version de Python."],
        leadership_evidence=[],
    )

    assert calculate_match_score(candidate) == 85


def test_explicit_rag_and_leadership_evidence_receive_full_credit() -> None:
    candidate = CandidateParseEvidence(
        skills=[
            "Python",
            "FastAPI",
            "Pydantic",
            "Architecture RAG",
            "Docker",
            "ChromaDB",
            "OpenAI API",
        ],
        years_of_experience=6,
        education_level="Master en Informatique",
        warning_points=[],
        leadership_evidence=["A encadré une équipe de développeurs."],
    )

    assert calculate_match_score(candidate) == 99


def test_basic_python_and_one_year_experience_receive_partial_credit() -> None:
    candidate = CandidateParseEvidence(
        skills=["Notion de Python de base", "Base de données relationnelles"],
        years_of_experience=1,
        education_level="Bootcamp Développement Web",
        warning_points=[],
        leadership_evidence=[],
    )

    assert calculate_match_score(candidate) == 5


def test_python_version_311_or_newer_gets_full_python_credit() -> None:
    candidate = CandidateParseEvidence(
        skills=["Python 3.11+"],
        years_of_experience=0,
        education_level="Non précisé",
        warning_points=[],
        leadership_evidence=[],
    )

    assert calculate_match_score(candidate) == 11


def test_substrings_in_unrelated_skills_do_not_count_as_rag() -> None:
    candidate = CandidateParseEvidence(
        skills=["Cloud Storage", "Data Averaging"],
        years_of_experience=0,
        education_level="Non précisé",
        warning_points=[],
        leadership_evidence=[],
    )

    assert calculate_match_score(candidate) == 0
