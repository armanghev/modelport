from __future__ import annotations

from app.database import PricingOverride
from app.tracking.cost_service import calculate_estimated_cost_usd


def test_calculate_estimated_cost_usd_rejects_negative_rates() -> None:
    pricing = PricingOverride(
        provider_id="openrouter",
        model="openrouter/auto",
        input_per_1m_usd=-1_000_000.0,
        output_per_1m_usd=-1_000_000.0,
        currency="USD",
        enabled=True,
    )

    estimated_cost_usd, pricing_source = calculate_estimated_cost_usd(pricing, 41, 0)

    assert estimated_cost_usd is None
    assert pricing_source is None


def test_calculate_estimated_cost_usd_allows_zero_rates() -> None:
    pricing = PricingOverride(
        provider_id="ollama",
        model="llama3",
        input_per_1m_usd=0.0,
        output_per_1m_usd=0.0,
        currency="USD",
        enabled=True,
    )

    estimated_cost_usd, pricing_source = calculate_estimated_cost_usd(pricing, 1000, 500)

    assert estimated_cost_usd == 0.0
    assert pricing_source == "admin_override"
