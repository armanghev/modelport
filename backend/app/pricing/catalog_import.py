from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx

from app.pricing.rate_card import RateCard, TierRates

LITELLM_CATALOG_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
)

MILLION = Decimal(1_000_000)

# LiteLLM's provider names mapped onto ModelPort provider slugs.
PROVIDER_MAP: dict[str, str] = {
    "anthropic": "anthropic",
    "openai": "openai",
    "vertex_ai-language-models": "gemini",
    "gemini": "gemini",
}

# LiteLLM suffixes for service tiers; note batch is "batches".
SERVICE_TIER_SUFFIX: dict[str, str] = {
    "batch": "batches",
    "flex": "flex",
    "priority": "priority",
}

_ABOVE_THRESHOLD_RE = re.compile(r"^input_cost_per_token_above_(\d+)k_tokens$")


def _per_1m(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value)) * MILLION
    except (ArithmeticError, ValueError):
        return None


def _threshold_tokens(entry: dict[str, Any]) -> int | None:
    for key in entry:
        match = _ABOVE_THRESHOLD_RE.match(key)
        if match:
            return int(match.group(1)) * 1000
    return None


def _tier_rates(entry: dict[str, Any], suffix: str) -> TierRates | None:
    input_rate = _per_1m(entry.get(f"input_cost_per_token{suffix}"))
    output_rate = _per_1m(entry.get(f"output_cost_per_token{suffix}"))
    if input_rate is None or output_rate is None:
        return None
    return TierRates(
        input_per_1m=input_rate,
        output_per_1m=output_rate,
        cache_read_per_1m=_per_1m(entry.get(f"cache_read_input_token_cost{suffix}")),
        cache_write_5m_per_1m=_per_1m(entry.get(f"cache_creation_input_token_cost{suffix}")),
        cache_write_1h_per_1m=_per_1m(
            entry.get(f"cache_creation_input_token_cost_above_1hr{suffix}")
        ),
    )


def build_rate_card(entry: dict[str, Any], *, fetched_at: datetime) -> RateCard | None:
    standard = _tier_rates(entry, "")
    if standard is None:
        return None

    threshold = _threshold_tokens(entry)
    above = None
    if threshold is not None:
        above = _tier_rates(entry, f"_above_{threshold // 1000}k_tokens")
        if above is None:
            threshold = None

    service_tiers: dict[str, TierRates] = {}
    for tier, suffix in SERVICE_TIER_SUFFIX.items():
        rates = _tier_rates(entry, f"_{suffix}")
        if rates is not None:
            service_tiers[tier] = rates

    return RateCard(
        standard=standard,
        above_threshold=above,
        context_threshold_tokens=threshold,
        service_tiers=service_tiers,
        source="litellm",
        source_fetched_at=fetched_at,
    )


def build_rate_cards(payload: dict[str, Any]) -> dict[tuple[str, str], RateCard]:
    """Map LiteLLM's catalog onto ModelPort (provider_slug, model) keys."""
    fetched_at = datetime.now(timezone.utc)
    cards: dict[tuple[str, str], RateCard] = {}

    for model_id, entry in payload.items():
        if model_id == "sample_spec" or not isinstance(entry, dict):
            continue
        if entry.get("mode") != "chat":
            continue

        provider_slug = PROVIDER_MAP.get(str(entry.get("litellm_provider") or ""))
        if provider_slug is None:
            continue

        card = build_rate_card(entry, fetched_at=fetched_at)
        if card is None:
            continue

        cards[(provider_slug, model_id)] = card
        if provider_slug == "gemini" and not model_id.startswith("models/"):
            cards[(provider_slug, f"models/{model_id}")] = card

    return cards


def fetch_litellm_catalog(*, timeout: float = 30.0) -> dict[str, Any]:
    with httpx.Client(timeout=timeout) as client:
        response = client.get(LITELLM_CATALOG_URL)
        response.raise_for_status()
        return response.json()
