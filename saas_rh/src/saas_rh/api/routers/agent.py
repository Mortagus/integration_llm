import json
from collections.abc import AsyncIterable
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import TypeAdapter, ValidationError
from starlette.concurrency import iterate_in_threadpool

from saas_rh.agent.schemas import AgentConversationMessage
from saas_rh.agent.service import AgentService, AgentToolLoopLimitError
from saas_rh.api.dependencies import get_agent_service

router = APIRouter(
    prefix="/api/agent",
    tags=["agent"],
)


@router.post(
    "/chat",
    response_class=EventSourceResponse,
)
async def agent_chat(
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
    user_prompt: Annotated[str | None, Form(max_length=2_000)] = None,
    conversation_history_json: Annotated[str | None, Form(max_length=200_000)] = None,
) -> EventSourceResponse:
    if user_prompt is None or not user_prompt.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le message utilisateur ne peut pas être vide.",
        )

    try:
        decoded_history = json.loads(conversation_history_json or "[]")
        if not isinstance(decoded_history, list) or len(decoded_history) > 40:
            raise ValueError("Historique de conversation invalide.")
        conversation_history = TypeAdapter(
            list[AgentConversationMessage]
        ).validate_python(decoded_history)
    except (json.JSONDecodeError, ValidationError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'historique de conversation est invalide.",
        )

    async def event_stream() -> AsyncIterable[ServerSentEvent]:
        events = agent_service.stream_events(
            user_prompt.strip(),
            conversation_history=conversation_history,
        )
        try:
            async for event in iterate_in_threadpool(events):
                yield ServerSentEvent(event=event.event_type, data=event.data)
        except AgentToolLoopLimitError:
            yield ServerSentEvent(
                event="error",
                data={"message": "L'agent a atteint la limite d'appels d'outils."},
            )
            yield ServerSentEvent(event="done", data={"status": "error"})
        except Exception:  # noqa: BLE001 - errors must stay inside the SSE stream.
            yield ServerSentEvent(
                event="error",
                data={"message": "Une erreur est survenue pendant le traitement."},
            )
            yield ServerSentEvent(event="done", data={"status": "error"})

    return EventSourceResponse(event_stream())
