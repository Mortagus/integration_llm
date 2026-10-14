import asyncio
import json
from types import SimpleNamespace

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
    return [
        event
        async for event in agent_chat(
            agent_service=agent_service,
            user_prompt=user_prompt,
            conversation_history_json=conversation_history_json,
        )
    ]


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
    events = asyncio.run(_collect_agent_events(service, "Trouve un créneau."))

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

    asyncio.run(
        _collect_agent_events(
            service,
            "Je prends 09:00.",
            conversation_history_json=json.dumps(history),
        )
    )

    assert service.conversation_history == [
        AgentConversationMessage.model_validate(message) for message in history
    ]


def test_agent_chat_returns_error_and_done_events_when_service_fails() -> None:
    class FailingAgentService:
        def stream_events(self, user_prompt: str, conversation_history=()):
            raise RuntimeError("Erreur simulée")
            yield  # pragma: no cover

    events = asyncio.run(
        _collect_agent_events(FailingAgentService(), "Trouve un créneau.")
    )

    assert [(event.event, event.data) for event in events] == [
        ("error", {"message": "Une erreur est survenue pendant le traitement."}),
        ("done", {"status": "error"}),
    ]


def test_agent_chat_returns_error_event_for_a_blank_prompt() -> None:
    events = asyncio.run(_collect_agent_events(FakeAgentService(), "   "))

    assert [(event.event, event.data) for event in events] == [
        ("error", {"message": "Le message utilisateur ne peut pas être vide."}),
        ("done", {"status": "error"}),
    ]
