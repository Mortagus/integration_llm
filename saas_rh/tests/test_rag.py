from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from saas_rh.api.routers.rag import ask_rag
from saas_rh.rag.schemas import RagAskResponse
from saas_rh.rag.service import NO_CONTEXT_RESPONSE


def test_post_ask_rag_rejects_missing_question() -> None:
    with pytest.raises(HTTPException) as error_info:
        ask_rag(rag_service=Mock(), question=None)

    assert error_info.value.status_code == 400


def test_post_ask_rag_rejects_blank_question() -> None:
    with pytest.raises(HTTPException) as error_info:
        ask_rag(rag_service=Mock(), question="  ")

    assert error_info.value.status_code == 400


def test_post_ask_rag_returns_the_service_answer_and_sources() -> None:
    expected_response = RagAskResponse(content=NO_CONTEXT_RESPONSE, sources=[])
    rag_service = Mock()
    rag_service.answer_question.return_value = expected_response

    response = ask_rag(rag_service=rag_service, question=" Question RH ")

    assert response is expected_response
    rag_service.answer_question.assert_called_once_with("Question RH")
