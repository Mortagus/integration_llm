from pydantic import BaseModel


class InterviewsSlotsResponse(BaseModel):
    available_slots: list
