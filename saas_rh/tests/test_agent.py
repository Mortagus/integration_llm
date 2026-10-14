import json
from types import SimpleNamespace

import anyio
import pytest
from fastapi import HTTPException
from fastapi.sse import ServerSentEvent

from saas_rh.agent.schemas import AgentConversationMessage
from saas_rh.api.routers.agent import agent_chat


class FakeAgentService:
    def __init__(self, events: list[SimpleNamespace] | None = None) -> None:
        self.events = events or []
        self.user_prompt: str | None = None
        self.conversation_history = []

    def stream_events(self, user_prompt: str, conversation_history=()):
        self.user_prompt = user_prompt
        self.conversation_history = list(conversation_history)
        yield from self.events


async def _collect_agent_events(
    agent_service,
    user_prompt: str,
    conversation_history_json: str | None = None,
):
    response = await agent_chat(
        agent_service=agent_service,
        user_prompt=user_prompt,
        conversation_history_json=conversation_history_json,
    )
    events = []
    async for chunk in response.body_iterator:
        if isinstance(chunk, ServerSentEvent):
            events.append(SimpleNamespace(event=chunk.event, data=chunk.data))
            continue
        content = chunk.decode() if isinstance(chunk, bytes) else chunk
        for record in content.replace("\r\n", "\n").split("\n\n"):
            fields = dict(
                line.split(": ", maxsplit=1)
                for line in record.splitlines()
                if ": " in line
            )
            if "event" in fields and "data" in fields:
                events.append(
                    SimpleNamespace(
                        event=fields["event"], data=json.loads(fields["data"])
                    )
                )
    return events


def test_agent_chat_streams_text_tools_results_and_completion() -> None:
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
    events = anyio.run(_collect_agent_events, service, "Trouve un créneau.")

    assert [(event.event, event.data) for event in events] == [
        ("text", {"text": "Je recherche."}),
        ("tool_call", {"name": "search_interview_slots"}),
        ("tool_result", {"name": "search_interview_slots", "result": ["09:00"]}),
        ("done", {"status": "completed"}),
    ]
    assert service.user_prompt == "Trouve un créneau."
    assert service.conversation_history == []


def test_agent_chat_passes_validated_conversation_history_to_service() -> None:
    service = FakeAgentService(
        [SimpleNamespace(event_type="done", data={"status": "completed"})]
    )
    history = [
        {
            "role": "user",
            "content": "Recherche le 2026-10-15 pour Jean Dupont.",
        },
        {"role": "assistant", "content": "Les créneaux sont 09:00 et 11:00."},
    ]

    anyio.run(
        _collect_agent_events,
        service,
        "Je prends 09:00.",
        json.dumps(history),
    )

    assert service.conversation_history == [
        AgentConversationMessage.model_validate(message) for message in history
    ]


def test_agent_chat_returns_error_and_done_events_when_service_fails() -> None:
    class FailingAgentService:
        def stream_events(self, user_prompt: str, conversation_history=()):
            raise RuntimeError("Erreur simulée")
            yield  # pragma: no cover

    events = anyio.run(
        _collect_agent_events, FailingAgentService(), "Trouve un créneau."
    )

    assert [(event.event, event.data) for event in events] == [
        ("error", {"message": "Une erreur est survenue pendant le traitement."}),
        ("done", {"status": "error"}),
    ]


def test_agent_chat_rejects_blank_prompt_with_bad_request() -> None:
    with pytest.raises(HTTPException) as error_info:
        anyio.run(_collect_agent_events, FakeAgentService(), "   ")

    assert error_info.value.status_code == 400
