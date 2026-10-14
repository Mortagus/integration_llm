import json
from collections.abc import Mapping
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
