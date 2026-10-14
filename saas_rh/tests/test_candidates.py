from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import HTTPException, UploadFile

from saas_rh.api.routers.candidates import parse_candidate
from saas_rh.candidates.pdf import CandidatePdfTextExtractor
from saas_rh.candidates.schemas import CandidateParseResponse
from saas_rh.candidates.service import CandidateParserService


def test_post_parse_candidate_check_returns_400() -> None:
    with pytest.raises(HTTPException) as error_info:
        parse_candidate(
            parser=Mock(spec=CandidateParserService),
            pdf_text_extractor=CandidatePdfTextExtractor(),
        )

    assert error_info.value.status_code == 400


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
        uploaded_file = UploadFile(filename=pdf_path.name, file=pdf_file)
        try:
            result = parse_candidate(
                parser=parser,
                pdf_text_extractor=CandidatePdfTextExtractor(),
                cv_file=uploaded_file,
            )
        except HTTPException as error:
            pytest.fail(
                f"Le parsing du PDF devrait réussir, mais la route renvoie "
                f"HTTP {error.status_code} : {error.detail}"
            )

    assert result == expected_candidate
    parser.parse_candidate.assert_called_once()
    extracted_text = parser.parse_candidate.call_args.args[0]
    assert len(extracted_text.split()) > 100
