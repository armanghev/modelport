from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.database import PricingOverride, get_provider_by_slug
from app.pricing.rate_card import RateCard
from app.pricing_seed import load_pricing_catalog, seed_pricing_overrides

FIXTURE = Path(__file__).parent / "fixtures" / "litellm_subset.json"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _seed(client) -> dict[str, int]:
    return seed_pricing_overrides(
        client.app.state.session_factory,
        catalog_path=REPO_ROOT / "pricing_catalog.yaml",
        sync_openrouter=False,
        discover_ollama=False,
        litellm_payload=json.loads(FIXTURE.read_text(encoding="utf-8")),
    )


def _find(client, provider_slug: str, model: str) -> PricingOverride | None:
    with client.app.state.session_factory() as session:
        provider = get_provider_by_slug(session, provider_slug)
        return session.scalar(
            select(PricingOverride).where(
                PricingOverride.provider_id == provider.id,
                PricingOverride.model == model,
            )
        )


def test_seeding_is_idempotent(client) -> None:
    first = _seed(client)
    second = _seed(client)

    assert first["litellm"] == second["litellm"]


def test_seeded_card_carries_cache_rates(client) -> None:
    _seed(client)

    record = _find(client, "anthropic", "claude-sonnet-4-6")

    assert record is not None
    assert record.source == "litellm"
    assert record.input_per_1m_usd == 3.0
    card = RateCard.model_validate_json(record.rate_card_json)
    assert card.standard.cache_read_per_1m == Decimal("0.3")


def test_manual_cards_are_not_overwritten_by_reimport(client) -> None:
    _seed(client)

    session_factory = client.app.state.session_factory
    with session_factory() as session:
        provider = get_provider_by_slug(session, "anthropic")
        record = session.scalar(
            select(PricingOverride).where(
                PricingOverride.provider_id == provider.id,
                PricingOverride.model == "claude-sonnet-4-6",
            )
        )
        record.source = "manual"
        record.input_per_1m_usd = 99.0
        session.commit()

    _seed(client)

    assert _find(client, "anthropic", "claude-sonnet-4-6").input_per_1m_usd == 99.0


def test_local_yaml_still_seeds_ollama_defaults(client) -> None:
    catalog = load_pricing_catalog(REPO_ROOT / "pricing_catalog.yaml")

    assert catalog["ollama"]["*"]["input_per_1m_usd"] == 0.0

    _seed(client)
    record = _find(client, "ollama", "*")

    assert record is not None
    assert record.rate_card_json is not None
    assert RateCard.model_validate_json(record.rate_card_json).source == "local"


def test_fetch_openrouter_pricing_skips_negative_sentinel_prices(monkeypatch) -> None:
    from app.pricing_seed import fetch_openrouter_pricing

    def fake_fetch_openrouter_models_api_payload() -> dict:
        return {
            "data": [
                {
                    "id": "openrouter/auto",
                    "pricing": {"prompt": "-1", "completion": "-1"},
                },
                {
                    "id": "openai/gpt-4.1",
                    "pricing": {"prompt": "0.000002", "completion": "0.000008"},
                },
            ]
        }

    monkeypatch.setattr(
        "app.pricing_seed.fetch_openrouter_models_api_payload",
        fake_fetch_openrouter_models_api_payload,
    )

    rows = fetch_openrouter_pricing()

    assert rows == [("openai/gpt-4.1", 2.0, 8.0)]
