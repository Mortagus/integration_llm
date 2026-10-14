import asyncio

from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient

from saas_rh.api.dependencies import get_interview_service
from saas_rh.api.routers.interviews import router
from saas_rh.interviews.repository import InterviewScheduleRepository
from saas_rh.interviews.service import InterviewService


async def _get_interview_service() -> InterviewService:
    return InterviewService(InterviewScheduleRepository())


app = FastAPI()
app.include_router(router)
app.dependency_overrides[get_interview_service] = _get_interview_service


async def _get_response(params: dict[str, object]):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        return await client.get("/api/interviews/slots", params=params)


def test_get_interviews_slots_returns_available_slots() -> None:
    response = asyncio.run(
        _get_response({"candidate_id": 42, "date": "2026-10-15"})
    )

    assert response.status_code == 200
    assert response.json() == {
        "available_slots": ["09:00", "11:00", "14:30", "16:00"]
    }


def test_get_interviews_slots_returns_empty_list_when_no_slots_exist() -> None:
    response = asyncio.run(
        _get_response({"candidate_id": 42, "date": "2026-10-17"})
    )

    assert response.status_code == 200
    assert response.json() == {"available_slots": []}


def test_get_interviews_slots_requires_valid_candidate_id_and_date() -> None:
    response = asyncio.run(
        _get_response({"candidate_id": 0, "date": "not-a-date"})
    )

    assert response.status_code == 422
