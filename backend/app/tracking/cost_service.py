from __future__ import annotations

from app.database import PricingOverride


def calculate_estimated_cost_usd(
    pricing: PricingOverride | None,
    input_tokens: int,
    output_tokens: int,
) -> tuple[float | None, str | None]:
    if pricing is None:
        return None, None

    estimated_cost = (
        (input_tokens / 1_000_000) * pricing.input_per_1m_usd
        + (output_tokens / 1_000_000) * pricing.output_per_1m_usd
    )
    return round(estimated_cost, 6), "admin_override"
