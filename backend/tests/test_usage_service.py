from __future__ import annotations

from app.tracking.usage_service import (
    build_stream_usage_snapshot,
    extract_usage_snapshot,
    normalize_provider_usage,
)


def test_normalize_provider_usage_gemini_openai_compat_with_reasoning() -> None:
    usage = {
        "prompt_tokens": 102_475,
        "completion_tokens": 45,
        "total_tokens": 102_924,
        "completion_tokens_details": {"reasoning_tokens": 404},
    }

    snapshot = normalize_provider_usage(usage)

    assert snapshot.input_tokens == 102_475
    assert snapshot.output_tokens == 449
    assert snapshot.total_tokens == 102_924
    assert snapshot.token_source == "provider_reported"


def test_normalize_provider_usage_prefers_provider_total_over_sum() -> None:
    usage = {
        "prompt_tokens": 7,
        "completion_tokens": 2,
        "total_tokens": 183,
    }

    snapshot = normalize_provider_usage(usage)

    assert snapshot.input_tokens == 7
    assert snapshot.output_tokens == 2
    assert snapshot.total_tokens == 183


def test_normalize_provider_usage_derives_output_from_total_when_needed() -> None:
    usage = {
        "prompt_tokens": 7,
        "completion_tokens": 0,
        "total_tokens": 68,
    }

    snapshot = normalize_provider_usage(usage)

    assert snapshot.input_tokens == 7
    assert snapshot.output_tokens == 61
    assert snapshot.total_tokens == 68


def test_extract_usage_snapshot_uses_provider_usage() -> None:
    snapshot = extract_usage_snapshot(
        {"messages": [{"role": "user", "content": "tiny"}]},
        {
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 150,
                "completion_tokens_details": {"reasoning_tokens": 30},
            },
        },
    )

    assert snapshot.input_tokens == 100
    assert snapshot.output_tokens == 50
    assert snapshot.total_tokens == 150
    assert snapshot.token_source == "provider_reported"


def test_extract_usage_snapshot_falls_back_to_estimates() -> None:
    snapshot = extract_usage_snapshot(
        {"messages": [{"role": "user", "content": "abcd"}]},
        {"choices": [{"message": {"role": "assistant", "content": "efgh"}}]},
    )

    assert snapshot.input_tokens == 1
    assert snapshot.output_tokens == 1
    assert snapshot.total_tokens == 2
    assert snapshot.token_source == "estimated"


def test_build_stream_usage_snapshot_uses_provider_usage() -> None:
    snapshot = build_stream_usage_snapshot(
        {"messages": [{"role": "user", "content": "x" * 100_000}]},
        "short",
        {
            "prompt_tokens": 102_475,
            "completion_tokens": 45,
            "total_tokens": 102_924,
            "completion_tokens_details": {"reasoning_tokens": 404},
        },
    )

    assert snapshot.input_tokens == 102_475
    assert snapshot.output_tokens == 449
    assert snapshot.total_tokens == 102_924
    assert snapshot.token_source == "provider_reported"


def test_build_stream_usage_snapshot_falls_back_without_usage() -> None:
    snapshot = build_stream_usage_snapshot(
        {"messages": [{"role": "user", "content": "abcd"}]},
        "efgh",
        None,
    )

    assert snapshot.token_source == "estimated"
    assert snapshot.input_tokens == 1
    assert snapshot.output_tokens == 1
