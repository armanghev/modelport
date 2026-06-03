from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import PricingOverride


def find_pricing_override(
    session: Session,
    provider_id: str,
    model: str,
) -> PricingOverride | None:
    return session.scalars(
        select(PricingOverride).where(
            PricingOverride.provider_id == provider_id,
            PricingOverride.model == model,
            PricingOverride.enabled.is_(True),
        )
    ).first()
