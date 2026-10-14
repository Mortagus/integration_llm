from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentConversationMessage(BaseModel):
    """A text message from one participant in a browser chat history."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4_000)
