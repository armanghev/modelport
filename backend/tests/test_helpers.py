from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from app.database import PricingOverride
from app.pricing.rate_card import RateCard


def provider_uuid(client: TestClient, slug: str) -> str:
    providers = client.get("/admin/providers").json()
    return next(provider["id"] for provider in providers if provider["slug"] == slug)


def cards_by_slug(cards: list[dict]) -> dict[str, dict]:
    return {card["slug"]: card for card in cards}


def seed_pricing(
    client: TestClient,
    *,
    provider_slug: str,
    model: str,
    input_per_1m_usd: float,
    output_per_1m_usd: float,
) -> None:
    with client.app.state.session_factory() as session:
        session.add(
            PricingOverride(
                provider_id=provider_uuid(client, provider_slug),
                model=model,
                input_per_1m_usd=input_per_1m_usd,
                output_per_1m_usd=output_per_1m_usd,
                rate_card_json=RateCard(
                    standard={
                        "input_per_1m": Decimal(str(input_per_1m_usd)),
                        "output_per_1m": Decimal(str(output_per_1m_usd)),
                    },
                    source="fixture",
                ).model_dump_json(),
                source="fixture",
                enabled=True,
            )
        )
        session.commit()
