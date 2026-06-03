from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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


def _coerce_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _extract_reasoning_tokens(usage: dict[str, Any]) -> int:
    completion_details = usage.get("completion_tokens_details")
    if isinstance(completion_details, dict):
        reasoning = _coerce_int(completion_details.get("reasoning_tokens"))
        if reasoning > 0:
            return reasoning

    for key in ("thoughts_token_count", "thoughtsTokenCount", "thought_tokens"):
        reasoning = _coerce_int(usage.get(key))
        if reasoning > 0:
            return reasoning

    return 0


def _extract_input_tokens(usage: dict[str, Any]) -> int:
    for key in ("prompt_tokens", "promptTokenCount", "prompt_token_count", "input_tokens"):
        value = _coerce_int(usage.get(key))
        if value > 0:
            return value
    return 0


def _extract_completion_tokens(usage: dict[str, Any]) -> int:
    for key in ("completion_tokens", "candidatesTokenCount", "candidates_token_count", "output_tokens"):
        value = _coerce_int(usage.get(key))
        if value > 0:
            return value
    return 0


def _extract_total_tokens(usage: dict[str, Any]) -> int:
    for key in ("total_tokens", "totalTokenCount", "total_token_count"):
        value = _coerce_int(usage.get(key))
        if value > 0:
            return value
    return 0


def normalize_provider_usage(usage: dict[str, Any]) -> UsageSnapshot:
    input_tokens = _extract_input_tokens(usage)
    completion_tokens = _extract_completion_tokens(usage)
    reasoning_tokens = _extract_reasoning_tokens(usage)
    provider_total = _extract_total_tokens(usage)

    if reasoning_tokens > 0:
        output_tokens = completion_tokens + reasoning_tokens
    else:
        output_tokens = completion_tokens

    if provider_total > 0:
        total_tokens = provider_total
        if output_tokens == 0 and input_tokens > 0:
            output_tokens = max(0, provider_total - input_tokens)
    else:
        total_tokens = input_tokens + output_tokens

    return UsageSnapshot(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        token_source="provider_reported",
    )


def build_stream_usage_snapshot(
    request_payload: dict,
    output_text: str,
    usage: dict | None,
) -> UsageSnapshot:
    if isinstance(usage, dict):
        return normalize_provider_usage(usage)

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
        return normalize_provider_usage(usage)

    input_tokens = estimate_request_tokens(request_payload)
    output_tokens = estimate_response_tokens(response_payload)
    return UsageSnapshot(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        token_source="estimated",
    )
