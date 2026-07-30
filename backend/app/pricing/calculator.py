from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from app.pricing.rate_card import RateCard
from app.tracking.usage_service import UsageSnapshot

MILLION = Decimal(1_000_000)
COST_QUANTUM = Decimal("0.000001")


@dataclass(frozen=True)
class RequestContext:
    service_tier: str = "standard"
    tool_calls: dict[str, int] = field(default_factory=dict)
    operation_units: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class CostBreakdown:
    input_usd: Decimal
    output_usd: Decimal
    reasoning_usd: Decimal
    cache_read_usd: Decimal
    cache_write_usd: Decimal
    tools_usd: Decimal
    modalities_usd: Decimal
    total_usd: Decimal
    context_tier: str
    service_tier: str


def _component(tokens: int, rate: Decimal | None) -> Decimal:
    if tokens <= 0 or rate is None:
        return Decimal(0)
    return (Decimal(tokens) / MILLION) * rate


def to_storage_usd(value: Decimal) -> float:
    return float(value.quantize(COST_QUANTUM, rounding=ROUND_HALF_UP))


def price(
    usage: UsageSnapshot | None,
    card: RateCard,
    context: RequestContext,
) -> CostBreakdown:
    input_tokens = usage.input_tokens if usage is not None else 0
    context_tier = card.context_tier_for(input_tokens)
    rates = card.rates_for(context_tier=context_tier, service_tier=context.service_tier)

    input_usd = _component(usage.uncached_input_tokens, rates.input_per_1m) if usage and rates else Decimal(0)
    visible_output_tokens = max(0, usage.output_tokens - usage.reasoning_tokens) if usage else 0
    output_usd = _component(visible_output_tokens, rates.output_per_1m) if usage and rates else Decimal(0)
    reasoning_usd = _component(
        usage.reasoning_tokens,
        rates.reasoning_output_per_1m or rates.output_per_1m,
    ) if usage and rates else Decimal(0)
    cache_read_usd = _component(usage.cache_read_tokens, rates.cache_read_per_1m) if usage and rates else Decimal(0)
    cache_write_usd = (
        _component(usage.cache_write_5m_tokens, rates.cache_write_5m_per_1m)
        + _component(usage.cache_write_1h_tokens, rates.cache_write_1h_per_1m)
        if usage and rates
        else Decimal(0)
    )
    tools_usd = sum(
        (charge.per_call_usd * context.tool_calls.get(charge.name, 0) for charge in card.tools),
        Decimal(0),
    )
    modalities_usd = sum(
        (
            card.operation_rates.get(name, Decimal(0)) * count
            for name, count in context.operation_units.items()
            if count > 0
        ),
        Decimal(0),
    )

    # Keep full Decimal precision so the caller can round the total only once on write.
    total_usd = input_usd + output_usd + reasoning_usd + cache_read_usd + cache_write_usd + tools_usd + modalities_usd

    return CostBreakdown(
        input_usd=input_usd,
        output_usd=output_usd,
        reasoning_usd=reasoning_usd,
        cache_read_usd=cache_read_usd,
        cache_write_usd=cache_write_usd,
        tools_usd=tools_usd,
        modalities_usd=modalities_usd,
        total_usd=total_usd,
        context_tier=context_tier,
        service_tier=context.service_tier,
    )
