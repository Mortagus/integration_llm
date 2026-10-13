from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, status
from fastapi.sse import EventSourceResponse

router = APIRouter(
    prefix="/api/agent",
    tags=["agent"],
)


@router.post(
    "/chat",
    response_class=EventSourceResponse,
    responses={501: {"description": "Agent Chat non implémenté"}},
)
async def agent_chat(
    user_prompt: Annotated[str | None, Form()] = None,
) -> EventSourceResponse:
    has_user_prompt = user_prompt is not None and bool(user_prompt.strip())

    if not has_user_prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Veuillez envoyer un prompt.",
        )
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Agent Chat n'est pas encore implémenté.",
    )
