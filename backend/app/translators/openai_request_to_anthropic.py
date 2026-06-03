from __future__ import annotations

from app.schemas.anthropic import AnthropicMessage, AnthropicMessageCreate
from app.schemas.openai import OpenAIChatCompletionCreate, OpenAITextPart


def flatten_openai_text_parts(parts: list[OpenAITextPart]) -> str:
    return "\n".join(part.text for part in parts if part.text)


def normalize_openai_content(content: str | list[OpenAITextPart]) -> str:
    if isinstance(content, str):
        return content
    return flatten_openai_text_parts(content)


def translate_openai_chat_completion_request_to_anthropic(
    payload: OpenAIChatCompletionCreate,
) -> AnthropicMessageCreate:
    system_messages: list[str] = []
    messages: list[AnthropicMessage] = []

    for message in payload.messages:
        normalized_content = normalize_openai_content(message.content)
        if message.role == "system":
            if normalized_content:
                system_messages.append(normalized_content)
            continue

        messages.append(
            AnthropicMessage(
                role=message.role,
                content=normalized_content,
            )
        )

    system = "\n\n".join(system_messages) if system_messages else None
    return AnthropicMessageCreate(
        provider=payload.provider,
        fallback_providers=payload.fallback_providers,
        model=payload.model,
        max_tokens=payload.max_tokens,
        system=system,
        messages=messages,
        stream=payload.stream,
    )
