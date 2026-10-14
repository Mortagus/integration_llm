from saas_rh.interviews.repository import InterviewScheduleRepository
from saas_rh.interviews.schemas import (
    InterviewReservationInput,
    InterviewReservationResult,
    InterviewReservationStatus,
    InterviewSlotSearchInput,
    InterviewsSlotsResponse,
)


class InterviewService:
    """Apply interview scheduling rules using an injected schedule repository."""

    def __init__(self, repository: InterviewScheduleRepository) -> None:
        self.repository = repository

    def search_slots(
        self,
        request: InterviewSlotSearchInput,
    ) -> InterviewsSlotsResponse:
        available_slots = self.repository.get_available_slots(request.date.isoformat())
        return InterviewsSlotsResponse(available_slots=available_slots)

    def reserve_slot(
        self,
        request: InterviewReservationInput,
    ) -> InterviewReservationResult:
        interview_date = request.date.isoformat()
        interview_time = request.time.strftime("%H:%M")
        reserved = self.repository.reserve_slot(interview_date, interview_time)

        if not reserved:
            return InterviewReservationResult(
                status=InterviewReservationStatus.UNAVAILABLE,
                message="Créneau indisponible.",
            )

        return InterviewReservationResult(
            status=InterviewReservationStatus.SUCCEEDED,
            message=(
                f"Entretien confirmé pour {request.candidate_name} le "
                f"{interview_date} à {interview_time}. "
                f"Invitation envoyée à {request.email}."
            ),
        )
