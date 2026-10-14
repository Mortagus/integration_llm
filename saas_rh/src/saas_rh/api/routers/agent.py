import json
import logging
from collections.abc import AsyncIterable
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Response, status
from fastapi.sse import EventSourceResponse
from pydantic import TypeAdapter, ValidationError
from starlette.concurrency import iterate_in_threadpool

from saas_rh.agent.schemas import AgentConversationMessage
from saas_rh.agent.service import AgentService, AgentToolLoopLimitError
from saas_rh.api.dependencies import get_agent_service

router = APIRouter(
    prefix="/api/agent",
    tags=["agent"],
)
logger = logging.getLogger(__name__)


@router.post(
    "/chat",
    response_class=Response,
    responses={200: {"content": {"text/event-stream": {}}}},
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

    # En production, conserver l'historique côté serveur ou en vérifier l'intégrité :
    # un client peut modifier les messages qu'il transmet ici.
    try:
        decoded_history = json.loads(conversation_history_json or "[]")
        if not isinstance(decoded_history, list) or len(decoded_history) > 40:
            raise ValueError("Historique de conversation invalide.")
        conversation_history = TypeAdapter(
            list[AgentConversationMessage]
        ).validate_python(decoded_history)
    except (json.JSONDecodeError, ValidationError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'historique de conversation est invalide.",
        ) from error

    async def event_stream() -> AsyncIterable[str]:
        events = agent_service.stream_events(
            user_prompt.strip(),
            conversation_history=conversation_history,
        )
        try:
            async for event in iterate_in_threadpool(events):
                yield _format_sse_event(event.event_type, event.data)
        except AgentToolLoopLimitError:
            yield _format_sse_event(
                "error", {"message": "L'agent a atteint la limite d'appels d'outils."}
            )
            yield _format_sse_event("done", {"status": "error"})
        except Exception as error:  # noqa: BLE001 - errors must stay inside the SSE stream.
            logger.error(
                "Échec inattendu du chat agent : type=%s", type(error).__name__
            )
            yield _format_sse_event(
                "error", {"message": "Une erreur est survenue pendant le traitement."}
            )
            yield _format_sse_event("done", {"status": "error"})

    return EventSourceResponse(event_stream())


def _format_sse_event(event: str, data: object) -> str:
    """Encode one agent event as a Server-Sent Event frame."""
    serialized_data = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {serialized_data}\n\n"
