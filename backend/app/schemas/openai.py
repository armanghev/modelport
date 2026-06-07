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
    role: Literal["system", "developer", "user", "assistant", "tool"]
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
    temperature: float | None = None
    top_p: float | None = None
    stop: str | list[str] | None = None
    tools: list[OpenAIToolDefinition] | None = None
    tool_choice: str | dict[str, Any] | None = None
    response_format: dict[str, Any] | None = None
    user: str | None = None
    n: int | None = None
    seed: int | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    logit_bias: dict[str, float] | None = None
    logprobs: bool | None = None
    top_logprobs: int | None = None
    parallel_tool_calls: bool | None = None


class OpenAIChatCompletionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    model: str
    choices: list[dict]
    usage: dict | None = None
    object: str | None = None
    created: int | None = None


class OpenAIEmbeddingCreate(BaseModel):
    provider: str | None = None
    fallback_providers: list[str] = []
    model: str
    input: str | list[str]
    encoding_format: str | None = None
    dimensions: int | None = None
    user: str | None = None


class OpenAIResponseInputTextPart(BaseModel):
    type: Literal["input_text"]
    text: str


class OpenAIResponseInputMessage(BaseModel):
    role: Literal["system", "developer", "user", "assistant"]
    content: str | list[OpenAIResponseInputTextPart]


class OpenAIResponseCreate(BaseModel):
    provider: str | None = None
    fallback_providers: list[str] = []
    model: str
    input: str | list[OpenAIResponseInputMessage]
    instructions: str | None = None
    stream: bool = False
    max_output_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    tools: list[OpenAIToolDefinition] | None = None
    tool_choice: str | dict[str, Any] | None = None


class OpenAIResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    object: str
    status: str
    model: str
    output: list[dict]
    usage: dict | None = None
