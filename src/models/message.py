from typing import Literal, Any, Optional
from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["user", "system", "assistant", "tool"]
    content: str
    tool_calls: Optional[list[Any]] = None
    thinking: Optional[str] = None
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None


class ChatHistory(BaseModel):
    messages: list[Message] = Field(default_factory=list)
