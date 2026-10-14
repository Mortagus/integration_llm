from pydantic import BaseModel, Field


class RagSource(BaseModel):
    id: str
    title: str
    excerpt: str


class RagAskResponse(BaseModel):
    content: str
    sources: list[RagSource] = Field(default_factory=list)
