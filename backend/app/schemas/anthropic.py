from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class AnthropicTextBlock(BaseModel):
    type: Literal["text"]
    text: str


class AnthropicMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str | list[AnthropicTextBlock]


class AnthropicMessageCreate(BaseModel):
    provider: str | None = None
    fallback_providers: list[str] = []
    model: str
    max_tokens: int | None = None
    system: str | list[AnthropicTextBlock] | None = None
    messages: list[AnthropicMessage]
    stream: bool = False


class AnthropicResponseContentBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str


class AnthropicUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class AnthropicMessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    type: Literal["message"] = "message"
    role: Literal["assistant"] = "assistant"
    model: str
    content: list[AnthropicResponseContentBlock]
    stop_reason: Literal["end_turn", "max_tokens", "tool_use"] | None = None
    stop_sequence: str | None = None
    usage: AnthropicUsage
