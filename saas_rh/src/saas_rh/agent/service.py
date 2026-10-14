import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from saas_rh.agent.schemas import AgentConversationMessage
from saas_rh.interviews.schemas import (
    InterviewReservationInput,
    InterviewReservationResult,
    InterviewReservationStatus,
    InterviewSlotSearchInput,
)
from saas_rh.interviews.service import InterviewService
from saas_rh.llm.gateway import LLMGateway

AGENT_SYSTEM_PROMPT = (
    "Tu es un assistant de recrutement. Aide à planifier les entretiens en "
    "utilisant les outils métier. Pour chaque demande de réservation, cherche "
    "les créneaux pendant le tour courant, même si une recherche antérieure "
    "figure dans l'historique. Cherche toujours les créneaux avant de "
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
        llm_gateway: LLMGateway,
        model_name: str,
        interview_service: InterviewService,
        max_tool_rounds: int = 5,
    ) -> None:
        if max_tool_rounds < 1:
            raise ValueError("max_tool_rounds doit être supérieur ou égal à 1.")
        self.llm_gateway = llm_gateway
        self.model_name = model_name
        self.interview_service = interview_service
        self.max_tool_rounds = max_tool_rounds

    def stream_events(
        self,
        user_prompt: str,
        conversation_history: Sequence[AgentConversationMessage] = (),
    ) -> Iterator[AgentStreamEvent]:
        """Yield text, tool activity, and completion events for one request."""
        if not user_prompt.strip():
            raise ValueError("Le message utilisateur ne peut pas être vide.")

        yield from self._stream_with_tools(
            user_prompt,
            conversation_history,
        )

    def _stream_with_tools(
        self,
        user_prompt: str,
        conversation_history: Sequence[AgentConversationMessage],
    ) -> Iterator[AgentStreamEvent]:
        messages: list[dict[str, Any]] = [
            *(message.model_dump() for message in conversation_history),
            {"role": "user", "content": user_prompt},
        ]
        searched_slots: dict[str, list[str]] = {}
        for tool_round in range(self.max_tool_rounds + 1):
            received_text = False
            round_text = ""
            tool_calls: list[dict[str, Any]] = []
            for event in self.llm_gateway.stream_with_tools(
                self.model_name,
                AGENT_SYSTEM_PROMPT,
                messages,
            ):
                if event.event_type == "text" and event.text:
                    received_text = True
                    round_text += event.text
                    yield AgentStreamEvent("text", {"text": event.text})
                elif event.event_type == "tool_call":
                    tool_calls.append(
                        {
                            "id": event.tool_call_id,
                            "name": event.tool_name,
                            "arguments": event.tool_arguments,
                        }
                    )
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
                    "content": round_text or None,
                    "tool_calls": [
                        {
                            "id": call["id"],
                            "type": "function",
                            "function": {
                                "name": call["name"],
                                "arguments": (
                                    call["arguments"]
                                    if isinstance(call["arguments"], str)
                                    else json.dumps(
                                        call["arguments"], ensure_ascii=False
                                    )
                                ),
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
