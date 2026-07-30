from __future__ import annotations

from decimal import Decimal

from app.pricing.calculator import RequestContext, price
from app.pricing.rate_card import RateCard, TierRates, ToolCharge
from app.tracking.usage_service import UsageSnapshot


def sonnet_card() -> RateCard:
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
            cache_read_per_1m=Decimal("0.6"),
        ),
        context_threshold_tokens=200_000,
        source="litellm",
    )


def test_cache_heavy_anthropic_request_is_priced_on_cache_rates() -> None:
    usage = UsageSnapshot(
        uncached_input_tokens=1_000,
        cache_read_tokens=190_000,
        cache_write_5m_tokens=9_000,
        cache_write_1h_tokens=0,
        output_tokens=2_000,
        total_tokens=202_000,
        token_source="provider_reported",
    )

    breakdown = price(usage, sonnet_card(), RequestContext())

    assert breakdown.input_usd == Decimal("0.003000")
    assert breakdown.cache_read_usd == Decimal("0.057000")
    assert breakdown.cache_write_usd == Decimal("0.033750")
    assert breakdown.output_usd == Decimal("0.030000")
    assert breakdown.total_usd == Decimal("0.123750")
    assert breakdown.context_tier == "standard"


def test_components_always_sum_to_the_total() -> None:
    usage = UsageSnapshot(
        uncached_input_tokens=333,
        cache_read_tokens=777,
        cache_write_5m_tokens=111,
        cache_write_1h_tokens=222,
        output_tokens=999,
        total_tokens=2_442,
        token_source="provider_reported",
    )

    breakdown = price(usage, sonnet_card(), RequestContext())

    assert (
        breakdown.input_usd
        + breakdown.output_usd
        + breakdown.cache_read_usd
        + breakdown.cache_write_usd
        + breakdown.tools_usd
    ) == breakdown.total_usd


def test_total_is_not_distorted_by_component_rounding() -> None:
    card = RateCard(
        standard=TierRates(
            input_per_1m=Decimal("0.5"),
            output_per_1m=Decimal("0.5"),
        ),
        source="litellm",
    )
    usage = UsageSnapshot(1, 0, 0, 0, 1, 2, "provider_reported")

    breakdown = price(usage, card, RequestContext())

    assert breakdown.input_usd == Decimal("0.0000005")
    assert breakdown.output_usd == Decimal("0.0000005")
    assert breakdown.total_usd == Decimal("0.0000010")


def test_crossing_the_context_threshold_uses_above_threshold_rates() -> None:
    usage = UsageSnapshot(
        uncached_input_tokens=200_001,
        cache_read_tokens=0,
        cache_write_5m_tokens=0,
        cache_write_1h_tokens=0,
        output_tokens=1_000,
        total_tokens=201_001,
        token_source="provider_reported",
    )

    breakdown = price(usage, sonnet_card(), RequestContext())

    assert breakdown.context_tier == "above_threshold"
    assert breakdown.output_usd == Decimal("0.022500")


def test_one_hour_cache_writes_use_the_one_hour_rate() -> None:
    # Stays under the 200k threshold so the standard tier (which carries a 1h rate) applies.
    usage = UsageSnapshot(
        uncached_input_tokens=0,
        cache_read_tokens=0,
        cache_write_5m_tokens=0,
        cache_write_1h_tokens=100_000,
        output_tokens=0,
        total_tokens=100_000,
        token_source="provider_reported",
    )

    breakdown = price(usage, sonnet_card(), RequestContext())

    assert breakdown.context_tier == "standard"
    assert breakdown.cache_write_usd == Decimal("0.600000")


def test_card_without_cache_rates_contributes_zero_for_cache_tokens() -> None:
    card = RateCard(
        standard=TierRates(input_per_1m=Decimal("1"), output_per_1m=Decimal("2")),
        source="litellm",
    )
    usage = UsageSnapshot(
        uncached_input_tokens=1_000_000,
        cache_read_tokens=1_000_000,
        cache_write_5m_tokens=1_000_000,
        cache_write_1h_tokens=0,
        output_tokens=0,
        total_tokens=3_000_000,
        token_source="provider_reported",
    )

    breakdown = price(usage, card, RequestContext())

    assert breakdown.cache_read_usd == Decimal("0.000000")
    assert breakdown.cache_write_usd == Decimal("0.000000")
    assert breakdown.total_usd == Decimal("1.000000")


def test_tool_calls_add_per_call_charges() -> None:
    card = RateCard(
        standard=TierRates(input_per_1m=Decimal("0"), output_per_1m=Decimal("0")),
        tools=[ToolCharge(name="web_search", per_call_usd=Decimal("0.01"))],
        source="litellm",
    )
    usage = UsageSnapshot(0, 0, 0, 0, 0, 0, "provider_reported")

    breakdown = price(usage, card, RequestContext(tool_calls={"web_search": 3}))

    assert breakdown.tools_usd == Decimal("0.030000")


def test_operation_units_price_modality_only_requests() -> None:
    card = RateCard(
        operation_rates={"image_output": Decimal("0.04")},
        source="litellm",
    )

    breakdown = price(
        None,
        card,
        RequestContext(operation_units={"image_output": 2}),
    )

    assert breakdown.modalities_usd == Decimal("0.08")
    assert breakdown.total_usd == Decimal("0.08")


def test_unknown_service_tier_falls_back_to_standard() -> None:
    # 100k keeps this on the standard context tier, isolating the service-tier fallback.
    usage = UsageSnapshot(100_000, 0, 0, 0, 0, 100_000, "provider_reported")

    breakdown = price(usage, sonnet_card(), RequestContext(service_tier="nonexistent"))

    assert breakdown.input_usd == Decimal("0.300000")
    assert breakdown.service_tier == "nonexistent"
