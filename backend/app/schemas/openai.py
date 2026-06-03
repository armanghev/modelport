from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class OpenAITextPart(BaseModel):
    type: Literal["text"]
    text: str


class OpenAIChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str | list[OpenAITextPart]


class OpenAIChatCompletionCreate(BaseModel):
    provider: str | None = None
    fallback_providers: list[str] = []
    model: str
    max_tokens: int | None = None
    messages: list[OpenAIChatMessage]
    stream: bool = False


class OpenAIChatCompletionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    model: str
    choices: list[dict]
    usage: dict | None = None
    object: str | None = None
    created: int | None = None
