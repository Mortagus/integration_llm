from datetime import date as Date
from datetime import time as Time
from enum import StrEnum

from pydantic import BaseModel, Field


class InterviewSlotSearchInput(BaseModel):
    """Arguments accepted by the tool that searches interview availability."""

    date: Date = Field(description="Date to search, in YYYY-MM-DD format.")


class InterviewReservationInput(BaseModel):
    """Arguments accepted by the tool that reserves an interview slot."""

    candidate_name: str = Field(min_length=1, description="Candidate's full name.")
    date: Date = Field(description="Interview date, in YYYY-MM-DD format.")
    time: Time = Field(description="Available interview time, in HH:MM format.")
    email: str = Field(
        min_length=3,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        description="Candidate's email address.",
    )


class InterviewReservationStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    UNAVAILABLE = "UNAVAILABLE"


class InterviewReservationResult(BaseModel):
    """Outcome returned by the reservation tool."""

    status: InterviewReservationStatus
    message: str


class InterviewsSlotsResponse(BaseModel):
    available_slots: list[str]
