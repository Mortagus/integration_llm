from concurrent.futures import ThreadPoolExecutor
from datetime import date, time

from saas_rh.interviews.repository import InterviewScheduleRepository
from saas_rh.interviews.schemas import (
    InterviewReservationInput,
    InterviewReservationStatus,
    InterviewSlotSearchInput,
)
from saas_rh.interviews.service import InterviewService


def test_search_slots_returns_available_times_for_known_date() -> None:
    service = InterviewService(InterviewScheduleRepository())

    result = service.search_slots(
        InterviewSlotSearchInput(date=date(2026, 10, 15))
    )

    assert result.available_slots == ["09:00", "11:00", "14:30", "16:00"]


def test_search_slots_returns_empty_list_for_unknown_date() -> None:
    service = InterviewService(InterviewScheduleRepository())

    result = service.search_slots(
        InterviewSlotSearchInput(date=date(2026, 10, 17))
    )

    assert result.available_slots == []


def test_reserve_slot_removes_it_from_available_slots() -> None:
    service = InterviewService(InterviewScheduleRepository())
    request = InterviewReservationInput(
        candidate_name="Jean Dupont",
        date=date(2026, 10, 15),
        time=time(9, 0),
        email="jean.dupont@email.com",
    )

    result = service.reserve_slot(request)

    assert result.status is InterviewReservationStatus.SUCCEEDED
    assert "2026-10-15 à 09:00" in result.message
    assert "jean.dupont@email.com" in result.message
    assert service.search_slots(
        InterviewSlotSearchInput(date=date(2026, 10, 15))
    ).available_slots == ["11:00", "14:30", "16:00"]


def test_reserve_slot_refuses_a_slot_that_was_already_reserved() -> None:
    service = InterviewService(InterviewScheduleRepository())
    request = InterviewReservationInput(
        candidate_name="Jean Dupont",
        date=date(2026, 10, 15),
        time=time(9, 0),
        email="jean.dupont@email.com",
    )

    first_result = service.reserve_slot(request)
    second_result = service.reserve_slot(request)

    assert first_result.status is InterviewReservationStatus.SUCCEEDED
    assert second_result.status is InterviewReservationStatus.UNAVAILABLE
    assert second_result.message == "Créneau indisponible."


def test_repository_returns_a_copy_of_available_slots() -> None:
    repository = InterviewScheduleRepository()

    returned_slots = repository.get_available_slots("2026-10-15")
    returned_slots.remove("09:00")

    assert repository.get_available_slots("2026-10-15") == [
        "09:00",
        "11:00",
        "14:30",
        "16:00",
    ]


def test_new_repository_starts_from_unmodified_initial_schedule() -> None:
    first_repository = InterviewScheduleRepository()
    assert first_repository.reserve_slot("2026-10-15", "09:00") is True

    second_repository = InterviewScheduleRepository()

    assert second_repository.get_available_slots("2026-10-15") == [
        "09:00",
        "11:00",
        "14:30",
        "16:00",
    ]


def test_concurrent_reservations_only_allow_one_winner() -> None:
    repository = InterviewScheduleRepository()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(
            executor.map(
                lambda _: repository.reserve_slot("2026-10-15", "09:00"),
                range(2),
            )
        )

    assert sorted(outcomes) == [False, True]
