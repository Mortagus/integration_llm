import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient

from saas_rh.agent.schemas import AgentConversationMessage
from saas_rh.agent.service import AgentService
from saas_rh.api.dependencies import get_agent_service
from saas_rh.api.routers.agent import router


class FakeAgentService:
    def __init__(self, events: list[SimpleNamespace] | None = None) -> None:
        self.events = events or []
        self.user_prompt: str | None = None
        self.conversation_history = []

    def stream_events(self, user_prompt: str, conversation_history=()):
        self.user_prompt = user_prompt
        self.conversation_history = list(conversation_history)
        yield from self.events


def make_app(agent_service: object) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_agent_service] = lambda: agent_service
    return app


async def post_form(app: FastAPI, data: dict[str, str]):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        return await client.post("/api/agent/chat", data=data)


def parse_sse_events(response_text: str) -> list[SimpleNamespace]:
    events = []
    for record in response_text.replace("\r\n", "\n").split("\n\n"):
        fields = dict(
            line.split(": ", maxsplit=1) for line in record.splitlines() if ": " in line
        )
        if "event" in fields and "data" in fields:
            events.append(
                SimpleNamespace(event=fields["event"], data=json.loads(fields["data"]))
            )
    return events


def test_agent_chat_streams_events_over_http() -> None:
    service = FakeAgentService(
        [
            SimpleNamespace(event_type="text", data={"text": "Je recherche."}),
            SimpleNamespace(
                event_type="tool_call",
                data={"name": "search_interview_slots"},
            ),
            SimpleNamespace(
                event_type="tool_result",
                data={"name": "search_interview_slots", "result": ["09:00"]},
            ),
            SimpleNamespace(event_type="done", data={"status": "completed"}),
        ]
    )

    response = asyncio.run(
        post_form(make_app(service), {"user_prompt": "Trouve un créneau."})
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert [(event.event, event.data) for event in parse_sse_events(response.text)] == [
        ("text", {"text": "Je recherche."}),
        ("tool_call", {"name": "search_interview_slots"}),
        ("tool_result", {"name": "search_interview_slots", "result": ["09:00"]}),
        ("done", {"status": "completed"}),
    ]
    assert service.user_prompt == "Trouve un créneau."
    assert service.conversation_history == []


def test_agent_chat_passes_validated_history_over_http() -> None:
    service = FakeAgentService(
        [SimpleNamespace(event_type="done", data={"status": "completed"})]
    )
    history = [
        {"role": "user", "content": "Recherche le 2026-10-15 pour Jean Dupont."},
        {"role": "assistant", "content": "Les créneaux sont 09:00 et 11:00."},
    ]

    response = asyncio.run(
        post_form(
            make_app(service),
            {
                "user_prompt": "Je prends 09:00.",
                "conversation_history_json": json.dumps(history),
            },
        )
    )

    assert response.status_code == 200
    assert service.conversation_history == [
        AgentConversationMessage.model_validate(message) for message in history
    ]


def test_agent_chat_returns_error_event_when_service_fails_over_http() -> None:
    class FailingAgentService:
        def stream_events(self, user_prompt: str, conversation_history=()):
            raise RuntimeError("Erreur simulée")
            yield  # pragma: no cover

    response = asyncio.run(
        post_form(
            make_app(FailingAgentService()),
            {"user_prompt": "Trouve un créneau."},
        )
    )

    assert response.status_code == 200
    assert [(event.event, event.data) for event in parse_sse_events(response.text)] == [
        ("error", {"message": "Une erreur est survenue pendant le traitement."}),
        ("done", {"status": "error"}),
    ]


def test_agent_chat_rejects_blank_prompt_over_http() -> None:
    response = asyncio.run(
        post_form(make_app(Mock(spec=AgentService)), {"user_prompt": "   "})
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Le message utilisateur ne peut pas être vide."
    }


def test_agent_chat_rejects_invalid_history_over_http() -> None:
    response = asyncio.run(
        post_form(
            make_app(Mock(spec=AgentService)),
            {"user_prompt": "Bonjour", "conversation_history_json": "not-json"},
        )
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "L'historique de conversation est invalide."}
