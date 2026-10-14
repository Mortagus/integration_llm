from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from openai import APIStatusError

from saas_rh.candidates.schemas import CandidateParseEvidence
from saas_rh.candidates.service import (
    CandidateModelsUnavailableError,
    CandidateParserService,
)
from saas_rh.data.candidates.mock_data import CANDIDAT_EXEMPLE_1


def make_status_error(
    status_code: int,
    message: str = "Temporary model error",
) -> APIStatusError:
    response = MagicMock()
    response.status_code = status_code
    response.headers = {}
    response.request = MagicMock()
    return APIStatusError(message, response=response, body={})


def make_client(parse_mock: Mock) -> SimpleNamespace:
    return SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(parse=parse_mock),
        ),
    )


def test_candidate_parser_falls_back_after_temporary_model_error() -> None:
    candidate = CandidateParseEvidence(
        skills=["Python", "FastAPI"],
        years_of_experience=6,
        education_level="Master",
        warning_points=[],
        leadership_evidence=[],
    )
    parsed_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(parsed=candidate))]
    )
    parse_mock = Mock(side_effect=[make_status_error(503), parsed_response])
    service = CandidateParserService(
        client=make_client(parse_mock),
        model_name="gemini-model-surcharge",
        fallback_model_names=["gemini-model-disponible"],
    )

    result = service.parse_candidate(CANDIDAT_EXEMPLE_1)

    assert result.skills == candidate.skills
    assert result.match_score == 32
    assert [call.kwargs["model"] for call in parse_mock.call_args_list] == [
        "gemini-model-surcharge",
        "gemini-model-disponible",
    ]


def test_candidate_parser_does_not_fallback_on_bad_request() -> None:
    parse_mock = Mock(side_effect=make_status_error(400))
    service = CandidateParserService(
        client=make_client(parse_mock),
        model_name="gemini-model-configure",
        fallback_model_names=["gemini-model-disponible"],
    )

    with pytest.raises(APIStatusError):
        service.parse_candidate(CANDIDAT_EXEMPLE_1)

    assert parse_mock.call_count == 1


def test_candidate_parser_rejects_missing_structured_output() -> None:
    response_without_parsed_candidate = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(parsed=None))]
    )
    parse_mock = Mock(return_value=response_without_parsed_candidate)
    service = CandidateParserService(
        client=make_client(parse_mock),
        model_name="gemini-model-configure",
    )

    with pytest.raises(ValueError, match="profil candidat valide"):
        service.parse_candidate(CANDIDAT_EXEMPLE_1)

    assert parse_mock.call_count == 1


def test_candidate_parser_reports_when_all_models_are_unavailable() -> None:
    parse_mock = Mock(
        side_effect=[
            make_status_error(429, "The service is busy."),
            make_status_error(503, "Model is experiencing high demand."),
        ]
    )
    service = CandidateParserService(
        client=make_client(parse_mock),
        model_name="gemini-model-sature-1",
        fallback_model_names=["gemini-model-sature-2"],
    )

    with pytest.raises(CandidateModelsUnavailableError) as error_info:
        service.parse_candidate(CANDIDAT_EXEMPLE_1)

    assert parse_mock.call_count == 2
    assert error_info.value.model_name == "gemini-model-sature-2"
    assert error_info.value.status_code == 503
    assert "experiencing high demand" in str(error_info.value)
