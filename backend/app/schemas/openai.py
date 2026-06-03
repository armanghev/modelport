from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class OpenAITextPart(BaseModel):
    type: Literal["text"]
    text: str


class OpenAIFunctionCall(BaseModel):
    name: str
    arguments: str


class OpenAIToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: OpenAIFunctionCall


class OpenAIFunctionDefinition(BaseModel):
    name: str
    description: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class OpenAIToolDefinition(BaseModel):
    type: Literal["function"] = "function"
    function: OpenAIFunctionDefinition


class OpenAIChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[OpenAITextPart] | None = None
    tool_calls: list[OpenAIToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class OpenAIChatCompletionCreate(BaseModel):
    provider: str | None = None
    fallback_providers: list[str] = []
    model: str
    max_tokens: int | None = None
    messages: list[OpenAIChatMessage]
    stream: bool = False
    tools: list[OpenAIToolDefinition] | None = None
    tool_choice: str | dict[str, Any] | None = None


class OpenAIChatCompletionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    model: str
    choices: list[dict]
    usage: dict | None = None
    object: str | None = None
    created: int | None = None
