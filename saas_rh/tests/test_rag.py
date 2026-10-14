from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from saas_rh.api.dependencies import get_rag_service
from saas_rh.api.routers.rag import router
from saas_rh.rag.schemas import RagAskResponse
from saas_rh.rag.service import NO_CONTEXT_RESPONSE, RAGService


def make_client(rag_service: Mock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_rag_service] = lambda: rag_service
    return TestClient(app)


def test_post_ask_rag_rejects_missing_question() -> None:
    response = make_client(Mock(spec=RAGService)).post("/api/rag/ask", data={})

    assert response.status_code == 400
    assert response.json() == {"detail": "Veuillez envoyer une question."}


def test_post_ask_rag_rejects_blank_question() -> None:
    response = make_client(Mock(spec=RAGService)).post(
        "/api/rag/ask", data={"question": "  "}
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Veuillez envoyer une question."}


def test_post_ask_rag_returns_the_service_answer_and_sources() -> None:
    expected_response = RagAskResponse(
        content="Les RTT peuvent être versés au CET.",
        sources=[{"id": "rh_doc_02", "title": "Congés", "excerpt": "Dix jours."}],
    )
    rag_service = Mock(spec=RAGService)
    rag_service.answer_question.return_value = expected_response

    response = make_client(rag_service).post(
        "/api/rag/ask", data={"question": " Question RH "}
    )

    assert response.status_code == 200
    assert response.json() == expected_response.model_dump()
    rag_service.answer_question.assert_called_once_with("Question RH")


def test_post_ask_rag_returns_refusal_without_sources_over_http() -> None:
    rag_service = Mock(spec=RAGService)
    rag_service.answer_question.return_value = RagAskResponse(
        content=NO_CONTEXT_RESPONSE, sources=[]
    )

    response = make_client(rag_service).post(
        "/api/rag/ask", data={"question": "Question absente"}
    )

    assert response.status_code == 200
    assert response.json() == {"content": NO_CONTEXT_RESPONSE, "sources": []}
