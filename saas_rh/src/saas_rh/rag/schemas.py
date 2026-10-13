from pydantic import BaseModel


class RagAskResponse(BaseModel):
    content: str
