from __future__ import annotations

import json

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


def format_sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


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


class AnthropicStreamTranslator:
    def __init__(self, *, requested_model: str, input_tokens: int) -> None:
        self.requested_model = requested_model
        self.input_tokens = input_tokens
        self.response_id = "msg_generated"
        self.stop_reason = "end_turn"
        self.output_tokens = 0
        self.content_started = False
        self.text_parts: list[str] = []
        self.completion_reason: str | None = None

    def _start_events(self) -> list[str]:
        if self.content_started:
            return []

        self.content_started = True
        return [
            format_sse_event(
                "message_start",
                {
                    "type": "message_start",
                    "message": {
                        "id": self.response_id,
                        "type": "message",
                        "role": "assistant",
                        "model": self.requested_model,
                        "content": [],
                        "stop_reason": None,
                        "stop_sequence": None,
                        "usage": {
                            "input_tokens": self.input_tokens,
                            "output_tokens": 0,
                        },
                    },
                },
            ),
            format_sse_event(
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "text", "text": ""},
                },
            ),
        ]

    def consume_chunk(self, chunk: dict) -> list[str]:
        events = []
        if chunk.get("id"):
            self.response_id = str(chunk["id"])

        choices = chunk.get("choices")
        if not isinstance(choices, list) or not choices:
            return events

        first_choice = choices[0] if isinstance(choices[0], dict) else {}
        delta = first_choice.get("delta") if isinstance(first_choice, dict) else {}
        finish_reason = first_choice.get("finish_reason") if isinstance(first_choice, dict) else None
        usage = chunk.get("usage") if isinstance(chunk.get("usage"), dict) else {}

        events.extend(self._start_events())

        content_text = ""
        if isinstance(delta, dict):
            raw_content = delta.get("content")
            if isinstance(raw_content, str):
                content_text = raw_content
            elif isinstance(raw_content, list):
                content_text = extract_text_content(raw_content)

        if content_text:
            self.text_parts.append(content_text)
            events.append(
                format_sse_event(
                    "content_block_delta",
                    {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "text_delta", "text": content_text},
                    },
                )
            )

        if finish_reason:
            self.completion_reason = str(finish_reason)
            self.stop_reason = STOP_REASON_MAP.get(str(finish_reason), "end_turn")
        if usage:
            self.output_tokens = int(usage.get("completion_tokens", self.output_tokens) or self.output_tokens)

        return events

    def finish_events(self) -> list[str]:
        events = self._start_events()
        events.extend(
            [
                format_sse_event(
                    "content_block_stop",
                    {"type": "content_block_stop", "index": 0},
                ),
                format_sse_event(
                    "message_delta",
                    {
                        "type": "message_delta",
                        "delta": {
                            "stop_reason": self.stop_reason,
                            "stop_sequence": None,
                        },
                        "usage": {"output_tokens": self.output_tokens},
                    },
                ),
                format_sse_event("message_stop", {"type": "message_stop"}),
            ]
        )
        return events
