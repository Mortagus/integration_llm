from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from saas_rh.api.dependencies import get_interview_service
from saas_rh.interviews.schemas import InterviewSlotSearchInput, InterviewsSlotsResponse
from saas_rh.interviews.service import InterviewService

router = APIRouter(
    prefix="/api/interviews",
    tags=["entretiens"],
)


@router.get(
    "/slots",
    response_model=InterviewsSlotsResponse,
)
async def get_interviews_slots(
    candidate_id: Annotated[int, Query(gt=0)],
    interview_date: Annotated[date, Query(alias="date")],
    interview_service: Annotated[InterviewService, Depends(get_interview_service)],
) -> InterviewsSlotsResponse:
    """List global recruiter availability for a validated candidate identifier.

    The mock schedule is not candidate-specific; candidate_id remains required
    by the existing endpoint contract but cannot be resolved to a candidate yet.
    """
    return interview_service.search_slots(
        InterviewSlotSearchInput(date=interview_date)
    )
