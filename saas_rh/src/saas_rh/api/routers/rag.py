from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, status

from saas_rh.api.dependencies import get_rag_service
from saas_rh.rag.schemas import RagAskResponse
from saas_rh.rag.service import RAGService

router = APIRouter(
    prefix="/api/rag",
    tags=["rag"],
)


@router.post("/ask", response_model=RagAskResponse)
def ask_rag(
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
    question: Annotated[str | None, Form()] = None,
) -> RagAskResponse:
    has_question = question is not None and bool(question.strip())

    if not has_question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Veuillez envoyer une question.",
        )

    assert question is not None
    return rag_service.answer_question(question.strip())
