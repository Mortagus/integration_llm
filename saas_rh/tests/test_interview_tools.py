from saas_rh.interviews.tools import (
    anthropic_interview_tools,
    openai_interview_tools,
)


def test_openai_tools_describe_search_and_reservation_arguments() -> None:
    tools = openai_interview_tools()

    assert [tool["function"]["name"] for tool in tools] == [
        "search_interview_slots",
        "reserve_interview_slot",
    ]
    search_schema = tools[0]["function"]["parameters"]
    reservation_schema = tools[1]["function"]["parameters"]
    assert search_schema["required"] == ["date"]
    assert reservation_schema["required"] == [
        "candidate_name",
        "date",
        "time",
        "email",
    ]


def test_anthropic_tools_use_input_schema_for_the_same_arguments() -> None:
    tools = anthropic_interview_tools()

    assert [tool["name"] for tool in tools] == [
        "search_interview_slots",
        "reserve_interview_slot",
    ]
    assert tools[0]["input_schema"]["required"] == ["date"]
    assert tools[1]["input_schema"]["required"] == [
        "candidate_name",
        "date",
        "time",
        "email",
    ]
