from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    thread_id: str
    message: str = Field(min_length=1, max_length=4000)


class Source(BaseModel):
    title: str
    url: str


class ToolCall(BaseModel):
    tool_name: str
    tool_input: dict
    tool_output: str
    sources: list[Source] = []


class ChatMessage(BaseModel):
    role: str                           # "human" | "ai" | "tool"
    content: str
    tool_call: Optional[ToolCall] = None


class ChatHistoryRead(BaseModel):
    thread_id: str
    messages: list[ChatMessage]