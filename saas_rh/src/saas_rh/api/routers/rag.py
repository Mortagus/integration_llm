from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, status

from saas_rh.rag.schemas import RagAskResponse

router = APIRouter(
    prefix="/api/rag",
    tags=["rag"],
)


@router.post(
    "/ask",
    response_model=RagAskResponse,
    responses={501: {"description": "Rag Query non implémenté"}},
)
async def ask_rag(
    question: Annotated[str | None, Form()] = None,
) -> RagAskResponse:
    has_question = question is not None and bool(question.strip())

    if not has_question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Veuillez envoyer une question.",
        )

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Rag Ask n'est pas encore implémenté.",
    )
