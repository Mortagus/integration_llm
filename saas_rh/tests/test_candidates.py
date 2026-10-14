from pathlib import Path
from unittest.mock import Mock

import pytest
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


def test_post_parse_candidate_check_returns_400() -> None:
    response = make_client(Mock(spec=CandidateParserService)).post(
        "/api/candidates/parse", data={}
    )

    assert response.status_code == 400


def test_parse_candidate_from_pdf_returns_a_structured_profile() -> None:
    pdf_path = (
        Path(__file__).parents[1]
        / "src"
        / "saas_rh"
        / "data"
        / "candidates"
        / "20261014_test_cv.pdf"
    )
    if not pdf_path.exists():
        pytest.skip("Le CV PDF personnel local n'est pas présent dans ce checkout.")

    expected_candidate = CandidateParseResponse(
        skills=["Python"],
        years_of_experience=1,
        education_level="Test",
        match_score=50,
        warning_points=[],
    )
    parser = Mock(spec=CandidateParserService)
    parser.parse_candidate.return_value = expected_candidate

    with pdf_path.open("rb") as pdf_file:
        response = make_client(parser).post(
            "/api/candidates/parse",
            files={"cv_file": (pdf_path.name, pdf_file, "application/pdf")},
        )

    assert response.status_code == 200
    assert response.json() == expected_candidate.model_dump()
    parser.parse_candidate.assert_called_once()
    extracted_text = parser.parse_candidate.call_args.args[0]
    assert len(extracted_text.split()) > 100
