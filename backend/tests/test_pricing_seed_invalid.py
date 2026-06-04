from __future__ import annotations

from app.database import PricingOverride
from app.pricing_seed import disable_invalid_pricing_overrides
from sqlalchemy import select


def test_disable_invalid_pricing_overrides_disables_negative_rows(client) -> None:
    session_factory = client.app.state.session_factory
    with session_factory() as session:
        session.add(
            PricingOverride(
                provider_id="openrouter",
                model="openrouter/auto",
                input_per_1m_usd=-1_000_000.0,
                output_per_1m_usd=-1_000_000.0,
                currency="USD",
                enabled=True,
            )
        )
        session.commit()
        disabled = disable_invalid_pricing_overrides(session)
        session.commit()
        record = session.scalar(
            select(PricingOverride).where(
                PricingOverride.provider_id == "openrouter",
                PricingOverride.model == "openrouter/auto",
            )
        )

    assert disabled == 1
    assert record is not None
    assert record.enabled is False
