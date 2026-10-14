from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from anthropic import Anthropic
from openai import OpenAI

from saas_rh.agent.schemas import AgentConversationMessage
from saas_rh.agent.service import AgentService
from saas_rh.interviews.repository import InterviewScheduleRepository
from saas_rh.interviews.schemas import InterviewSlotSearchInput
from saas_rh.interviews.service import InterviewService
from saas_rh.llm.gateway import AnthropicGateway, OpenAICompatibleGateway


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


def openai_chunk(content=None, tool_call=None):
    tool_calls = (
        [
            SimpleNamespace(
                index=0,
                id=tool_call.id,
                function=tool_call.function,
            )
        ]
        if tool_call
        else None
    )
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=content, tool_calls=tool_calls)
            )
        ]
    )


def test_openai_agent_streams_final_text_after_a_tool_result() -> None:
    client = OpenAI(api_key="test-api-key")
    tool_call = SimpleNamespace(
        id="call-search",
        function=SimpleNamespace(
            name="search_interview_slots", arguments='{"date":"2026-10-15"}'
        ),
    )
    client.chat.completions.create = Mock(
        side_effect=[
            FakeStream([openai_chunk(tool_call=tool_call)]),
            FakeStream(
                [
                    openai_chunk(
                        "Les créneaux disponibles sont 09:00, 11:00, 14:30 et 16:00."
                    )
                ]
            ),
        ]
    )
    service = AgentService(
        llm_gateway=OpenAICompatibleGateway(client),
        model_name="modele-test",
        interview_service=InterviewService(InterviewScheduleRepository()),
    )

    try:
        events = list(service.stream_events("Quels sont les créneaux le 2026-10-15 ?"))
    finally:
        client.close()

    assert "".join(event.data.get("text", "") for event in events) == (
        "Les créneaux disponibles sont 09:00, 11:00, 14:30 et 16:00."
    )
    assert client.chat.completions.create.call_count == 2
    second_call_messages = client.chat.completions.create.call_args_list[1].kwargs[
        "messages"
    ]
    assert second_call_messages[-1]["role"] == "tool"
    assert (
        '"available_slots": ["09:00", "11:00", "14:30", "16:00"]'
        in (second_call_messages[-1]["content"])
    )


def test_anthropic_agent_streams_final_text_after_a_tool_result() -> None:
    client = Anthropic(api_key="test-api-key")
    client.messages.stream = Mock(
        side_effect=[
            FakeAnthropicStream(
                [],
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
            ),
            FakeAnthropicStream(
                ["Il reste quatre créneaux disponibles."],
                SimpleNamespace(
                    content=[
                        SimpleNamespace(
                            type="text", text="Il reste quatre créneaux disponibles."
                        )
                    ]
                ),
            ),
        ]
    )
    service = AgentService(
        llm_gateway=AnthropicGateway(client),
        model_name="modele-test",
        interview_service=InterviewService(InterviewScheduleRepository()),
    )

    try:
        events = list(service.stream_events("Quels sont les créneaux le 2026-10-15 ?"))
    finally:
        client.close()

    assert "".join(event.data.get("text", "") for event in events) == (
        "Il reste quatre créneaux disponibles."
    )
    assert client.messages.stream.call_count == 2
    second_call_messages = client.messages.stream.call_args_list[1].kwargs["messages"]
    assert second_call_messages[-1]["role"] == "user"
    assert second_call_messages[-1]["content"][0]["type"] == "tool_result"
    assert second_call_messages[-1]["content"][0]["tool_use_id"] == "tool-search"


def test_agent_stops_when_model_exceeds_tool_round_limit() -> None:
    client = OpenAI(api_key="test-api-key")
    tool_call = SimpleNamespace(
        id="call-search",
        function=SimpleNamespace(
            name="search_interview_slots", arguments='{"date":"2026-10-15"}'
        ),
    )
    client.chat.completions.create = Mock(
        return_value=FakeStream([openai_chunk(tool_call=tool_call)])
    )
    service = AgentService(
        llm_gateway=OpenAICompatibleGateway(client),
        model_name="modele-test",
        interview_service=InterviewService(InterviewScheduleRepository()),
        max_tool_rounds=1,
    )

    try:
        with pytest.raises(RuntimeError, match="limite d'appels d'outils"):
            list(service.stream_events("Trouve un créneau."))
    finally:
        client.close()

    assert client.chat.completions.create.call_count == 2


