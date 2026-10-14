import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from anthropic import Anthropic
from openai import OpenAI
from pydantic import ValidationError

from saas_rh.interviews.schemas import (
    InterviewReservationInput,
    InterviewReservationResult,
    InterviewReservationStatus,
    InterviewSlotSearchInput,
)
from saas_rh.interviews.service import InterviewService
from saas_rh.interviews.tools import anthropic_interview_tools, openai_interview_tools

AGENT_SYSTEM_PROMPT = (
    "Tu es un assistant de recrutement. Aide à planifier les entretiens en "
    "utilisant les outils métier. Cherche toujours les créneaux avant de "
    "réserver et ne choisis que parmi ceux retournés pour la date demandée. "
    "Ne confirme jamais une réservation si l'outil ne retourne pas le statut "
    "SUCCEEDED. Si une information nécessaire manque, demande-la à l'utilisateur."
)


@dataclass(frozen=True)
class AgentStreamEvent:
    """One event produced while the agent handles a request."""

    event_type: str
    data: dict[str, Any]


class AgentToolLoopLimitError(RuntimeError):
    """Raised when the model keeps requesting tools without finishing."""


class AgentService:
    """Run an LLM tool-calling loop against the interview scheduling service."""

    def __init__(
        self,
        llm_client: OpenAI | Anthropic,
        model_name: str,
        interview_service: InterviewService,
        max_tool_rounds: int = 5,
    ) -> None:
        if max_tool_rounds < 1:
            raise ValueError("max_tool_rounds doit être supérieur ou égal à 1.")
        self.llm_client = llm_client
        self.model_name = model_name
        self.interview_service = interview_service
        self.max_tool_rounds = max_tool_rounds

    def respond(self, user_prompt: str) -> str:
        """Return a final answer after any requested tools have been executed."""
        if not user_prompt.strip():
            raise ValueError("Le message utilisateur ne peut pas être vide.")

        searched_slots: dict[str, list[str]] = {}
        if isinstance(self.llm_client, Anthropic):
            return self._respond_with_anthropic(user_prompt, searched_slots)
        return self._respond_with_openai(user_prompt, searched_slots)

    def stream_events(self, user_prompt: str) -> Iterator[AgentStreamEvent]:
        """Yield text, tool activity, and completion events for one request."""
        if not user_prompt.strip():
            raise ValueError("Le message utilisateur ne peut pas être vide.")

        searched_slots: dict[str, list[str]] = {}
        if isinstance(self.llm_client, Anthropic):
            yield from self._stream_with_anthropic(user_prompt, searched_slots)
        else:
            yield from self._stream_with_openai(user_prompt, searched_slots)

    def _stream_with_openai(
        self,
        user_prompt: str,
        searched_slots: dict[str, list[str]],
    ) -> Iterator[AgentStreamEvent]:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        tools = openai_interview_tools()

        for tool_round in range(self.max_tool_rounds + 1):
            assembled_tool_calls: dict[int, dict[str, str]] = {}
            received_text = False
            with self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                parallel_tool_calls=False,
                temperature=0.0,
                stream=True,
            ) as response_stream:
                for chunk in response_stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta.content:
                        received_text = True
                        yield AgentStreamEvent("text", {"text": delta.content})
                    for tool_delta in delta.tool_calls or []:
                        tool_call = assembled_tool_calls.setdefault(
                            tool_delta.index,
                            {"id": "", "name": "", "arguments": ""},
                        )
                        if tool_delta.id:
                            tool_call["id"] = tool_delta.id
                        if tool_delta.function and tool_delta.function.name:
                            tool_call["name"] += tool_delta.function.name
                        if tool_delta.function and tool_delta.function.arguments:
                            tool_call["arguments"] += tool_delta.function.arguments

            tool_calls = [
                assembled_tool_calls[index]
                for index in sorted(assembled_tool_calls)
            ]
            if not tool_calls:
                if not received_text:
                    raise ValueError("L'agent n'a pas retourné de réponse textuelle.")
                yield AgentStreamEvent("done", {"status": "completed"})
                return
            if tool_round == self.max_tool_rounds:
                raise AgentToolLoopLimitError(
                    "L'agent a dépassé la limite d'appels d'outils."
                )

            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call["id"],
                            "type": "function",
                            "function": {
                                "name": call["name"],
                                "arguments": call["arguments"],
                            },
                        }
                        for call in tool_calls
                    ],
                }
            )
            for call in tool_calls:
                yield AgentStreamEvent("tool_call", {"name": call["name"]})
                result = self._execute_tool(
                    call["name"],
                    call["arguments"],
                    searched_slots,
                )
                yield AgentStreamEvent(
                    "tool_result",
                    {"name": call["name"], "result": result},
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

        raise AgentToolLoopLimitError("L'agent a dépassé la limite d'appels d'outils.")

    def _stream_with_anthropic(
        self,
        user_prompt: str,
        searched_slots: dict[str, list[str]],
    ) -> Iterator[AgentStreamEvent]:
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
        tools = anthropic_interview_tools()

        for tool_round in range(self.max_tool_rounds + 1):
            with self.llm_client.messages.stream(
                model=self.model_name,
                max_tokens=1024,
                system=AGENT_SYSTEM_PROMPT,
                messages=messages,
                tools=tools,
            ) as response_stream:
                for text_fragment in response_stream.text_stream:
                    yield AgentStreamEvent("text", {"text": text_fragment})
                response = response_stream.get_final_message()

            tool_uses = [
                block for block in response.content if block.type == "tool_use"
            ]
            if not tool_uses:
                if not any(block.type == "text" for block in response.content):
                    raise ValueError("L'agent n'a pas retourné de réponse textuelle.")
                yield AgentStreamEvent("done", {"status": "completed"})
                return
            if tool_round == self.max_tool_rounds:
                raise AgentToolLoopLimitError(
                    "L'agent a dépassé la limite d'appels d'outils."
                )

            messages.append(
                {
                    "role": "assistant",
                    "content": [
                        self._anthropic_block_as_dict(block)
                        for block in response.content
                    ],
                }
            )
            tool_results = []
            for tool_use in tool_uses:
                yield AgentStreamEvent("tool_call", {"name": tool_use.name})
                result = self._execute_tool(
                    tool_use.name,
                    tool_use.input,
                    searched_slots,
                )
                yield AgentStreamEvent(
                    "tool_result",
                    {"name": tool_use.name, "result": result},
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(result, ensure_ascii=False),
                        "is_error": "error" in result,
                    }
                )
            messages.append({"role": "user", "content": tool_results})

        raise AgentToolLoopLimitError("L'agent a dépassé la limite d'appels d'outils.")

    def _respond_with_openai(
        self,
        user_prompt: str,
        searched_slots: dict[str, list[str]],
    ) -> str:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        tools = openai_interview_tools()

        for tool_round in range(self.max_tool_rounds + 1):
            response = self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                parallel_tool_calls=False,
                temperature=0.0,
            )
            message = response.choices[0].message
            tool_calls = message.tool_calls or []
            if not tool_calls:
                if not message.content or not message.content.strip():
                    raise ValueError("L'agent n'a pas retourné de réponse textuelle.")
                return message.content.strip()
            if tool_round == self.max_tool_rounds:
                raise AgentToolLoopLimitError(
                    "L'agent a dépassé la limite d'appels d'outils."
                )

            messages.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.function.name,
                                "arguments": call.function.arguments,
                            },
                        }
                        for call in tool_calls
                    ],
                }
            )
            for call in tool_calls:
                result = self._execute_tool(
                    call.function.name,
                    call.function.arguments,
                    searched_slots,
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

        raise AgentToolLoopLimitError("L'agent a dépassé la limite d'appels d'outils.")

    def _respond_with_anthropic(
        self,
        user_prompt: str,
        searched_slots: dict[str, list[str]],
    ) -> str:
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
        tools = anthropic_interview_tools()

        for tool_round in range(self.max_tool_rounds + 1):
            response = self.llm_client.messages.create(
                model=self.model_name,
                max_tokens=1024,
                system=AGENT_SYSTEM_PROMPT,
                messages=messages,
                tools=tools,
            )
            tool_uses = [
                block for block in response.content if block.type == "tool_use"
            ]
            if not tool_uses:
                answer = "\n".join(
                    block.text for block in response.content if block.type == "text"
                )
                if not answer.strip():
                    raise ValueError("L'agent n'a pas retourné de réponse textuelle.")
                return answer.strip()
            if tool_round == self.max_tool_rounds:
                raise AgentToolLoopLimitError(
                    "L'agent a dépassé la limite d'appels d'outils."
                )

            messages.append(
                {
                    "role": "assistant",
                    "content": [
                        self._anthropic_block_as_dict(block)
                        for block in response.content
                    ],
                }
            )
            tool_results = []
            for tool_use in tool_uses:
                result = self._execute_tool(
                    tool_use.name,
                    tool_use.input,
                    searched_slots,
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(result, ensure_ascii=False),
                        "is_error": "error" in result,
                    }
                )
            messages.append({"role": "user", "content": tool_results})

        raise AgentToolLoopLimitError("L'agent a dépassé la limite d'appels d'outils.")

    @staticmethod
    def _anthropic_block_as_dict(block: Any) -> dict[str, Any]:
        if hasattr(block, "model_dump"):
            return block.model_dump(exclude_none=True)
        if isinstance(block, dict):
            return block
        if hasattr(block, "__dict__"):
            return vars(block)
        raise TypeError("Bloc de réponse Anthropic non pris en charge.")

    def _execute_tool(
        self,
        tool_name: str,
        raw_arguments: str | Mapping[str, Any],
        searched_slots: dict[str, list[str]],
    ) -> dict[str, Any]:
        try:
            arguments = (
                json.loads(raw_arguments)
                if isinstance(raw_arguments, str)
                else raw_arguments
            )
            if not isinstance(arguments, Mapping):
                return {"error": "Les arguments de l'outil doivent être un objet."}

            if tool_name == "search_interview_slots":
                request = InterviewSlotSearchInput.model_validate(arguments)
                result = self.interview_service.search_slots(request)
                searched_slots[request.date.isoformat()] = result.available_slots
                return result.model_dump(mode="json")

            if tool_name == "reserve_interview_slot":
                request = InterviewReservationInput.model_validate(arguments)
                interview_date = request.date.isoformat()
                interview_time = request.time.strftime("%H:%M")
                if interview_time not in searched_slots.get(interview_date, []):
                    return InterviewReservationResult(
                        status=InterviewReservationStatus.UNAVAILABLE,
                        message=(
                            "Ce créneau n'a pas été retourné par une recherche "
                            "pour cette date. Recherchez les disponibilités avant "
                            "toute réservation."
                        ),
                    ).model_dump(mode="json")

                result = self.interview_service.reserve_slot(request)
                if result.status is InterviewReservationStatus.SUCCEEDED:
                    searched_slots[interview_date].remove(interview_time)
                return result.model_dump(mode="json")

            return {"error": f"Outil inconnu : {tool_name}."}
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
            return {"error": "Arguments invalides pour l'outil demandé."}
