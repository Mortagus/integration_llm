from pydantic import BaseModel, Field


class CandidateParseResponse(BaseModel):
    skills: list[str]
    years_of_experience: float = Field(ge=0)
    education_level: str = Field(min_length=1)
    match_score: int = Field(ge=0, le=100)
    warning_points: list[str]