def test_agent_refuses_to_reserve_a_slot_not_returned_by_search() -> None:
    client = OpenAI(api_key="test-api-key")
    tool_call = SimpleNamespace(
        id="call-reserve",
        function=SimpleNamespace(
            name="reserve_interview_slot",
            arguments=(
                '{"candidate_name":"Jean Dupont","date":"2026-10-15",'
                '"time":"09:00","email":"jean.dupont@email.com"}'
            ),
        ),
    )
    client.chat.completions.create = Mock(
        side_effect=[
            FakeStream([openai_chunk(tool_call=tool_call)]),
            FakeStream([openai_chunk("Je n'ai pas pu effectuer la réservation.")]),
        ]
    )
    interview_service = InterviewService(InterviewScheduleRepository())
    service = AgentService(
        llm_gateway=OpenAICompatibleGateway(client),
        model_name="modele-test",
        interview_service=interview_service,
    )

    try:
        events = list(
            service.stream_events("Réserve le créneau de 09:00 pour Jean Dupont.")
        )
    finally:
        client.close()

    tool_result = client.chat.completions.create.call_args_list[1].kwargs["messages"][
        -1
    ]["content"]
    assert "".join(event.data.get("text", "") for event in events) == (
        "Je n'ai pas pu effectuer la réservation."
    )
    assert '"status": "UNAVAILABLE"' in tool_result
    assert (
        interview_service.search_slots(
            InterviewSlotSearchInput(date="2026-10-15")
        ).available_slots[0]
        == "09:00"
    )


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
                delta=SimpleNamespace(
                    content="Quatre créneaux sont disponibles.", tool_calls=None
                )
            )
        ]
    )
    client.chat.completions.create = Mock(
        side_effect=[FakeStream([tool_call_chunk]), FakeStream([final_text_chunk])]
    )
    service = AgentService(
        llm_gateway=OpenAICompatibleGateway(client),
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
            SimpleNamespace(content=[SimpleNamespace(type="text", text="Bonjour !")]),
        )
    )
    service = AgentService(
        llm_gateway=AnthropicGateway(client),
        model_name="modele-test",
        interview_service=InterviewService(InterviewScheduleRepository()),
    )
    history = [
        AgentConversationMessage(role="user", content="Je cherche un créneau."),
        AgentConversationMessage(role="assistant", content="09:00 est disponible."),
    ]

    try:
        events = list(service.stream_events("Je choisis 09:00.", history))
    finally:
        client.close()

    assert [(event.event_type, event.data) for event in events] == [
        ("text", {"text": "Bonjour"}),
        ("text", {"text": " !"}),
        ("done", {"status": "completed"}),
    ]
    assert client.messages.stream.call_args.kwargs["messages"] == [
        {"role": "user", "content": "Je cherche un créneau."},
        {"role": "assistant", "content": "09:00 est disponible."},
        {"role": "user", "content": "Je choisis 09:00."},
    ]


def test_openai_agent_includes_previous_turns_in_the_next_request() -> None:
    client = OpenAI(api_key="test-api-key")
    response_chunk = SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content="Je vérifie ce créneau.", tool_calls=None)
            )
        ]
    )
    client.chat.completions.create = Mock(return_value=FakeStream([response_chunk]))
    service = AgentService(
        llm_gateway=OpenAICompatibleGateway(client),
        model_name="modele-test",
        interview_service=InterviewService(InterviewScheduleRepository()),
    )
    conversation_history = [
        AgentConversationMessage(
            role="user",
            content=(
                "Trouve un créneau le 2026-10-15 pour Jean Dupont "
                "(jean.dupont@email.com)."
            ),
        ),
        AgentConversationMessage(
            role="assistant",
            content="Les créneaux disponibles sont 09:00 et 11:00.",
        ),
    ]

    try:
        list(
            service.stream_events(
                "Je prends 09:00.",
                conversation_history=conversation_history,
            )
        )
    finally:
        client.close()

    messages = client.chat.completions.create.call_args.kwargs["messages"]
    assert messages[1:3] == [message.model_dump() for message in conversation_history]
    assert messages[3] == {"role": "user", "content": "Je prends 09:00."}
