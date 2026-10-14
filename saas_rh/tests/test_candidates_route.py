from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from saas_rh.api.dependencies import get_candidate_parser_service
from saas_rh.api.routers.candidates import router
from saas_rh.candidates.schemas import CandidateParseResponse
from saas_rh.candidates.service import CandidateParserService


def make_client(parser: Mock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_candidate_parser_service] = lambda: parser
    return TestClient(app)


def test_parse_candidate_returns_profile_over_http() -> None:
    parser = Mock(spec=CandidateParserService)
    parser.parse_candidate.return_value = CandidateParseResponse(
        skills=["Python"],
        years_of_experience=6,
        education_level="Master",
        match_score=90,
        warning_points=[],
    )

    response = make_client(parser).post(
        "/api/candidates/parse", data={"cv_text": " CV de développeur "}
    )

    assert response.status_code == 200
    assert response.json() == {
        "skills": ["Python"],
        "years_of_experience": 6.0,
        "education_level": "Master",
        "match_score": 90,
        "warning_points": [],
    }
    parser.parse_candidate.assert_called_once_with("CV de développeur")


def test_parse_candidate_rejects_text_and_pdf_sent_together_over_http() -> None:
    parser = Mock(spec=CandidateParserService)

    response = make_client(parser).post(
        "/api/candidates/parse",
        data={"cv_text": "CV texte"},
        files={"cv_file": ("cv.pdf", b"contenu PDF", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Fournissez exactement un CV texte ou un fichier CV."
    }
    parser.parse_candidate.assert_not_called()


def test_parse_candidate_rejects_missing_input_over_http() -> None:
    response = make_client(Mock(spec=CandidateParserService)).post(
        "/api/candidates/parse", data={}
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Fournissez exactement un CV texte ou un fichier CV."
    }
