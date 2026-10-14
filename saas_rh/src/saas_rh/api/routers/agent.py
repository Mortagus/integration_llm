import json
from collections.abc import AsyncIterable
from typing import Annotated

from fastapi import APIRouter, Depends, Form
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import TypeAdapter, ValidationError

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
    user_prompt: Annotated[str | None, Form()] = None,
    conversation_history_json: Annotated[str | None, Form()] = None,
) -> AsyncIterable[ServerSentEvent]:
    if user_prompt is None or not user_prompt.strip():
        yield ServerSentEvent(
            event="error",
            data={"message": "Le message utilisateur ne peut pas être vide."},
        )
        yield ServerSentEvent(event="done", data={"status": "error"})
        return

    try:
        decoded_history = json.loads(conversation_history_json or "[]")
        if not isinstance(decoded_history, list) or len(decoded_history) > 40:
            raise ValueError("Historique de conversation invalide.")
        conversation_history = TypeAdapter(
            list[AgentConversationMessage]
        ).validate_python(decoded_history)
    except (json.JSONDecodeError, ValidationError, ValueError):
        yield ServerSentEvent(
            event="error",
            data={"message": "L'historique de conversation est invalide."},
        )
        yield ServerSentEvent(event="done", data={"status": "error"})
        return

    async def event_stream() -> AsyncIterable[ServerSentEvent]:
        events = iter(
            agent_service.stream_events(
                user_prompt.strip(),
                conversation_history=conversation_history,
            )
        )
        try:
            for event in events:
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

    async for event in event_stream():
        yield event
