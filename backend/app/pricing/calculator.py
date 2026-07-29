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


@dataclass(frozen=True)
class CostBreakdown:
    input_usd: Decimal
    output_usd: Decimal
    cache_read_usd: Decimal
    cache_write_usd: Decimal
    tools_usd: Decimal
    total_usd: Decimal
    context_tier: str
    service_tier: str


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(COST_QUANTUM, rounding=ROUND_HALF_UP)


def _component(tokens: int, rate: Decimal | None) -> Decimal:
    if tokens <= 0 or rate is None:
        return Decimal(0)
    return (Decimal(tokens) / MILLION) * rate


def price(
    usage: UsageSnapshot,
    card: RateCard,
    context: RequestContext,
) -> CostBreakdown:
    context_tier = card.context_tier_for(usage.input_tokens)
    rates = card.rates_for(context_tier=context_tier, service_tier=context.service_tier)

    input_usd = _quantize(_component(usage.uncached_input_tokens, rates.input_per_1m))
    output_usd = _quantize(_component(usage.output_tokens, rates.output_per_1m))
    cache_read_usd = _quantize(_component(usage.cache_read_tokens, rates.cache_read_per_1m))
    cache_write_usd = _quantize(
        _component(usage.cache_write_5m_tokens, rates.cache_write_5m_per_1m)
        + _component(usage.cache_write_1h_tokens, rates.cache_write_1h_per_1m)
    )
    tools_usd = _quantize(
        sum(
            (charge.per_call_usd * context.tool_calls.get(charge.name, 0) for charge in card.tools),
            Decimal(0),
        )
    )

    # Total is the sum of already-quantized components so the breakdown always reconciles.
    total_usd = input_usd + output_usd + cache_read_usd + cache_write_usd + tools_usd

    return CostBreakdown(
        input_usd=input_usd,
        output_usd=output_usd,
        cache_read_usd=cache_read_usd,
        cache_write_usd=cache_write_usd,
        tools_usd=tools_usd,
        total_usd=total_usd,
        context_tier=context_tier,
        service_tier=context.service_tier,
    )
