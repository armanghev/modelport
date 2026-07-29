from __future__ import annotations

from app.tracking.usage_service import (
    UsageSnapshot,
    normalize_anthropic_shaped_usage,
    normalize_openai_shaped_usage,
)


def test_openai_cached_tokens_are_a_subset_of_prompt_tokens() -> None:
    snapshot = normalize_openai_shaped_usage(
        {
            "prompt_tokens": 1000,
            "completion_tokens": 200,
            "total_tokens": 1200,
            "prompt_tokens_details": {"cached_tokens": 800},
        }
    )

    assert snapshot.uncached_input_tokens == 200
    assert snapshot.cache_read_tokens == 800
    assert snapshot.input_tokens == 1000
    assert snapshot.output_tokens == 200


def test_openai_reasoning_tokens_fold_into_output() -> None:
    snapshot = normalize_openai_shaped_usage(
        {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "completion_tokens_details": {"reasoning_tokens": 400},
        }
    )

    assert snapshot.output_tokens == 450


def test_openai_falls_back_to_gemini_native_keys() -> None:
    snapshot = normalize_openai_shaped_usage(
        {
            "promptTokenCount": 500,
            "candidatesTokenCount": 100,
            "cachedContentTokenCount": 400,
        }
    )

    assert snapshot.uncached_input_tokens == 100
    assert snapshot.cache_read_tokens == 400


def test_anthropic_input_tokens_exclude_cache() -> None:
    snapshot = normalize_anthropic_shaped_usage(
        {
            "input_tokens": 50,
            "output_tokens": 300,
            "cache_read_input_tokens": 9000,
            "cache_creation_input_tokens": 1000,
        }
    )

    assert snapshot.uncached_input_tokens == 50
    assert snapshot.cache_read_tokens == 9000
    assert snapshot.cache_write_5m_tokens == 1000
    assert snapshot.input_tokens == 10050
    assert snapshot.total_tokens == 10350


def test_anthropic_splits_cache_writes_by_duration() -> None:
    snapshot = normalize_anthropic_shaped_usage(
        {
            "input_tokens": 10,
            "output_tokens": 20,
            "cache_creation": {
                "ephemeral_5m_input_tokens": 300,
                "ephemeral_1h_input_tokens": 700,
            },
        }
    )

    assert snapshot.cache_write_5m_tokens == 300
    assert snapshot.cache_write_1h_tokens == 700


def test_cache_read_never_exceeds_reported_prompt_tokens() -> None:
    snapshot = normalize_openai_shaped_usage(
        {"prompt_tokens": 100, "completion_tokens": 10, "prompt_tokens_details": {"cached_tokens": 999}}
    )

    assert snapshot.uncached_input_tokens == 0
    assert snapshot.cache_read_tokens == 100


def test_flat_constructor_puts_everything_in_uncached_input() -> None:
    snapshot = UsageSnapshot.flat(
        input_tokens=10, output_tokens=5, total_tokens=15, token_source="estimated"
    )

    assert snapshot.uncached_input_tokens == 10
    assert snapshot.cache_read_tokens == 0
    assert snapshot.input_tokens == 10
