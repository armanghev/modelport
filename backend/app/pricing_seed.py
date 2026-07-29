from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path

import httpx
import yaml
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import load_config
from app.database import PricingOverride, Provider, build_session_factory, get_provider_by_slug
from app.model_metadata_service import (
    fetch_openrouter_models_api_payload,
    parse_openrouter_model,
    sync_openrouter_metadata,
)
from app.pricing.catalog_import import build_rate_cards, fetch_litellm_catalog
from app.pricing.rate_card import RateCard, TierRates, source_rank
DEFAULT_CATALOG_PATH = Path("../pricing_catalog.yaml")


def load_pricing_catalog(catalog_path: Path) -> dict[str, dict[str, dict[str, float]]]:
    raw = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
    catalog = raw.get("catalog")
    if not isinstance(catalog, dict):
        raise ValueError(f"{catalog_path} must contain a top-level 'catalog' mapping.")
    return catalog


def upsert_rate_card(
    session: Session,
    *,
    provider_id: str,
    model: str,
    card: RateCard,
) -> bool:
    """Write a rate card, refusing to downgrade a higher-precedence source."""
    record = session.scalar(
        select(PricingOverride).where(
            PricingOverride.provider_id == provider_id,
            PricingOverride.model == model,
        )
    )

    if record is not None and source_rank(record.source) > source_rank(card.source):
        return False

    if record is None:
        record = PricingOverride(provider_id=provider_id, model=model, enabled=True)
        session.add(record)

    record.rate_card_json = card.model_dump_json()
    record.source = card.source
    # Kept in the same transaction as the card so the two never diverge.
    record.input_per_1m_usd = float(card.standard.input_per_1m)
    record.output_per_1m_usd = float(card.standard.output_per_1m)
    record.enabled = True
    session.flush()
    return True


def upsert_pricing_override(
    session: Session,
    *,
    provider_id: str,
    model: str,
    input_per_1m_usd: float,
    output_per_1m_usd: float,
    source: str = "legacy_seed",
) -> bool:
    """Upsert a flat two-rate card for sources that report no cache dimensions."""
    card = RateCard(
        standard=TierRates(
            input_per_1m=Decimal(str(input_per_1m_usd)),
            output_per_1m=Decimal(str(output_per_1m_usd)),
        ),
        source=source,
    )
    return upsert_rate_card(session, provider_id=provider_id, model=model, card=card)


def resolve_provider_uuid(session: Session, slug: str) -> str | None:
    provider = get_provider_by_slug(session, slug)
    return provider.id if provider is not None else None


def list_configured_provider_slugs(session: Session) -> set[str]:
    slugs = session.scalars(select(Provider.slug)).all()
    return {slug for slug in slugs if slug}


def seed_catalog_pricing(
    session: Session,
    catalog: dict[str, dict[str, dict[str, float]]],
    *,
    configured_provider_slugs: set[str],
) -> int:
    upserted = 0
    for provider_slug, models in catalog.items():
        if provider_slug not in configured_provider_slugs:
            continue
        provider_uuid = resolve_provider_uuid(session, provider_slug)
        if provider_uuid is None:
            continue
        for model, rates in models.items():
            upsert_pricing_override(
                session,
                provider_id=provider_uuid,
                model=model,
                input_per_1m_usd=float(rates["input_per_1m_usd"]),
                output_per_1m_usd=float(rates["output_per_1m_usd"]),
                source="local",
            )
            upserted += 1
    return upserted


def fetch_openrouter_pricing() -> list[tuple[str, float, float]]:
    payload = fetch_openrouter_models_api_payload()

    rows: list[tuple[str, float, float]] = []
    for item in payload.get("data", []):
        if not isinstance(item, dict):
            continue
        record = parse_openrouter_model(item)
        if record is None:
            continue
        input_per_1m = record.get("input_per_1m_usd")
        output_per_1m = record.get("output_per_1m_usd")
        if input_per_1m is None or output_per_1m is None:
            continue
        rows.append((record["id"], input_per_1m, output_per_1m))
    return rows


def disable_invalid_pricing_overrides(session: Session) -> int:
    """Disable overrides seeded before unknown-price handling (e.g. OpenRouter -1)."""
    rows = session.scalars(
        select(PricingOverride).where(
            PricingOverride.enabled.is_(True),
            or_(
                PricingOverride.input_per_1m_usd < 0,
                PricingOverride.output_per_1m_usd < 0,
            ),
        )
    ).all()
    for row in rows:
        row.enabled = False
    return len(rows)


def seed_openrouter_pricing(session: Session, *, configured_provider_slugs: set[str]) -> int:
    if "openrouter" not in configured_provider_slugs:
        return 0

    provider_uuid = resolve_provider_uuid(session, "openrouter")
    if provider_uuid is None:
        return 0

    upserted = 0
    for model_id, input_per_1m, output_per_1m in fetch_openrouter_pricing():
        upsert_pricing_override(
            session,
            provider_id=provider_uuid,
            model=model_id,
            input_per_1m_usd=input_per_1m,
            output_per_1m_usd=output_per_1m,
            source="openrouter",
        )
        upserted += 1
    return upserted


