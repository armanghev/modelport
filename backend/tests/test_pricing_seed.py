from __future__ import annotations

from pathlib import Path

from app.pricing_seed import load_pricing_catalog, seed_pricing_overrides
from sqlalchemy import select

from app.database import PricingOverride


def test_seed_pricing_overrides_is_idempotent(client) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    catalog_path = repo_root / "pricing_catalog.yaml"
    config = client.app.state.config
    session_factory = client.app.state.session_factory

    first = seed_pricing_overrides(
        session_factory,
        config,
        catalog_path=catalog_path,
        sync_openrouter=False,
        discover_ollama=False,
    )
    second = seed_pricing_overrides(
        session_factory,
        config,
        catalog_path=catalog_path,
        sync_openrouter=False,
        discover_ollama=False,
    )

    assert first["catalog"] == second["catalog"]

    with session_factory() as session:
        gemini_pro = session.scalar(
            select(PricingOverride).where(
                PricingOverride.provider_id == "gemini",
                PricingOverride.model == "models/gemini-2.5-pro",
            )
        )
    assert gemini_pro is not None
    assert gemini_pro.input_per_1m_usd == 1.25
    assert gemini_pro.output_per_1m_usd == 10.0


def test_load_pricing_catalog_parses_provider_models() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    catalog = load_pricing_catalog(repo_root / "pricing_catalog.yaml")
    assert "openai" in catalog
    assert catalog["openai"]["gpt-4.1"]["input_per_1m_usd"] == 2.0
