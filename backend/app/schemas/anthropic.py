from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AnthropicTextBlock(BaseModel):
    type: Literal["text"]
    text: str


class AnthropicToolUseBlock(BaseModel):
    type: Literal["tool_use"]
    id: str
    name: str
    input: dict[str, Any] = Field(default_factory=dict)


class AnthropicToolResultBlock(BaseModel):
    type: Literal["tool_result"]
    tool_use_id: str
    content: str | list[AnthropicTextBlock]
    is_error: bool | None = None


AnthropicContentBlock = Annotated[
    AnthropicTextBlock | AnthropicToolUseBlock | AnthropicToolResultBlock,
    Field(discriminator="type"),
]


class AnthropicMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str | list[AnthropicContentBlock]


class AnthropicToolDefinition(BaseModel):
    name: str
    description: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)


class AnthropicMessageCreate(BaseModel):
    provider: str | None = None
    fallback_providers: list[str] = []
    model: str
    max_tokens: int | None = None
    system: str | list[AnthropicTextBlock] | None = None
    messages: list[AnthropicMessage]
    stream: bool = False
    tools: list[AnthropicToolDefinition] | None = None
    tool_choice: dict[str, Any] | None = None


class AnthropicResponseContentBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str


class AnthropicResponseToolUseBlock(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any] = Field(default_factory=dict)


AnthropicResponseContent = Annotated[
    AnthropicResponseContentBlock | AnthropicResponseToolUseBlock,
    Field(discriminator="type"),
]


class AnthropicUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class AnthropicMessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    type: Literal["message"] = "message"
    role: Literal["assistant"] = "assistant"
    model: str
    content: list[AnthropicResponseContentBlock | AnthropicResponseToolUseBlock]
    stop_reason: Literal["end_turn", "max_tokens", "tool_use"] | None = None
    stop_sequence: str | None = None
    usage: AnthropicUsage
