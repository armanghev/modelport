from __future__ import annotations

from fastapi import HTTPException, status

from app.schemas.anthropic import (
    AnthropicMessageResponse,
    AnthropicResponseContentBlock,
    AnthropicUsage,
)

STOP_REASON_MAP = {
    "stop": "end_turn",
    "length": "max_tokens",
    "tool_calls": "tool_use",
}


def extract_text_content(content: object) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    text_parts.append(item["text"])
                elif item.get("type") == "output_text" and isinstance(item.get("text"), str):
                    text_parts.append(item["text"])
        return "\n".join(text_parts)
    return str(content)


def translate_openai_chat_completion_to_anthropic(
    payload: dict,
    requested_model: str,
) -> AnthropicMessageResponse:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream provider returned no completion choices.",
        )

    first_choice = choices[0]
    message = first_choice.get("message") if isinstance(first_choice, dict) else None
    if not isinstance(message, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream provider returned an invalid completion payload.",
        )

    content_text = extract_text_content(message.get("content"))
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    finish_reason = first_choice.get("finish_reason") if isinstance(first_choice, dict) else None

    return AnthropicMessageResponse(
        id=str(payload.get("id") or "msg_generated"),
        model=requested_model,
        content=[AnthropicResponseContentBlock(text=content_text)],
        stop_reason=STOP_REASON_MAP.get(str(finish_reason), "end_turn") if finish_reason else "end_turn",
        stop_sequence=None,
        usage=AnthropicUsage(
            input_tokens=int(usage.get("prompt_tokens", 0) or 0),
            output_tokens=int(usage.get("completion_tokens", 0) or 0),
        ),
    )
