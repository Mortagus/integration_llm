from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from saas_rh.interviews.schemas import (
    InterviewReservationInput,
    InterviewSlotSearchInput,
)


@dataclass(frozen=True)
class InterviewToolDefinition:
    """Provider-independent description of an interview tool."""

    name: str
    description: str
    input_model: type[BaseModel]


INTERVIEW_TOOL_DEFINITIONS = (
    InterviewToolDefinition(
        name="search_interview_slots",
        description=(
            "Recherche les heures disponibles pour une date. "
            "Appelez cet outil avant toute réservation et ne choisissez "
            "qu'une heure retournée par cette recherche."
        ),
        input_model=InterviewSlotSearchInput,
    ),
    InterviewToolDefinition(
        name="reserve_interview_slot",
        description=(
            "Réserve un créneau pour un candidat. Utilisez uniquement une "
            "heure précédemment retournée par search_interview_slots. "
            "Ne confirmez pas la réservation si le résultat indique un échec."
        ),
        input_model=InterviewReservationInput,
    ),
)


def openai_interview_tools() -> list[Any]:
    """Return tool definitions in OpenAI Chat Completions format."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_model.model_json_schema(),
            },
        }
        for tool in INTERVIEW_TOOL_DEFINITIONS
    ]


def anthropic_interview_tools() -> list[Any]:
    """Return tool definitions in Anthropic Messages format."""
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_model.model_json_schema(),
        }
        for tool in INTERVIEW_TOOL_DEFINITIONS
    ]
