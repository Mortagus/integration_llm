from collections.abc import Mapping, Sequence
from threading import Lock

from saas_rh.data.interviews.mock_data import AGENDA_RECRUTEUR


class InterviewScheduleRepository:
    """Keep a process-local, mutable copy of the initial interview schedule."""

    def __init__(
        self,
        initial_schedule: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        schedule = AGENDA_RECRUTEUR if initial_schedule is None else initial_schedule
        self._available_slots = {
            interview_date: list(slots) for interview_date, slots in schedule.items()
        }
        self._lock = Lock()

    def get_available_slots(self, interview_date: str) -> list[str]:
        """Return a copy so callers cannot mutate the repository's state."""
        with self._lock:
            return list(self._available_slots.get(interview_date, []))

    def reserve_slot(self, interview_date: str, slot: str) -> bool:
        """Atomically remove a slot, returning whether it was available."""
        with self._lock:
            available_slots = self._available_slots.get(interview_date)
            if available_slots is None or slot not in available_slots:
                return False

            available_slots.remove(slot)
            return True
