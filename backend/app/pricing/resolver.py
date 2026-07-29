from __future__ import annotations

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import PricingOverride, get_provider_by_slug
from app.pricing.rate_card import RateCard, source_rank

MODEL_ALIASES: dict[tuple[str, str], str] = {
    ("gemini", "gemini3.5-flash"): "gemini-3.5-flash",
    ("ollama", "gemma4"): "gemma4:latest",
}


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


def _best_override(
    session: Session,
    *,
    provider_uuid: str,
    model: str,
) -> PricingOverride | None:
    rows = session.scalars(
        select(PricingOverride).where(
            PricingOverride.provider_id == provider_uuid,
            PricingOverride.model == model,
            PricingOverride.enabled.is_(True),
        )
    ).all()
    if not rows:
        return None
    return max(rows, key=lambda row: source_rank(row.source))


def _to_rate_card(record: PricingOverride) -> RateCard | None:
    if not record.rate_card_json:
        return None
    try:
        return RateCard.model_validate_json(record.rate_card_json)
    except ValidationError:
        return None


def resolve_rate_card(
    session: Session,
    *,
    provider_id: str | None,
    resolved_model: str | None,
    requested_model: str | None,
) -> RateCard | None:
    if not provider_id:
        return None

    provider = get_provider_by_slug(session, provider_id)
    if provider is None:
        return None

    for model in model_lookup_candidates(provider_id, resolved_model, requested_model):
        record = _best_override(session, provider_uuid=provider.id, model=model)
        if record is not None:
            card = _to_rate_card(record)
            if card is not None:
                return card

    if provider_id == "ollama":
        record = _best_override(session, provider_uuid=provider.id, model="*")
        if record is not None:
            return _to_rate_card(record)

    return None
