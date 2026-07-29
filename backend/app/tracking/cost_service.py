from __future__ import annotations

from decimal import Decimal

from pydantic import ValidationError

from app.database import PricingOverride
from app.pricing.calculator import RequestContext, price
from app.pricing.rate_card import RateCard, TierRates
from app.tracking.usage_service import UsageSnapshot


def _legacy_flat_cost(
    pricing: PricingOverride,
    input_tokens: int,
    output_tokens: int,
) -> tuple[float | None, str | None]:
    if pricing.input_per_1m_usd < 0 or pricing.output_per_1m_usd < 0:
        return None, None

    estimated_cost = (
        (input_tokens / 1_000_000) * pricing.input_per_1m_usd
        + (output_tokens / 1_000_000) * pricing.output_per_1m_usd
    )
    return round(estimated_cost, 6), "admin_override"


def _rate_card_from_legacy_pricing(pricing: PricingOverride) -> RateCard | None:
    if pricing.input_per_1m_usd < 0 or pricing.output_per_1m_usd < 0:
        return None
    return RateCard(
        standard=TierRates(
            input_per_1m=Decimal(str(pricing.input_per_1m_usd)),
            output_per_1m=Decimal(str(pricing.output_per_1m_usd)),
        ),
        source="admin_override",
    )


def calculate_estimated_cost_usd(
    pricing: PricingOverride | None,
    input_tokens: int,
    output_tokens: int,
) -> tuple[float | None, str | None]:
    if pricing is None:
        return None, None

    card: RateCard | None = None
    if pricing.rate_card_json:
        try:
            card = RateCard.model_validate_json(pricing.rate_card_json)
        except ValidationError:
            card = None

    if card is None:
        card = _rate_card_from_legacy_pricing(pricing)
    if card is None:
        return None, None

    usage = UsageSnapshot.flat(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        token_source=None,
    )
    breakdown = price(usage, card, RequestContext())
    return float(breakdown.total_usd), card.source
