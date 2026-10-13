from datetime import date
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Query, status

from saas_rh.interviews.schemas import InterviewsSlotsResponse

router = APIRouter(
    prefix="/api/interviews",
    tags=["entretiens"],
)


@router.get(
    "/slots",
    response_model=InterviewsSlotsResponse,
    responses={501: {"description": "Interviews Slots non implémenté"}},
)
async def get_interviews_slots(
    candidate_id: Annotated[int, Query(gt=0)],
    interview_date: Annotated[date, Query(alias="date")],
) -> InterviewsSlotsResponse:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Interviews/Slots n'est pas encore implémenté.",
    )
