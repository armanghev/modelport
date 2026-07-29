from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from app.pricing.catalog_import import build_rate_cards

FIXTURE = Path(__file__).parent / "fixtures" / "litellm_subset.json"


def _cards() -> dict[tuple[str, str], object]:
    return build_rate_cards(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_anthropic_model_maps_to_the_anthropic_provider() -> None:
    card = _cards()[("anthropic", "claude-sonnet-4-6")]

    assert card.standard.input_per_1m == Decimal("3")
    assert card.standard.output_per_1m == Decimal("15")
    assert card.standard.cache_read_per_1m == Decimal("0.3")
    assert card.standard.cache_write_5m_per_1m == Decimal("3.75")
    assert card.standard.cache_write_1h_per_1m == Decimal("6")
    assert card.source == "litellm"


def test_context_threshold_and_above_rates_are_parsed() -> None:
    card = _cards()[("anthropic", "claude-sonnet-4-6")]

    assert card.context_threshold_tokens == 200_000
    assert card.above_threshold.input_per_1m == Decimal("6")
    assert card.above_threshold.cache_read_per_1m == Decimal("0.6")


def test_openai_272k_threshold_and_batch_tier_are_parsed() -> None:
    card = _cards()[("openai", "gpt-5.6-sol")]

    assert card.context_threshold_tokens == 272_000
    assert card.above_threshold.output_per_1m == Decimal("45")
    assert card.service_tiers["batch"].input_per_1m == Decimal("2.5")


def test_gemini_models_are_registered_under_both_id_forms() -> None:
    cards = _cards()

    assert ("gemini", "gemini-2.5-flash") in cards
    assert ("gemini", "models/gemini-2.5-flash") in cards


def test_non_chat_modes_are_skipped() -> None:
    assert ("openai", "text-embedding-3-small") not in _cards()


def test_entries_without_base_rates_are_skipped_without_raising() -> None:
    assert ("openai", "broken-entry") not in _cards()


def test_sample_spec_placeholder_is_skipped() -> None:
    assert not any(model == "sample_spec" for _, model in _cards())
