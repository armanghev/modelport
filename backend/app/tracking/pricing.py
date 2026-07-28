from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import PricingOverride, get_provider_by_slug

MODEL_ALIASES: dict[tuple[str, str], str] = {
    ("gemini", "gemini3.5-flash"): "gemini-2.5-flash",
    ("ollama", "gemma4"): "gemma4:latest",
}


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


def model_lookup_candidates(
    provider_id: str | None,
    resolved_model: str | None,
    requested_model: str | None,
) -> list[str]:
    candidates: list[str] = []
    for value in (resolved_model, requested_model):
        if not value or not value.strip():
            continue
        normalized = value.strip()
        if normalized not in candidates:
            candidates.append(normalized)

        if provider_id and (provider_id, normalized) in MODEL_ALIASES:
            alias = MODEL_ALIASES[(provider_id, normalized)]
            if alias not in candidates:
                candidates.append(alias)

        if normalized.startswith("models/"):
            stripped = normalized.removeprefix("models/")
            if stripped not in candidates:
                candidates.append(stripped)
        else:
            prefixed = f"models/{normalized}"
            if prefixed not in candidates:
                candidates.append(prefixed)

    return candidates


def resolve_pricing_override(
    session: Session,
    *,
    provider_id: str | None,
    resolved_model: str | None,
    requested_model: str | None,
) -> PricingOverride | None:
    if not provider_id:
        return None

    provider = get_provider_by_slug(session, provider_id)
    if provider is None:
        return None
    provider_uuid = provider.id

    for model in model_lookup_candidates(provider_id, resolved_model, requested_model):
        pricing = find_pricing_override(session, provider_id=provider_uuid, model=model)
        if pricing is not None:
            return pricing

    if provider_id == "ollama":
        return find_pricing_override(session, provider_id=provider_uuid, model="*")

    return None
