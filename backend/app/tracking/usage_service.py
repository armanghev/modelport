from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class UsageSnapshot:
    uncached_input_tokens: int
    cache_read_tokens: int
    cache_write_5m_tokens: int
    cache_write_1h_tokens: int
    output_tokens: int
    total_tokens: int
    token_source: str | None

    @property
    def input_tokens(self) -> int:
        return (
            self.uncached_input_tokens
            + self.cache_read_tokens
            + self.cache_write_5m_tokens
            + self.cache_write_1h_tokens
        )

    @classmethod
    def flat(
        cls,
        *,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        token_source: str | None,
    ) -> "UsageSnapshot":
        """Snapshot for paths with no cache detail (estimates, legacy call sites)."""
        return cls(
            uncached_input_tokens=input_tokens,
            cache_read_tokens=0,
            cache_write_5m_tokens=0,
            cache_write_1h_tokens=0,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            token_source=token_source,
        )


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


def _extract_cached_tokens(usage: dict[str, Any]) -> int:
    details = usage.get("prompt_tokens_details")
    if isinstance(details, dict):
        cached = _coerce_int(details.get("cached_tokens"))
        if cached > 0:
            return cached

    for key in ("cachedContentTokenCount", "cached_content_token_count"):
        cached = _coerce_int(usage.get(key))
        if cached > 0:
            return cached

    return 0


def normalize_openai_shaped_usage(usage: dict[str, Any]) -> UsageSnapshot:
    """OpenAI-shaped usage: prompt_tokens already includes cached tokens."""
    prompt_tokens = _extract_input_tokens(usage)
    completion_tokens = _extract_completion_tokens(usage)
    reasoning_tokens = _extract_reasoning_tokens(usage)
    output_tokens = completion_tokens + reasoning_tokens if reasoning_tokens > 0 else completion_tokens

    cache_read = min(_extract_cached_tokens(usage), prompt_tokens)
    uncached_input = max(0, prompt_tokens - cache_read)

    provider_total = _extract_total_tokens(usage)
    if provider_total > 0:
        total_tokens = provider_total
        if output_tokens == 0 and prompt_tokens > 0:
            output_tokens = max(0, provider_total - prompt_tokens)
    else:
        total_tokens = prompt_tokens + output_tokens

    return UsageSnapshot(
        uncached_input_tokens=uncached_input,
        cache_read_tokens=cache_read,
        cache_write_5m_tokens=0,
        cache_write_1h_tokens=0,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        token_source="provider_reported",
    )


def normalize_anthropic_shaped_usage(usage: dict[str, Any]) -> UsageSnapshot:
    """Anthropic-shaped usage: input_tokens EXCLUDES cached tokens."""
    uncached_input = _coerce_int(usage.get("input_tokens"))
    cache_read = _coerce_int(usage.get("cache_read_input_tokens"))

    cache_creation = usage.get("cache_creation")
    if isinstance(cache_creation, dict):
        write_5m = _coerce_int(cache_creation.get("ephemeral_5m_input_tokens"))
        write_1h = _coerce_int(cache_creation.get("ephemeral_1h_input_tokens"))
    else:
        write_5m = _coerce_int(usage.get("cache_creation_input_tokens"))
        write_1h = 0

    output_tokens = _coerce_int(usage.get("output_tokens"))

    return UsageSnapshot(
        uncached_input_tokens=uncached_input,
        cache_read_tokens=cache_read,
        cache_write_5m_tokens=write_5m,
        cache_write_1h_tokens=write_1h,
        output_tokens=output_tokens,
        total_tokens=uncached_input + cache_read + write_5m + write_1h + output_tokens,
        token_source="provider_reported",
    )


def normalize_provider_usage(usage: dict[str, Any]) -> UsageSnapshot:
    return normalize_openai_shaped_usage(usage)


def build_stream_usage_snapshot(
    request_payload: dict,
    output_text: str,
    usage: dict | None,
) -> UsageSnapshot:
    if isinstance(usage, dict):
        return normalize_provider_usage(usage)

    input_tokens = estimate_request_tokens(request_payload)
    output_tokens = estimate_token_count(output_text)
    return UsageSnapshot.flat(
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
    return UsageSnapshot.flat(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        token_source="estimated",
    )
