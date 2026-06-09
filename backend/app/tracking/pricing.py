from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import PricingOverride, get_provider_by_slug


def find_pricing_override(
    session: Session,
    provider_id: str,
    model: str,
) -> PricingOverride | None:
    record = session.scalars(
        select(PricingOverride).where(
            PricingOverride.provider_id == provider_id,
            PricingOverride.model == model,
            PricingOverride.enabled.is_(True),
        )
    ).first()
    if record is not None:
        return record

    provider = get_provider_by_slug(session, provider_id)
    if provider is None:
        return None

    return session.scalars(
        select(PricingOverride).where(
            PricingOverride.provider_id == provider.id,
            PricingOverride.model == model,
            PricingOverride.enabled.is_(True),
        )
    ).first()
