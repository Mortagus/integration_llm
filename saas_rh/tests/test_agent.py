import asyncio
from types import SimpleNamespace

from saas_rh.api.routers.agent import agent_chat


class FakeAgentService:
    def __init__(self, events: list[SimpleNamespace] | None = None) -> None:
        self.events = events or []
        self.user_prompt: str | None = None

    def stream_events(self, user_prompt: str):
        self.user_prompt = user_prompt
        yield from self.events


async def _collect_agent_events(agent_service, user_prompt: str):
    return [
        event
        async for event in agent_chat(
            agent_service=agent_service,
            user_prompt=user_prompt,
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


def test_agent_chat_returns_error_and_done_events_when_service_fails() -> None:
    class FailingAgentService:
        def stream_events(self, user_prompt: str):
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
