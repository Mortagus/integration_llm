import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

from anthropic import Anthropic
from openai import OpenAI

from saas_rh.agent.service import AgentService
from saas_rh.interviews.repository import InterviewScheduleRepository
from saas_rh.interviews.schemas import InterviewSlotSearchInput
from saas_rh.interviews.service import InterviewService
from saas_rh.llm.gateway import AnthropicGateway, OpenAICompatibleGateway

USER_REQUEST = (
    "Trouve-moi un créneau le 2026-10-15 pour réserver un entretien avec "
    "Jean Dupont (jean.dupont@email.com)."
)
CONFIRMATION = (
    "Entretien confirmé pour Jean Dupont le 2026-10-15 à 09:00. "
    "Invitation envoyée à jean.dupont@email.com. "
    "Simulation de l'exercice : aucun e-mail réel n'a été envoyé."
)


class FakeOpenAIStream:
    def __init__(self, chunk):
        self.chunk = chunk

    def __enter__(self):
        return iter([self.chunk])

    def __exit__(self, *_args):
        return None


class FakeAnthropicStream:
    def __init__(self, response):
        self.response = response
        self.text_stream = iter(
            [block.text for block in response.content if block.type == "text"]
        )

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def get_final_message(self):
        return self.response


def _openai_response(content: str | None, tool_call=None):
    calls = [] if tool_call is None else [tool_call]
    chunk = SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=content,
                    tool_calls=[
                        SimpleNamespace(
                            index=0,
                            id=call.id,
                            function=call.function,
                        )
                        for call in calls
                    ]
                    or None,
                )
            )
        ]
    )
    return FakeOpenAIStream(chunk)


def _openai_tool_call(call_id: str, name: str, arguments: dict[str, str]):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(
            name=name,
            arguments=json.dumps(arguments),
        ),
    )


def _anthropic_response(block):
    return FakeAnthropicStream(SimpleNamespace(content=[block]))


def _anthropic_tool_use(
    call_id: str,
    name: str,
    arguments: dict[str, str],
):
    return SimpleNamespace(
        type="tool_use",
        id=call_id,
        name=name,
        input=arguments,
    )


def test_openai_agent_searches_and_reserves_before_confirming() -> None:
    client = OpenAI(api_key="test-api-key")
    client.chat.completions.create = Mock(
        side_effect=[
            _openai_response(
                None,
                _openai_tool_call(
                    "search-call",
                    "search_interview_slots",
                    {"date": "2026-10-15"},
                ),
            ),
            _openai_response(
                None,
                _openai_tool_call(
                    "reserve-call",
                    "reserve_interview_slot",
                    {
                        "candidate_name": "Jean Dupont",
                        "date": "2026-10-15",
                        "time": "09:00",
                        "email": "jean.dupont@email.com",
                    },
                ),
            ),
            _openai_response(CONFIRMATION),
        ]
    )
    interview_service = InterviewService(InterviewScheduleRepository())
    agent_service = AgentService(
        OpenAICompatibleGateway(client), "modele-test", interview_service
    )

    try:
        events = list(agent_service.stream_events(USER_REQUEST))
    finally:
        client.close()

    calls = client.chat.completions.create.call_args_list
    assert "".join(event.data.get("text", "") for event in events) == CONFIRMATION
    assert calls[0].kwargs["messages"][1]["content"] == USER_REQUEST
    final_call_messages = calls[2].kwargs["messages"]
    assert final_call_messages[-3]["role"] == "tool"
    assert json.loads(final_call_messages[-3]["content"]) == {
        "available_slots": ["09:00", "11:00", "14:30", "16:00"]
    }
    assert json.loads(final_call_messages[-1]["content"])["status"] == ("SUCCEEDED")
    assert (
        "09:00"
        not in interview_service.search_slots(
            InterviewSlotSearchInput(date=date(2026, 10, 15))
        ).available_slots
    )


def test_anthropic_agent_searches_and_reserves_before_confirming() -> None:
    client = Anthropic(api_key="test-api-key")
    client.messages.stream = Mock(
        side_effect=[
            _anthropic_response(
                _anthropic_tool_use(
                    "search-call",
                    "search_interview_slots",
                    {"date": "2026-10-15"},
                )
            ),
            _anthropic_response(
                _anthropic_tool_use(
                    "reserve-call",
                    "reserve_interview_slot",
                    {
                        "candidate_name": "Jean Dupont",
                        "date": "2026-10-15",
                        "time": "09:00",
                        "email": "jean.dupont@email.com",
                    },
                )
            ),
            _anthropic_response(SimpleNamespace(type="text", text=CONFIRMATION)),
        ]
    )
    interview_service = InterviewService(InterviewScheduleRepository())
    agent_service = AgentService(
        AnthropicGateway(client), "modele-test", interview_service
    )

    try:
        events = list(agent_service.stream_events(USER_REQUEST))
    finally:
        client.close()

    calls = client.messages.stream.call_args_list
    assert "".join(event.data.get("text", "") for event in events) == CONFIRMATION
    assert calls[0].kwargs["messages"][0]["content"] == USER_REQUEST
    final_call_messages = calls[2].kwargs["messages"]
    search_result = final_call_messages[-3]["content"][0]
    assert search_result["type"] == "tool_result"
    assert json.loads(search_result["content"])["available_slots"] == [
        "09:00",
        "11:00",
        "14:30",
        "16:00",
    ]
    reservation_result = final_call_messages[-1]["content"][0]
    assert json.loads(reservation_result["content"])["status"] == "SUCCEEDED"
    assert (
        "09:00"
        not in interview_service.search_slots(
            InterviewSlotSearchInput(date=date(2026, 10, 15))
        ).available_slots
    )
