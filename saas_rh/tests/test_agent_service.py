from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from anthropic import Anthropic
from openai import OpenAI

from saas_rh.agent.service import AgentService
from saas_rh.interviews.repository import InterviewScheduleRepository
from saas_rh.interviews.schemas import InterviewSlotSearchInput
from saas_rh.interviews.service import InterviewService


class FakeStream:
    def __init__(self, chunks):
        self.chunks = chunks

    def __enter__(self):
        return iter(self.chunks)

    def __exit__(self, *_args):
        return None


class FakeAnthropicStream:
    def __init__(self, text_fragments, final_message):
        self.text_stream = iter(text_fragments)
        self.final_message = final_message

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def get_final_message(self):
        return self.final_message


def test_openai_agent_returns_final_text_after_a_tool_result() -> None:
    client = OpenAI(api_key="test-api-key")
    client.chat.completions.create = Mock(
        side_effect=[
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    id="call-search",
                                    function=SimpleNamespace(
                                        name="search_interview_slots",
                                        arguments='{"date":"2026-10-15"}',
                                    ),
                                )
                            ],
                        )
                    )
                ]
            ),
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content="Les créneaux disponibles sont 09:00, 11:00, 14:30 et 16:00.",
                            tool_calls=[],
                        )
                    )
                ]
            ),
        ]
    )
    service = AgentService(
        llm_client=client,
        model_name="modele-test",
        interview_service=InterviewService(InterviewScheduleRepository()),
    )

    try:
        answer = service.respond("Quels sont les créneaux le 2026-10-15 ?")
    finally:
        client.close()

    assert answer == "Les créneaux disponibles sont 09:00, 11:00, 14:30 et 16:00."
    assert client.chat.completions.create.call_count == 2
    second_call_messages = client.chat.completions.create.call_args_list[1].kwargs[
        "messages"
    ]
    assert second_call_messages[-1]["role"] == "tool"
    assert '"available_slots": ["09:00", "11:00", "14:30", "16:00"]' in (
        second_call_messages[-1]["content"]
    )


def test_anthropic_agent_returns_final_text_after_a_tool_result() -> None:
    client = Anthropic(api_key="test-api-key")
    client.messages.create = Mock(
        side_effect=[
            SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="tool_use",
                        id="tool-search",
                        name="search_interview_slots",
                        input={"date": "2026-10-15"},
                    )
                ]
            ),
            SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="text",
                        text="Il reste quatre créneaux disponibles.",
                    )
                ]
            ),
        ]
    )
    service = AgentService(
        llm_client=client,
        model_name="modele-test",
        interview_service=InterviewService(InterviewScheduleRepository()),
    )

    try:
        answer = service.respond("Quels sont les créneaux le 2026-10-15 ?")
    finally:
        client.close()

    assert answer == "Il reste quatre créneaux disponibles."
    assert client.messages.create.call_count == 2
    second_call_messages = client.messages.create.call_args_list[1].kwargs["messages"]
    assert second_call_messages[-1]["role"] == "user"
    assert second_call_messages[-1]["content"][0]["type"] == "tool_result"
    assert second_call_messages[-1]["content"][0]["tool_use_id"] == "tool-search"


def test_agent_stops_when_model_exceeds_tool_round_limit() -> None:
    client = OpenAI(api_key="test-api-key")
    client.chat.completions.create = Mock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                id="call-search",
                                function=SimpleNamespace(
                                    name="search_interview_slots",
                                    arguments='{"date":"2026-10-15"}',
                                ),
                            )
                        ],
                    )
                )
            ]
        )
    )
    service = AgentService(
        llm_client=client,
        model_name="modele-test",
        interview_service=InterviewService(InterviewScheduleRepository()),
        max_tool_rounds=1,
    )

    try:
        with pytest.raises(RuntimeError, match="limite d'appels d'outils"):
            service.respond("Trouve un créneau.")
    finally:
        client.close()

    assert client.chat.completions.create.call_count == 2


def test_agent_refuses_to_reserve_a_slot_not_returned_by_search() -> None:
    client = OpenAI(api_key="test-api-key")
    client.chat.completions.create = Mock(
        side_effect=[
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    id="call-reserve",
                                    function=SimpleNamespace(
                                        name="reserve_interview_slot",
                                        arguments=(
                                            '{"candidate_name":"Jean Dupont",'
                                            '"date":"2026-10-15",'
                                            '"time":"09:00",'
                                            '"email":"jean.dupont@email.com"}'
                                        ),
                                    ),
                                )
                            ],
                        )
                    )
                ]
            ),
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content="Je n'ai pas pu effectuer la réservation.",
                            tool_calls=[],
                        )
                    )
                ]
            ),
        ]
    )
    interview_service = InterviewService(InterviewScheduleRepository())
    service = AgentService(
        llm_client=client,
        model_name="modele-test",
        interview_service=interview_service,
    )

    try:
        answer = service.respond("Réserve le créneau de 09:00 pour Jean Dupont.")
    finally:
        client.close()

    tool_result = client.chat.completions.create.call_args_list[1].kwargs[
        "messages"
    ][-1]["content"]
    assert answer == "Je n'ai pas pu effectuer la réservation."
    assert '"status": "UNAVAILABLE"' in tool_result
    assert interview_service.search_slots(
        InterviewSlotSearchInput(date="2026-10-15")
    ).available_slots[0] == "09:00"


def test_openai_agent_streams_tool_activity_and_final_text() -> None:
    client = OpenAI(api_key="test-api-key")
    tool_call_chunk = SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            index=0,
                            id="call-search",
                            function=SimpleNamespace(
                                name="search_interview_slots",
                                arguments='{"date":"2026-10-15"}',
                            ),
                        )
                    ],
                )
            )
        ]
    )
    final_text_chunk = SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content="Quatre créneaux sont disponibles.", tool_calls=None)
            )
        ]
    )
    client.chat.completions.create = Mock(
        side_effect=[FakeStream([tool_call_chunk]), FakeStream([final_text_chunk])]
    )
    service = AgentService(
        llm_client=client,
        model_name="modele-test",
        interview_service=InterviewService(InterviewScheduleRepository()),
    )

    try:
        events = list(service.stream_events("Quels sont les créneaux le 2026-10-15 ?"))
    finally:
        client.close()

    assert [event.event_type for event in events] == [
        "tool_call",
        "tool_result",
        "text",
        "done",
    ]
    assert events[0].data == {"name": "search_interview_slots"}
    assert events[1].data["result"]["available_slots"] == [
        "09:00",
        "11:00",
        "14:30",
        "16:00",
    ]
    assert events[2].data == {"text": "Quatre créneaux sont disponibles."}


def test_anthropic_agent_streams_text_and_completion() -> None:
    client = Anthropic(api_key="test-api-key")
    client.messages.stream = Mock(
        return_value=FakeAnthropicStream(
            ["Bonjour", " !"],
            SimpleNamespace(
                content=[SimpleNamespace(type="text", text="Bonjour !")]
            ),
        )
    )
    service = AgentService(
        llm_client=client,
        model_name="modele-test",
        interview_service=InterviewService(InterviewScheduleRepository()),
    )

    try:
        events = list(service.stream_events("Bonjour"))
    finally:
        client.close()

    assert [(event.event_type, event.data) for event in events] == [
        ("text", {"text": "Bonjour"}),
        ("text", {"text": " !"}),
        ("done", {"status": "completed"}),
    ]