def seed_ollama_discovered_models(
    session: Session,
    catalog: dict[str, dict[str, dict[str, float]]],
    *,
    configured_provider_slugs: set[str],
) -> int:
    if "ollama" not in configured_provider_slugs:
        return 0

    default_rates = catalog.get("ollama", {}).get("*")
    if not isinstance(default_rates, dict):
        return 0

    provider = get_provider_by_slug(session, "ollama")
    if provider is None:
        return 0

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{provider.base_url.rstrip('/')}/models")
            response.raise_for_status()
            payload = response.json()
        raw_models = payload.get("data")
        if not isinstance(raw_models, list):
            raw_models = payload.get("models")
        if not isinstance(raw_models, list):
            return 0
        models = [
            {"id": item["id"] if isinstance(item, dict) else item}
            for item in raw_models
            if (isinstance(item, dict) and item.get("id")) or isinstance(item, str)
        ]
    except Exception:
        return 0

    upserted = 0
    for model in models:
        model_id = model.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        upsert_pricing_override(
            session,
            provider_id=provider.id,
            model=model_id,
            input_per_1m_usd=float(default_rates["input_per_1m_usd"]),
            output_per_1m_usd=float(default_rates["output_per_1m_usd"]),
            source="local",
        )
        upserted += 1
    return upserted


def seed_litellm_rate_cards(
    session: Session,
    payload: dict | None,
    *,
    configured_provider_slugs: set[str],
) -> int:
    if payload is None:
        try:
            payload = fetch_litellm_catalog()
        except Exception:
            # A failed fetch must never wipe or downgrade existing rates.
            return 0

    provider_uuids = {
        slug: resolve_provider_uuid(session, slug) for slug in configured_provider_slugs
    }

    upserted = 0
    for (provider_slug, model), card in build_rate_cards(payload).items():
        provider_uuid = provider_uuids.get(provider_slug)
        if provider_uuid is None:
            continue
        if upsert_rate_card(session, provider_id=provider_uuid, model=model, card=card):
            upserted += 1
    return upserted


def seed_pricing_overrides(
    session_factory: sessionmaker[Session],
    *,
    catalog_path: Path = DEFAULT_CATALOG_PATH,
    sync_openrouter: bool = True,
    discover_ollama: bool = True,
    sync_metadata: bool = True,
    sync_litellm: bool = True,
    litellm_payload: dict | None = None,
) -> dict[str, int]:
    catalog = load_pricing_catalog(catalog_path)
    with session_factory() as session:
        configured_provider_slugs = list_configured_provider_slugs(session)

    with session_factory() as session:
        catalog_count = seed_catalog_pricing(
            session,
            catalog,
            configured_provider_slugs=configured_provider_slugs,
        )
        litellm_count = (
            seed_litellm_rate_cards(
                session,
                litellm_payload,
                configured_provider_slugs=configured_provider_slugs,
            )
            if sync_litellm or litellm_payload is not None
            else 0
        )
        openrouter_count = (
            seed_openrouter_pricing(session, configured_provider_slugs=configured_provider_slugs)
            if sync_openrouter
            else 0
        )
        ollama_count = (
            seed_ollama_discovered_models(
                session,
                catalog,
                configured_provider_slugs=configured_provider_slugs,
            )
            if discover_ollama
            else 0
        )
        metadata_count = 0
        if sync_metadata and sync_openrouter:
            try:
                metadata_count = sync_openrouter_metadata(session)
            except Exception:
                metadata_count = 0
        disabled_invalid = disable_invalid_pricing_overrides(session)
        session.commit()

    return {
        "catalog": catalog_count,
        "litellm": litellm_count,
        "openrouter": openrouter_count,
        "ollama_discovered": ollama_count,
        "metadata": metadata_count,
        "disabled_invalid": disabled_invalid,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed ModelPort pricing overrides.")
    parser.add_argument("--config", default="../config.yaml", help="Path to config.yaml")
    parser.add_argument(
        "--catalog",
        default=str(DEFAULT_CATALOG_PATH),
        help="Path to pricing_catalog.yaml",
    )
    parser.add_argument("--skip-openrouter", action="store_true")
    parser.add_argument("--skip-ollama-discovery", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config)
    session_factory = build_session_factory(config.database.url)
    counts = seed_pricing_overrides(
        session_factory,
        catalog_path=Path(args.catalog),
        sync_openrouter=not args.skip_openrouter,
        discover_ollama=not args.skip_ollama_discovery,
    )
    print(
        "Seeded pricing overrides:",
        f"catalog={counts['catalog']}",
        f"openrouter={counts['openrouter']}",
        f"ollama_discovered={counts['ollama_discovered']}",
        f"disabled_invalid={counts['disabled_invalid']}",
    )


if __name__ == "__main__":
    main()
