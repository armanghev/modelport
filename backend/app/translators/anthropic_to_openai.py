from __future__ import annotations

from app.schemas.anthropic import AnthropicMessageCreate, AnthropicTextBlock


def flatten_text_blocks(blocks: list[AnthropicTextBlock]) -> str:
    return "\n".join(block.text for block in blocks if block.text)


def normalize_content(content: str | list[AnthropicTextBlock]) -> str:
    if isinstance(content, str):
        return content
    return flatten_text_blocks(content)


def translate_anthropic_message_to_openai(
    payload: AnthropicMessageCreate,
    upstream_model: str,
) -> dict:
    translated_messages: list[dict[str, str]] = []

    if payload.system:
        system_text = normalize_content(payload.system)
        if system_text:
            translated_messages.append({"role": "system", "content": system_text})

    for message in payload.messages:
        translated_messages.append(
            {
                "role": message.role,
                "content": normalize_content(message.content),
            }
        )

    translated_payload = {
        "model": upstream_model,
        "messages": translated_messages,
        "stream": payload.stream,
    }
    if payload.max_tokens is not None:
        translated_payload["max_tokens"] = payload.max_tokens
    return translated_payload
