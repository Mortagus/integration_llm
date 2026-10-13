from collections.abc import AsyncIterable
from typing import Annotated

from fastapi import APIRouter, Form
from fastapi.sse import EventSourceResponse, ServerSentEvent

router = APIRouter(
    prefix="/api/agent",
    tags=["agent"],
)


@router.post(
    "/chat",
    response_class=EventSourceResponse,
)
async def agent_chat(
    user_prompt: Annotated[str | None, Form()] = None,
) -> AsyncIterable[ServerSentEvent]:
    yield ServerSentEvent(raw_data="Route SSE prête")
