import logging
from typing import Annotated

from anthropic import APIError as AnthropicAPIError
from chromadb.errors import ChromaError
from fastapi import APIRouter, Depends, Form, HTTPException, status
from openai import APIError as OpenAIAPIError

from saas_rh.api.dependencies import get_rag_service
from saas_rh.rag.schemas import RagAskResponse
from saas_rh.rag.service import RAGService

router = APIRouter(
    prefix="/api/rag",
    tags=["rag"],
)
logger = logging.getLogger(__name__)


@router.post("/ask", response_model=RagAskResponse)
def ask_rag(
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
    question: Annotated[str | None, Form(max_length=1_000)] = None,
) -> RagAskResponse:
    has_question = question is not None and bool(question.strip())

    if not has_question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Veuillez envoyer une question.",
        )

    assert question is not None
    try:
        return rag_service.answer_question(question.strip())
    except (OpenAIAPIError, AnthropicAPIError, ChromaError) as error:
        logger.error(
            "Échec d'une intégration RAG : type=%s", type(error).__name__
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service RH est momentanément indisponible.",
        ) from error
    except ValueError as error:
        logger.error("Réponse RAG invalide : type=%s", type(error).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Le service RH n'a pas retourné de réponse valide.",
        ) from error
