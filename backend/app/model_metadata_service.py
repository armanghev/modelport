from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics_service import list_providers, list_requests, model_name, request_status, round_decimal, round_percent
from app.database import ModelMetadata, PricingOverride, Provider

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_MODELS_QUERY_PARAMS = {"output_modalities": "all"}
GEMINI_NATIVE_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
MetadataSource = str  # "openrouter" | "local" | "pricing" | "unknown"
METADATA_MAX_AGE = timedelta(hours=24)

# OpenRouter model ids use vendor prefixes; map ModelPort provider ids to those vendors.
OPENROUTER_VENDOR_BY_PROVIDER: dict[str, str | None] = {
    "openai": "openai",
    "anthropic": "anthropic",
    "gemini": "google",
    "google": "google",
    "meta": "meta-llama",
    "xai": "x-ai",
    "mistral": "mistralai",
    "cohere": "cohere",
    "deepseek": "deepseek",
    "openrouter": None,
    "ollama": "ollama",
    "qwen": "qwen",
}


def is_gemini_provider(provider: Provider) -> bool:
    return "generativelanguage.googleapis.com" in provider.base_url


def is_openrouter_provider(provider: Provider) -> bool:
    return provider.id == "openrouter" or "openrouter.ai" in provider.base_url


def openrouter_models_request_kwargs() -> dict[str, Any]:
    return {"params": dict(OPENROUTER_MODELS_QUERY_PARAMS)}


def fetch_openrouter_models_api_payload() -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            OPENROUTER_MODELS_URL,
            **openrouter_models_request_kwargs(),
        )
        response.raise_for_status()
        return response.json()


@dataclass(slots=True)
class ModelUsageStats:
    request_count: int = 0
    token_total: int = 0
    cost_usd: float = 0.0
    avg_latency_ms: int = 0
    error_rate: float = 0.0


def _parse_modalities(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str) and value:
        return [value]
    return []


