from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UsageSnapshot:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    token_source: str | None


def estimate_token_count(text: str) -> int:
    normalized = text.strip()
    if not normalized:
        return 0
    return max(1, round(len(normalized) / 4))


def estimate_request_tokens(payload: dict) -> int:
    total = 0
    for message in payload.get("messages", []):
        content = message.get("content")
        if isinstance(content, str):
            total += estimate_token_count(content)
    return total


def estimate_response_tokens(payload: dict) -> int:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return 0
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return 0
    message = first_choice.get("message")
    if not isinstance(message, dict):
        return 0
    content = message.get("content")
    if isinstance(content, str):
        return estimate_token_count(content)
    return 0


def build_stream_usage_snapshot(
    request_payload: dict,
    output_text: str,
    usage: dict | None,
) -> UsageSnapshot:
    if isinstance(usage, dict):
        input_tokens = int(usage.get("prompt_tokens", 0) or 0)
        output_tokens = int(usage.get("completion_tokens", 0) or 0)
        return UsageSnapshot(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            token_source="provider_reported",
        )

    input_tokens = estimate_request_tokens(request_payload)
    output_tokens = estimate_token_count(output_text)
    return UsageSnapshot(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        token_source="estimated",
    )


def extract_usage_snapshot(
    request_payload: dict,
    response_payload: dict,
) -> UsageSnapshot:
    usage = response_payload.get("usage")
    if isinstance(usage, dict):
        input_tokens = int(usage.get("prompt_tokens", 0) or 0)
        output_tokens = int(usage.get("completion_tokens", 0) or 0)
        return UsageSnapshot(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            token_source="provider_reported",
        )

    input_tokens = estimate_request_tokens(request_payload)
    output_tokens = estimate_response_tokens(response_payload)
    return UsageSnapshot(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        token_source="estimated",
    )
