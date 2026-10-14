from pydantic import BaseModel, Field


class CandidateParseEvidence(BaseModel):
    """Facts extracted from a CV before calculating its match score."""

    skills: list[str]
    years_of_experience: float = Field(ge=0, le=50)
    education_level: str | None = None
    warning_points: list[str]
    leadership_evidence: list[str]


class CandidateParseResponse(BaseModel):
    skills: list[str]
    years_of_experience: float = Field(ge=0, le=50)
    education_level: str | None = None
    match_score: int = Field(ge=0, le=100)
    warning_points: list[str]