def _parse_supported_parameters(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return []


def _architecture_dict(item: dict) -> dict[str, Any]:
    architecture = item.get("architecture")
    if not isinstance(architecture, dict):
        return {}
    return {
        key: architecture[key]
        for key in ("modality", "input_modalities", "output_modalities", "tokenizer", "instruct_type")
        if key in architecture
    }


def _pricing_per_million_value(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        per_token = float(raw)
    except (TypeError, ValueError):
        return None
    # OpenRouter uses -1 when pricing is unknown.
    if per_token < 0:
        return None
    return per_token * 1_000_000


def _pricing_per_million(item: dict) -> tuple[float | None, float | None]:
    pricing = item.get("pricing")
    if not isinstance(pricing, dict):
        return None, None
    return (
        _pricing_per_million_value(pricing.get("prompt")),
        _pricing_per_million_value(pricing.get("completion")),
    )


def sanitize_price_per_million(value: float | None) -> float | None:
    if value is None or value < 0:
        return None
    return value


def parse_openrouter_model(item: dict) -> dict[str, Any] | None:
    model_id = item.get("id")
    if not isinstance(model_id, str) or not model_id.strip():
        return None

    architecture = _architecture_dict(item)
    input_modalities = _parse_modalities(
        architecture.get("input_modalities") or item.get("input_modalities"),
    )
    output_modalities = _parse_modalities(
        architecture.get("output_modalities") or item.get("output_modalities"),
    )
    input_per_1m, output_per_1m = _pricing_per_million(item)

    context_length = item.get("context_length")
    if not isinstance(context_length, int):
        context_length = None

    return {
        "id": model_id,
        "canonical_slug": item.get("canonical_slug")
        if isinstance(item.get("canonical_slug"), str)
        else None,
        "name": item.get("name") if isinstance(item.get("name"), str) else None,
        "description": item.get("description") if isinstance(item.get("description"), str) else None,
        "context_length": context_length,
        "architecture": architecture,
        "input_modalities": input_modalities,
        "output_modalities": output_modalities,
        "supported_parameters": _parse_supported_parameters(item.get("supported_parameters")),
        "input_per_1m_usd": input_per_1m,
        "output_per_1m_usd": output_per_1m,
        "top_provider": item.get("top_provider") if isinstance(item.get("top_provider"), dict) else None,
        "expiration_date": item.get("expiration_date")
        if isinstance(item.get("expiration_date"), str)
        else None,
        "source": "openrouter",
    }


def bare_model_id(model_id: str) -> str:
    value = model_id.strip()
    if value.startswith("models/"):
        return value.removeprefix("models/")
    if "/" in value:
        return value.split("/", 1)[-1]
    return value


def openrouter_vendor_for_provider(provider_id: str) -> str | None:
    if provider_id in OPENROUTER_VENDOR_BY_PROVIDER:
        return OPENROUTER_VENDOR_BY_PROVIDER[provider_id]
    return provider_id


def parse_openrouter_upstream_models(payload: dict) -> list[dict[str, Any]]:
    raw_models = payload.get("data")
    if not isinstance(raw_models, list):
        return []

    models: list[dict[str, Any]] = []
    for item in raw_models:
        if not isinstance(item, dict):
            continue
        record = parse_openrouter_model(item)
        if record is None:
            continue
        owned_by = record["id"].split("/")[0] if "/" in record["id"] else None
        models.append(
            {
                "id": record["id"],
                "display_name": record.get("name"),
                "owned_by": owned_by,
                "description": record.get("description"),
                "context_length": record.get("context_length"),
                "openrouter_metadata": record,
            }
        )
    return models


def fetch_gemini_native_models_index(api_key: str) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    page_token: str | None = None

    with httpx.Client(timeout=30.0) as client:
        while True:
            params: dict[str, str | int] = {"key": api_key}
            if page_token:
                params["pageToken"] = page_token
            response = client.get(GEMINI_NATIVE_MODELS_URL, params=params)
            response.raise_for_status()
            payload = response.json()

            for item in payload.get("models", []):
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                if not isinstance(name, str) or not name.strip():
                    continue
                index[name] = item
                if name.startswith("models/"):
                    index[name.removeprefix("models/")] = item

            page_token = payload.get("nextPageToken")
            if not isinstance(page_token, str) or not page_token.strip():
                break

    return index


def apply_gemini_native_model_fields(
    models: list[dict],
    native_index: dict[str, dict[str, Any]],
) -> list[dict]:
    enriched: list[dict] = []
    for model in models:
        merged = dict(model)
        native = native_index.get(model["id"])
        if native is None:
            native = native_index.get(model["id"].removeprefix("models/"))
        if native is None:
            enriched.append(merged)
            continue

        description = native.get("description")
        if isinstance(description, str) and description.strip():
            merged["description"] = description.strip()

        display_name = native.get("displayName")
        if isinstance(display_name, str) and display_name.strip() and not merged.get("display_name"):
            merged["display_name"] = display_name.strip()

        input_limit = native.get("inputTokenLimit")
        if isinstance(input_limit, int) and input_limit > 0:
            merged["context_length"] = input_limit

        enriched.append(merged)
    return enriched


def fetch_openrouter_models_payload() -> list[dict[str, Any]]:
    payload = fetch_openrouter_models_api_payload()

    parsed: list[dict[str, Any]] = []
    for item in payload.get("data", []):
        if not isinstance(item, dict):
            continue
        record = parse_openrouter_model(item)
        if record is not None:
            parsed.append(record)
    return parsed


def upsert_model_metadata(session: Session, record: dict[str, Any]) -> ModelMetadata:
    existing = session.get(ModelMetadata, record["id"])
    architecture_json = json.dumps(record.get("architecture") or {})
    input_modalities_json = json.dumps(record.get("input_modalities") or [])
    output_modalities_json = json.dumps(record.get("output_modalities") or [])
    supported_parameters_json = json.dumps(record.get("supported_parameters") or [])
    top_provider_json = json.dumps(record.get("top_provider")) if record.get("top_provider") else None

    if existing is None:
        existing = ModelMetadata(
            id=record["id"],
            canonical_slug=record.get("canonical_slug"),
            name=record.get("name"),
            description=record.get("description"),
            context_length=record.get("context_length"),
            architecture_json=architecture_json,
            input_modalities_json=input_modalities_json,
            output_modalities_json=output_modalities_json,
            supported_parameters_json=supported_parameters_json,
            input_per_1m_usd=sanitize_price_per_million(record.get("input_per_1m_usd")),
            output_per_1m_usd=sanitize_price_per_million(record.get("output_per_1m_usd")),
            top_provider_json=top_provider_json,
            expiration_date=record.get("expiration_date"),
            source=record.get("source") or "openrouter",
            fetched_at=datetime.now(UTC),
        )
        session.add(existing)
    else:
        existing.canonical_slug = record.get("canonical_slug")
        existing.name = record.get("name")
        existing.description = record.get("description")
        existing.context_length = record.get("context_length")
        existing.architecture_json = architecture_json
        existing.input_modalities_json = input_modalities_json
        existing.output_modalities_json = output_modalities_json
        existing.supported_parameters_json = supported_parameters_json
        existing.input_per_1m_usd = sanitize_price_per_million(record.get("input_per_1m_usd"))
        existing.output_per_1m_usd = sanitize_price_per_million(record.get("output_per_1m_usd"))
        existing.top_provider_json = top_provider_json
        existing.expiration_date = record.get("expiration_date")
        existing.source = record.get("source") or "openrouter"
        existing.fetched_at = datetime.now(UTC)

    session.flush()
    return existing


def sync_openrouter_metadata(session: Session) -> int:
    records = fetch_openrouter_models_payload()
    for record in records:
        upsert_model_metadata(session, record)
    return len(records)


def ensure_openrouter_metadata_fresh(
    session: Session,
    *,
    max_age: timedelta = METADATA_MAX_AGE,
) -> bool:
    latest = session.scalar(
        select(ModelMetadata).order_by(ModelMetadata.fetched_at.desc()).limit(1)
    )
    now = datetime.now(UTC)
    if latest is not None:
        fetched_at = latest.fetched_at
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)
        if now - fetched_at < max_age:
            return False

    try:
        sync_openrouter_metadata(session)
        session.flush()
        return True
    except Exception:
        return False


@dataclass(slots=True)
class MetadataLookup:
    exact: dict[str, ModelMetadata] = field(default_factory=dict)
    by_suffix: dict[str, list[ModelMetadata]] = field(default_factory=dict)

    def get(self, key: str) -> ModelMetadata | None:
        normalized = _index_key(key)
        return self.exact.get(key) or self.exact.get(normalized)


def _index_key(value: str) -> str:
    return value.strip().lower()


def _normalize_model_key(value: str) -> str:
    return value.strip().lower().replace("_", "-")


def _register_exact(index: dict[str, ModelMetadata], key: str, record: ModelMetadata) -> None:
    if not key.strip():
        return
    index[key] = record
    index[_index_key(key)] = record


def _register_suffix(by_suffix: dict[str, list[ModelMetadata]], suffix: str, record: ModelMetadata) -> None:
    key = _index_key(suffix)
    if not key:
        return
    bucket = by_suffix.setdefault(key, [])
    if record not in bucket:
        bucket.append(record)


def _aliases_for_metadata_record(record: ModelMetadata) -> tuple[set[str], set[str]]:
    exact: set[str] = set()
    suffixes: set[str] = set()

    for value in (record.id, record.canonical_slug):
        if not isinstance(value, str) or not value.strip():
            continue
        stripped = value.strip()
        exact.add(stripped)
        exact.add(_normalize_model_key(stripped))

    bare = bare_model_id(record.id)
    suffixes.add(bare)
    suffixes.add(_normalize_model_key(bare))
    suffixes.add(f"models/{bare}")
    suffixes.add(f"models/{_normalize_model_key(bare)}")

    if record.id.startswith("models/"):
        exact.add(record.id)
        exact.add(_normalize_model_key(record.id))

    for alias in list(exact):
        if "/" in alias:
            suffix = alias.split("/", 1)[-1]
            suffixes.add(suffix)
            suffixes.add(_normalize_model_key(suffix))
            suffixes.add(f"models/{suffix}")

    return exact, suffixes


def load_metadata_index(session: Session) -> MetadataLookup:
    rows = session.scalars(select(ModelMetadata)).all()
    exact: dict[str, ModelMetadata] = {}
    by_suffix: dict[str, list[ModelMetadata]] = {}

    for row in rows:
        exact_aliases, suffix_aliases = _aliases_for_metadata_record(row)
        for alias in exact_aliases:
            _register_exact(exact, alias, row)
        for alias in suffix_aliases:
            _register_suffix(by_suffix, alias, row)

    return MetadataLookup(exact=exact, by_suffix=by_suffix)


def _candidate_match_keys(provider_id: str, model_id: str) -> list[str]:
    bare = bare_model_id(model_id)
    normalized_model = _normalize_model_key(model_id)
    normalized_bare = _normalize_model_key(bare)
    keys = [
        model_id,
        normalized_model,
        bare,
        normalized_bare,
        f"models/{bare}",
        f"models/{normalized_bare}",
        f"{provider_id}/{model_id}",
        f"{provider_id}/{normalized_model}",
        f"{provider_id}/{bare}",
        f"{provider_id}/{normalized_bare}",
    ]
    if "/" in model_id:
        keys.append(model_id.split("/", 1)[-1])
        keys.append(_normalize_model_key(model_id.split("/", 1)[-1]))

    vendor = openrouter_vendor_for_provider(provider_id)
    if vendor:
        keys.extend(
            [
                f"{vendor}/{model_id}",
                f"{vendor}/{normalized_model}",
                f"{vendor}/{bare}",
                f"{vendor}/{normalized_bare}",
            ]
        )

    deduped: list[str] = []
    seen: set[str] = set()
    for key in keys:
        lowered = key.lower()
        if lowered not in seen:
            seen.add(lowered)
            deduped.append(key)
    return deduped


def _pick_suffix_match(
    provider_id: str,
    model_id: str,
    candidates: list[ModelMetadata],
) -> ModelMetadata | None:
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    vendor = openrouter_vendor_for_provider(provider_id)
    bare = _normalize_model_key(bare_model_id(model_id))

    def score(record: ModelMetadata) -> int:
        or_id = record.id.lower()
        points = 0
        if vendor and or_id.startswith(f"{vendor}/"):
            points += 100
        if _normalize_model_key(bare_model_id(record.id)) == bare:
            points += 50
        slug = record.canonical_slug.lower() if record.canonical_slug else ""
        if vendor and slug == f"{vendor}/{bare}":
            points += 40
        if vendor and slug.endswith(f"/{bare}"):
            points += 20
        return points

    ranked = sorted(
        ((score(record), record) for record in candidates),
        key=lambda item: item[0],
        reverse=True,
    )
    best_score, best = ranked[0]
    if best_score <= 0:
        return None
    if len(ranked) > 1 and ranked[1][0] == best_score:
        return None
    return best


def match_model_metadata(
    provider_id: str,
    model_id: str,
    metadata_index: MetadataLookup,
) -> ModelMetadata | None:
    for key in _candidate_match_keys(provider_id, model_id):
        match = metadata_index.get(key)
        if match is not None:
            return match

    suffix_key = _index_key(bare_model_id(model_id))
    return _pick_suffix_match(
        provider_id,
        model_id,
        metadata_index.by_suffix.get(suffix_key, []),
    )


def parsed_openrouter_to_enrichment(parsed: dict[str, Any]) -> dict[str, Any]:
    return {
        "canonical_slug": parsed.get("canonical_slug"),
        "description": parsed.get("description"),
        "context_length": parsed.get("context_length"),
        "architecture": parsed.get("architecture") or {},
        "input_modalities": parsed.get("input_modalities") or [],
        "output_modalities": parsed.get("output_modalities") or [],
        "supported_parameters": parsed.get("supported_parameters") or [],
        "input_per_1m_usd": sanitize_price_per_million(parsed.get("input_per_1m_usd")),
        "output_per_1m_usd": sanitize_price_per_million(parsed.get("output_per_1m_usd")),
        "top_provider": parsed.get("top_provider"),
        "expiration_date": parsed.get("expiration_date"),
        "metadata_source": "openrouter",
        "openrouter_id": parsed.get("id"),
    }


def metadata_to_dict(record: ModelMetadata) -> dict[str, Any]:
    return {
        "canonical_slug": record.canonical_slug,
        "description": record.description,
        "context_length": record.context_length,
        "architecture": json.loads(record.architecture_json or "{}"),
        "input_modalities": json.loads(record.input_modalities_json or "[]"),
        "output_modalities": json.loads(record.output_modalities_json or "[]"),
        "supported_parameters": json.loads(record.supported_parameters_json or "[]"),
        "input_per_1m_usd": sanitize_price_per_million(record.input_per_1m_usd),
        "output_per_1m_usd": sanitize_price_per_million(record.output_per_1m_usd),
        "top_provider": json.loads(record.top_provider_json) if record.top_provider_json else None,
        "expiration_date": record.expiration_date,
        "metadata_source": record.source,
        "openrouter_id": record.id,
    }


def build_pricing_index(session: Session) -> dict[tuple[str, str], PricingOverride]:
    rows = session.scalars(select(PricingOverride).where(PricingOverride.enabled.is_(True))).all()
    return {(row.provider_id, row.model): row for row in rows}


def build_usage_index(session: Session) -> dict[tuple[str, str], ModelUsageStats]:
    providers_by_id = list_providers(session)
    groups: dict[tuple[str, str], list] = {}

    for record in list_requests(session):
        provider_id = record.provider or "unknown"
        resolved_model = model_name(record)
        groups.setdefault((provider_id, resolved_model), []).append(record)

    usage_index: dict[tuple[str, str], ModelUsageStats] = {}
    for (provider_id, model_id), records in groups.items():
        token_total = sum(record.total_tokens for record in records)
        cost_total = sum(record.estimated_cost_usd or 0.0 for record in records)
        average_latency = round(
            sum((record.duration_ms or 0) for record in records) / max(1, len(records)),
        )
        error_count = sum(1 for record in records if request_status(record) == "error")
        usage_index[(provider_id, model_id)] = ModelUsageStats(
            request_count=len(records),
            token_total=token_total,
            cost_usd=round_decimal(cost_total),
            avg_latency_ms=average_latency,
            error_rate=round_percent((error_count / max(1, len(records))) * 100),
        )

        display_name = providers_by_id[provider_id].display_name if provider_id in providers_by_id else None
        if display_name:
            usage_index[(display_name, model_id)] = usage_index[(provider_id, model_id)]

    return usage_index


def enrich_provider_model(
    *,
    provider: Provider,
    raw_model: dict,
    metadata_index: MetadataLookup,
    pricing_index: dict[tuple[str, str], PricingOverride],
    usage_index: dict[tuple[str, str], ModelUsageStats],
) -> dict[str, Any]:
    model_id = raw_model["id"]
    display_name = raw_model.get("display_name")
    if not isinstance(display_name, str) or not display_name.strip():
        display_name = model_id

    metadata = match_model_metadata(provider.id, model_id, metadata_index)
    pricing = pricing_index.get((provider.id, model_id))

    enriched: dict[str, Any] = {
        "id": model_id,
        "display_name": display_name if isinstance(display_name, str) else model_id,
        "owned_by": raw_model.get("owned_by"),
        "metadata_source": "unknown",
        "canonical_slug": None,
        "description": None,
        "context_length": None,
        "architecture": {},
        "input_modalities": [],
        "output_modalities": [],
        "supported_parameters": [],
        "input_per_1m_usd": None,
        "output_per_1m_usd": None,
        "top_provider": None,
        "expiration_date": None,
        "openrouter_id": None,
        "usage": None,
    }

    if metadata is not None:
        enriched.update(metadata_to_dict(metadata))
        enriched["metadata_source"] = "openrouter"
        if metadata.name and (not raw_model.get("display_name") or enriched["display_name"] == model_id):
            enriched["display_name"] = metadata.name
    else:
        parsed = raw_model.get("openrouter_metadata")
        if isinstance(parsed, dict):
            enriched.update(parsed_openrouter_to_enrichment(parsed))
            if isinstance(parsed.get("name"), str) and parsed["name"].strip():
                if not raw_model.get("display_name") or enriched["display_name"] == model_id:
                    enriched["display_name"] = parsed["name"].strip()

    if pricing is not None:
        enriched["input_per_1m_usd"] = pricing.input_per_1m_usd
        enriched["output_per_1m_usd"] = pricing.output_per_1m_usd
        if enriched["metadata_source"] == "unknown":
            enriched["metadata_source"] = "pricing"
        elif enriched["metadata_source"] == "openrouter":
            enriched["metadata_source"] = "openrouter"

    usage = usage_index.get((provider.id, model_id))
    if usage is None:
        usage = usage_index.get((provider.display_name, model_id))
    if usage is not None and usage.request_count > 0:
        enriched["usage"] = {
            "requestCount": usage.request_count,
            "tokenTotal": usage.token_total,
            "costUsd": usage.cost_usd,
            "avgLatencyMs": usage.avg_latency_ms,
            "errorRate": usage.error_rate,
        }

    upstream_description = raw_model.get("description")
    if isinstance(upstream_description, str) and upstream_description.strip() and not enriched.get(
        "description"
    ):
        enriched["description"] = upstream_description.strip()

    upstream_context = raw_model.get("context_length")
    if isinstance(upstream_context, int) and upstream_context > 0 and enriched.get("context_length") is None:
        enriched["context_length"] = upstream_context

    upstream_display_name = raw_model.get("display_name")
    if (
        isinstance(upstream_display_name, str)
        and upstream_display_name.strip()
        and enriched["display_name"] == model_id
    ):
        enriched["display_name"] = upstream_display_name.strip()

    return enriched
