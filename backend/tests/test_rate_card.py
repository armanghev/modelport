from __future__ import annotations

from decimal import Decimal

from app.pricing.rate_card import RateCard, TierRates


def _card() -> RateCard:
    return RateCard(
        standard=TierRates(
            input_per_1m=Decimal("3"),
            output_per_1m=Decimal("15"),
            cache_read_per_1m=Decimal("0.3"),
            cache_write_5m_per_1m=Decimal("3.75"),
            cache_write_1h_per_1m=Decimal("6"),
        ),
        above_threshold=TierRates(
            input_per_1m=Decimal("6"),
            output_per_1m=Decimal("22.5"),
        ),
        context_threshold_tokens=200_000,
        service_tiers={
            "batch": TierRates(input_per_1m=Decimal("1.5"), output_per_1m=Decimal("7.5")),
        },
        source="litellm",
    )


def test_context_tier_is_standard_at_or_below_threshold() -> None:
    assert _card().context_tier_for(200_000) == "standard"


def test_context_tier_is_above_threshold_past_the_boundary() -> None:
    assert _card().context_tier_for(200_001) == "above_threshold"


def test_context_tier_is_standard_when_card_has_no_threshold() -> None:
    card = RateCard(
        standard=TierRates(input_per_1m=Decimal("1"), output_per_1m=Decimal("2")),
        source="litellm",
    )
    assert card.context_tier_for(5_000_000) == "standard"


def test_rates_for_prefers_service_tier_over_context_tier() -> None:
    rates = _card().rates_for(context_tier="above_threshold", service_tier="batch")
    assert rates.input_per_1m == Decimal("1.5")


def test_rates_for_falls_back_to_standard_when_service_tier_unknown() -> None:
    rates = _card().rates_for(context_tier="standard", service_tier="priority")
    assert rates.input_per_1m == Decimal("3")


def test_rates_for_uses_above_threshold_rates() -> None:
    rates = _card().rates_for(context_tier="above_threshold", service_tier="standard")
    assert rates.output_per_1m == Decimal("22.5")


def test_card_survives_a_json_round_trip() -> None:
    restored = RateCard.model_validate_json(_card().model_dump_json())
    assert restored.standard.cache_read_per_1m == Decimal("0.3")
    assert restored.context_threshold_tokens == 200_000
