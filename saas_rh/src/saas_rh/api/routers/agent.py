from collections.abc import AsyncIterable
from typing import Annotated

from fastapi import APIRouter, Depends, Form
from fastapi.sse import EventSourceResponse, ServerSentEvent

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
) -> AsyncIterable[ServerSentEvent]:
    if user_prompt is None or not user_prompt.strip():
        yield ServerSentEvent(
            event="error",
            data={"message": "Le message utilisateur ne peut pas être vide."},
        )
        yield ServerSentEvent(event="done", data={"status": "error"})
        return

    async def event_stream() -> AsyncIterable[ServerSentEvent]:
        events = iter(agent_service.stream_events(user_prompt.strip()))
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
