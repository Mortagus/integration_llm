import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from anthropic import Anthropic
from anthropic import APIStatusError as AnthropicAPIStatusError
from openai import APIStatusError as OpenAIAPIStatusError
from openai import OpenAI
from pydantic import BaseModel

from saas_rh.interviews.tools import (
    anthropic_interview_tools,
    openai_interview_tools,
)

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMProviderStatusError(RuntimeError):
    def __init__(self, status_code: int, provider_message: str) -> None:
        self.status_code = status_code
        self.provider_message = provider_message
        super().__init__(provider_message)


@dataclass(frozen=True)
class LLMStreamEvent:
    """Provider-independent text or tool call returned during a chat turn."""

    event_type: str
    text: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    tool_arguments: str | Mapping[str, Any] | None = None


class LLMGateway(Protocol):
    def parse_structured(
        self,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
        schema: type[SchemaT],
    ) -> SchemaT | None: ...

    def complete(
        self, model_name: str, system_prompt: str, user_prompt: str
    ) -> str | None: ...

    def stream_with_tools(
        self,
        model_name: str,
        system_prompt: str,
        messages: Sequence[dict[str, Any]],
    ) -> Iterator[LLMStreamEvent]: ...


class OpenAICompatibleGateway:
    def __init__(self, client: OpenAI) -> None:
        self.client = client

    def parse_structured(
        self,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
        schema: type[SchemaT],
    ) -> SchemaT | None:
        try:
            response = self.client.chat.completions.parse(
                model=model_name,
                response_format=schema,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=4096,
                temperature=0.0,
            )
        except OpenAIAPIStatusError as error:
            raise LLMProviderStatusError(error.status_code, str(error)) from error
        return response.choices[0].message.parsed

    def complete(
        self, model_name: str, system_prompt: str, user_prompt: str
    ) -> str | None:
        response = self.client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1024,
            temperature=0.0,
        )
        return response.choices[0].message.content

    def stream_with_tools(
        self,
        model_name: str,
        system_prompt: str,
        messages: Sequence[dict[str, Any]],
    ) -> Iterator[LLMStreamEvent]:
        tool_definitions = openai_interview_tools()
        chat_messages: list[Any] = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]
        assembled_calls: dict[int, dict[str, str]] = {}
        with self.client.chat.completions.create(
            model=model_name,
            messages=chat_messages,
            tools=tool_definitions,
            tool_choice="auto",
            parallel_tool_calls=False,
            max_tokens=1024,
            temperature=0.0,
            stream=True,
        ) as response_stream:
            for chunk in response_stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    yield LLMStreamEvent("text", text=delta.content)
                for tool_delta in delta.tool_calls or []:
                    call = assembled_calls.setdefault(
                        tool_delta.index, {"id": "", "name": "", "arguments": ""}
                    )
                    if tool_delta.id:
                        call["id"] = tool_delta.id
                    if tool_delta.function and tool_delta.function.name:
                        call["name"] += tool_delta.function.name
                    if tool_delta.function and tool_delta.function.arguments:
                        call["arguments"] += tool_delta.function.arguments
        for call in (assembled_calls[index] for index in sorted(assembled_calls)):
            yield LLMStreamEvent(
                "tool_call",
                tool_call_id=call["id"],
                tool_name=call["name"],
                tool_arguments=call["arguments"],
            )


class AnthropicGateway:
    def __init__(self, client: Anthropic) -> None:
        self.client = client

    def parse_structured(
        self,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
        schema: type[SchemaT],
    ) -> SchemaT | None:
        try:
            response = self.client.messages.parse(
                model=model_name,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                output_format=schema,
            )
        except AnthropicAPIStatusError as error:
            raise LLMProviderStatusError(error.status_code, str(error)) from error
        return response.parsed_output

    def complete(
        self, model_name: str, system_prompt: str, user_prompt: str
    ) -> str | None:
        response = self.client.messages.create(
            model=model_name,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return "\n".join(
            block.text for block in response.content if block.type == "text"
        )

    def stream_with_tools(
        self,
        model_name: str,
        system_prompt: str,
        messages: Sequence[dict[str, Any]],
    ) -> Iterator[LLMStreamEvent]:
        tool_definitions = anthropic_interview_tools()
        anthropic_messages: list[Any] = self._messages_for_anthropic(messages)
        with self.client.messages.stream(
            model=model_name,
            max_tokens=1024,
            system=system_prompt,
            messages=anthropic_messages,
            tools=tool_definitions,
        ) as response_stream:
            for fragment in response_stream.text_stream:
                yield LLMStreamEvent("text", text=fragment)
            response = response_stream.get_final_message()
        for block in response.content:
            if block.type == "tool_use":
                yield LLMStreamEvent(
                    "tool_call",
                    tool_call_id=block.id,
                    tool_name=block.name,
                    tool_arguments=block.input,
                )

    @staticmethod
    def _messages_for_anthropic(
        messages: Sequence[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        for message in messages:
            if message["role"] == "assistant" and message.get("tool_calls"):
                assistant_content = []
                if message.get("content"):
                    assistant_content.append(
                        {"type": "text", "text": message["content"]}
                    )
                assistant_content.extend(
                    {
                        "type": "tool_use",
                        "id": call["id"],
                        "name": call["function"]["name"],
                        "input": json.loads(call["function"]["arguments"]),
                    }
                    for call in message["tool_calls"]
                )
                converted.append(
                    {
                        "role": "assistant",
                        "content": assistant_content,
                    }
                )
            elif message["role"] == "tool":
                tool_result = {
                    "type": "tool_result",
                    "tool_use_id": message["tool_call_id"],
                    "content": message["content"],
                    "is_error": "error" in json.loads(message["content"]),
                }
                if converted and converted[-1]["role"] == "user":
                    converted[-1]["content"].append(tool_result)
                else:
                    converted.append({"role": "user", "content": [tool_result]})
            else:
                converted.append(
                    {"role": message["role"], "content": message["content"]}
                )
        return converted
