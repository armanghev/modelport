from __future__ import annotations

import argparse
from pathlib import Path

import httpx
import yaml
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import AppConfig, load_config
from app.database import PricingOverride, Provider, build_session_factory
from app.model_metadata_service import (
    fetch_openrouter_models_api_payload,
    parse_openrouter_model,
    sync_openrouter_metadata,
)
DEFAULT_CATALOG_PATH = Path("../pricing_catalog.yaml")


def load_pricing_catalog(catalog_path: Path) -> dict[str, dict[str, dict[str, float]]]:
    raw = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
    catalog = raw.get("catalog")
    if not isinstance(catalog, dict):
        raise ValueError(f"{catalog_path} must contain a top-level 'catalog' mapping.")
    return catalog


def upsert_pricing_override(
    session: Session,
    *,
    provider_id: str,
    model: str,
    input_per_1m_usd: float,
    output_per_1m_usd: float,
) -> PricingOverride:
    record = session.scalar(
        select(PricingOverride).where(
            PricingOverride.provider_id == provider_id,
            PricingOverride.model == model,
        )
    )
    if record is None:
        record = PricingOverride(
            provider_id=provider_id,
            model=model,
            input_per_1m_usd=input_per_1m_usd,
            output_per_1m_usd=output_per_1m_usd,
            currency="USD",
            enabled=True,
        )
        session.add(record)
    else:
        record.input_per_1m_usd = input_per_1m_usd
        record.output_per_1m_usd = output_per_1m_usd
        record.enabled = True
    session.flush()
    return record


def seed_catalog_pricing(
    session: Session,
    catalog: dict[str, dict[str, dict[str, float]]],
    *,
    configured_provider_ids: set[str],
) -> int:
    upserted = 0
    for provider_id, models in catalog.items():
        if provider_id not in configured_provider_ids:
            continue
        for model, rates in models.items():
            upsert_pricing_override(
                session,
                provider_id=provider_id,
                model=model,
                input_per_1m_usd=float(rates["input_per_1m_usd"]),
                output_per_1m_usd=float(rates["output_per_1m_usd"]),
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


def seed_openrouter_pricing(session: Session, *, configured_provider_ids: set[str]) -> int:
    if "openrouter" not in configured_provider_ids:
        return 0

    upserted = 0
    for model_id, input_per_1m, output_per_1m in fetch_openrouter_pricing():
        upsert_pricing_override(
            session,
            provider_id="openrouter",
            model=model_id,
            input_per_1m_usd=input_per_1m,
            output_per_1m_usd=output_per_1m,
        )
        upserted += 1
    return upserted


def seed_ollama_discovered_models(
    session: Session,
    catalog: dict[str, dict[str, dict[str, float]]],
    *,
    configured_provider_ids: set[str],
) -> int:
    if "ollama" not in configured_provider_ids:
        return 0

    default_rates = catalog.get("ollama", {}).get("*")
    if not isinstance(default_rates, dict):
        return 0

    provider = session.get(Provider, "ollama")
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
            provider_id="ollama",
            model=model_id,
            input_per_1m_usd=float(default_rates["input_per_1m_usd"]),
            output_per_1m_usd=float(default_rates["output_per_1m_usd"]),
        )
        upserted += 1
    return upserted


def seed_pricing_overrides(
    session_factory: sessionmaker[Session],
    config: AppConfig,
    *,
    catalog_path: Path = DEFAULT_CATALOG_PATH,
    sync_openrouter: bool = True,
    discover_ollama: bool = True,
    sync_metadata: bool = True,
) -> dict[str, int]:
    catalog = load_pricing_catalog(catalog_path)
    configured_provider_ids = set(config.providers.keys())

    with session_factory() as session:
        catalog_count = seed_catalog_pricing(
            session,
            catalog,
            configured_provider_ids=configured_provider_ids,
        )
        openrouter_count = (
            seed_openrouter_pricing(session, configured_provider_ids=configured_provider_ids)
            if sync_openrouter
            else 0
        )
        ollama_count = (
            seed_ollama_discovered_models(
                session,
                catalog,
                configured_provider_ids=configured_provider_ids,
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
        config,
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
