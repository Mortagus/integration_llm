from io import BytesIO
from unittest.mock import Mock

import pytest
from fastapi import HTTPException, UploadFile

from saas_rh.api.routers.candidates import parse_candidate
from saas_rh.candidates.pdf import CandidatePdfTextExtractor
from saas_rh.candidates.schemas import CandidateParseResponse
from saas_rh.candidates.service import CandidateParserService


def test_parse_candidate_rejects_text_and_pdf_sent_together() -> None:
    parser = Mock(spec=CandidateParserService)
    pdf_text_extractor = Mock(spec=CandidatePdfTextExtractor)
    pdf_file = UploadFile(filename="cv.pdf", file=BytesIO(b"contenu PDF"))

    with pytest.raises(HTTPException) as error_info:
        parse_candidate(
            parser=parser,
            pdf_text_extractor=pdf_text_extractor,
            cv_text="CV texte",
            cv_file=pdf_file,
        )

    assert error_info.value.status_code == 400
    parser.parse_candidate.assert_not_called()
    pdf_text_extractor.extract_text.assert_not_called()


def test_parse_candidate_accepts_text_only_and_returns_its_score() -> None:
    candidate = CandidateParseResponse(
        skills=["Python"],
        years_of_experience=6,
        education_level="Master",
        match_score=90,
        warning_points=[],
    )
    parser = Mock(spec=CandidateParserService)
    parser.parse_candidate.return_value = candidate
    pdf_text_extractor = Mock(spec=CandidatePdfTextExtractor)

    result = parse_candidate(
        parser=parser,
        pdf_text_extractor=pdf_text_extractor,
        cv_text=" CV de développeur ",
    )

    assert result == candidate
    assert result.match_score == 90
    parser.parse_candidate.assert_called_once_with("CV de développeur")
    pdf_text_extractor.extract_text.assert_not_called()


def test_parse_candidate_accepts_pdf_only_and_returns_its_score() -> None:
    candidate = CandidateParseResponse(
        skills=["React"],
        years_of_experience=1,
        education_level="Bootcamp",
        match_score=25,
        warning_points=["Peu d'expérience Python"],
    )
    parser = Mock(spec=CandidateParserService)
    parser.parse_candidate.return_value = candidate
    pdf_text_extractor = Mock(spec=CandidatePdfTextExtractor)
    pdf_text_extractor.extract_text.return_value = "CV PDF extrait"
    pdf_file = UploadFile(filename="cv.pdf", file=BytesIO(b"contenu PDF"))

    result = parse_candidate(
        parser=parser,
        pdf_text_extractor=pdf_text_extractor,
        cv_file=pdf_file,
    )

    assert result == candidate
    assert result.match_score == 25
    pdf_text_extractor.extract_text.assert_called_once_with(b"contenu PDF")
    parser.parse_candidate.assert_called_once_with("CV PDF extrait")
