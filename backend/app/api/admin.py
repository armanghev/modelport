from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urljoin

import httpx

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.analytics_service import build_provider_details, list_requests, requests_today_count
from app.api.proxy_common import (
    get_session,
    provider_supports_anonymous_access,
    resolve_credential_secret,
)
from app.database import (
    ModelMetadata,
    PricingOverride,
    Provider,
    ProviderCredential,
    ProviderHealthCheck,
    clear_default_credentials,
    get_provider_by_slug,
    get_setting,
    is_credential_configured,
    resolved_key_hint,
    set_setting,
)
from app.routing.provider_router import select_provider_credential
from app.schemas.analytics import ProviderHealthPayload
from app.model_metadata_service import (
    apply_gemini_native_model_fields,
    filter_gemini_catalog_models,
    build_pricing_index,
    build_usage_index,
    enrich_provider_model,
    ensure_openrouter_metadata_fresh,
    fetch_gemini_native_models_index,
    is_gemini_provider,
    is_openrouter_provider,
    openrouter_models_request_kwargs,
    load_metadata_index,
    parse_openrouter_upstream_models,
)
from app.schemas.admin import (
    AppearanceSettings,
    CredentialSecretResponse,
    PricingOverrideCreate,
    ProviderModelsEntry,
    ProviderModelsPayload,
    ProviderModelsTotals,
    PricingOverrideResponse,
    PricingOverrideUpdate,
    ProviderCreate,
    ProviderPresetResponse,
    ProviderCredentialCreate,
    ProviderCredentialResponse,
    ProviderCredentialUpdate,
    ProviderResponse,
    ProviderUpdate,
    SettingsEnvelope,
    SettingsResponse,
    TrackingSettings,
)
from app.security import EncryptionConfigurationError, decrypt_secret, encrypt_secret

router = APIRouter(prefix="/admin", tags=["admin"])

_TRACKING_SETTING_KEYS = frozenset({"io_logging", "retention_days"})


def normalize_tracking_settings(settings: dict) -> dict:
    return {key: value for key, value in settings.items() if key in _TRACKING_SETTING_KEYS}


def require_provider_by_id(session: Session, provider_id: str) -> Provider:
    provider = session.get(Provider, provider_id)
    if provider is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found.")
    return provider


def require_provider_by_slug(session: Session, slug: str) -> Provider:
    provider = get_provider_by_slug(session, slug)
    if provider is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found.")
    return provider


def require_credential(session: Session, credential_id: str) -> ProviderCredential:
    credential = session.get(ProviderCredential, credential_id)
    if credential is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found.")
    return credential


def delete_provider_and_related(session: Session, provider_id: str) -> None:
    session.execute(delete(PricingOverride).where(PricingOverride.provider_id == provider_id))
    session.execute(delete(ProviderHealthCheck).where(ProviderHealthCheck.provider_id == provider_id))
    provider = session.get(Provider, provider_id)
    if provider is not None:
        session.delete(provider)


def require_pricing_override(session: Session, pricing_id: str) -> PricingOverride:
    record = session.get(PricingOverride, pricing_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pricing override not found.")
    return record


def serialize_provider(
    provider: Provider,
    latest_check: ProviderHealthCheck | None = None,
) -> ProviderResponse:
    default_credential = next((credential for credential in provider.credentials if credential.is_default), None)
    return ProviderResponse.model_validate(
        {
            "id": provider.id,
            "slug": provider.slug,
            "display_name": provider.display_name,
            "provider_type": provider.provider_type,
            "base_url": provider.base_url,
            "enabled": provider.enabled,
            "created_at": provider.created_at,
            "updated_at": provider.updated_at,
            "default_credential_id": default_credential.id if default_credential else None,
            "health_status": latest_check.status if latest_check else None,
            "last_checked_at": latest_check.checked_at if latest_check else None,
            "last_error": latest_check.error_message if latest_check else None,
        }
    )


def serialize_credential(
    credential: ProviderCredential,
    provider_slug: str | None = None,
) -> ProviderCredentialResponse:
    slug = provider_slug
    if slug is None and credential.provider is not None:
        slug = credential.provider.slug
    return ProviderCredentialResponse.model_validate(
        {
            "id": credential.id,
            "provider_id": credential.provider_id,
            "provider_slug": slug or "",
            "display_name": credential.display_name,
            "key_hint": resolved_key_hint(credential),
            "configured": is_credential_configured(credential),
            "is_default": credential.is_default,
            "enabled": credential.enabled,
            "created_at": credential.created_at,
            "updated_at": credential.updated_at,
        }
    )


def serialize_pricing(record: PricingOverride, provider_slug: str | None = None) -> PricingOverrideResponse:
    return PricingOverrideResponse.model_validate(
        {
            "id": record.id,
            "provider_id": record.provider_id,
            "provider_slug": provider_slug,
            "model": record.model,
            "input_per_1m_usd": record.input_per_1m_usd,
            "output_per_1m_usd": record.output_per_1m_usd,
            "currency": record.currency,
            "enabled": record.enabled,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def build_health_check_url(provider: Provider) -> str:
    normalized_base = provider.base_url.rstrip("/") + "/"
    if provider.provider_type == "anthropic_compatible":
        return urljoin(normalized_base, "v1/models")
    return urljoin(normalized_base, "models")


def parse_model_count(payload: dict) -> int:
    data = payload.get("data")
    if isinstance(data, list):
        return len(data)
    models = payload.get("models")
    if isinstance(models, list):
        return len(models)
    return 0


def parse_provider_models(payload: dict, provider: Provider | None = None) -> list[dict]:
    if provider is not None and is_openrouter_provider(provider):
        return parse_openrouter_upstream_models(payload)

    raw_models = payload.get("data")
    if not isinstance(raw_models, list):
        raw_models = payload.get("models")
    if not isinstance(raw_models, list):
        return []

    models: list[dict] = []
    for item in raw_models:
        if isinstance(item, str):
            models.append({"id": item, "display_name": None, "owned_by": None})
            continue
        if not isinstance(item, dict):
            continue

        model_id = item.get("id") or item.get("name")
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        display_name = item.get("display_name")
        if not isinstance(display_name, str):
            display_name = item.get("name") if isinstance(item.get("name"), str) else None
        owned_by = item.get("owned_by")
        if not isinstance(owned_by, str):
            owned_by = item.get("provider") if isinstance(item.get("provider"), str) else None

        description = item.get("description")
        if not isinstance(description, str):
            description = None

        models.append(
            {
                "id": model_id,
                "display_name": display_name,
                "owned_by": owned_by,
                "description": description,
            }
        )

    return models


def record_provider_health_check(
    session: Session,
    provider_id: str,
    status_value: str,
    latency_ms: int,
    available_model_count: int,
    error_message: str | None,
) -> ProviderHealthCheck:
    record = ProviderHealthCheck(
        provider_id=provider_id,
        status=status_value,
        latency_ms=latency_ms,
        available_model_count=available_model_count,
        error_message=error_message,
    )
    session.add(record)
    session.flush()
    return record


def fetch_provider_models_from_upstream(
    provider: Provider,
    secret: str | None,
) -> tuple[list[dict], int]:
    headers: dict[str, str] = {}
    if provider.provider_type == "anthropic_compatible":
        headers["anthropic-version"] = "2023-06-01"
        if secret:
            headers["x-api-key"] = secret
    elif secret:
        headers["Authorization"] = f"Bearer {secret}"

    start = time.perf_counter()
    request_kwargs: dict = {}
    if is_openrouter_provider(provider):
        request_kwargs.update(openrouter_models_request_kwargs())
    with httpx.Client(timeout=10.0) as client:
        response = client.get(
            build_health_check_url(provider),
            headers=headers,
            **request_kwargs,
        )
        response.raise_for_status()
        payload = response.json()

    latency_ms = max(1, round((time.perf_counter() - start) * 1000))
    models = parse_provider_models(payload, provider)
    native_index: dict | None = None
    if is_gemini_provider(provider) and secret:
        try:
            native_index = fetch_gemini_native_models_index(secret)
            models = apply_gemini_native_model_fields(models, native_index)
        except httpx.HTTPError:
            native_index = None
    if is_gemini_provider(provider):
        models = filter_gemini_catalog_models(models, native_index)
    return models, latency_ms


def run_provider_health_check(session: Session, provider: Provider) -> ProviderHealthCheck:
    if not provider.enabled:
        return record_provider_health_check(
            session,
            provider.id,
            "offline",
            0,
            0,
            "Provider disabled.",
        )

    credential = select_provider_credential(provider)
    secret: str | None = None
    try:
        secret = resolve_credential_secret(credential)
    except EncryptionConfigurationError as exc:
        return record_provider_health_check(
            session,
            provider.id,
            "offline",
            0,
            0,
            str(exc),
        )

    if not provider_supports_anonymous_access(provider.base_url, provider.provider_type) and not secret:
        return record_provider_health_check(
            session,
            provider.id,
            "offline",
            0,
            0,
            "No configured credential available.",
        )

    try:
        models, latency_ms = fetch_provider_models_from_upstream(provider, secret)
        available_model_count = len(models)
        status_value = "operational" if available_model_count > 0 else "degraded"
        error_message = None if available_model_count > 0 else "Provider returned no available models."
        return record_provider_health_check(
            session,
            provider.id,
            status_value,
            latency_ms,
            available_model_count,
            error_message,
        )
    except (httpx.HTTPError, ValueError) as exc:
        return record_provider_health_check(
            session,
            provider.id,
            "offline",
            0,
            0,
            str(exc),
        )


def get_latest_provider_health_check(session: Session, provider_id: str) -> ProviderHealthCheck | None:
    return session.scalars(
        select(ProviderHealthCheck)
        .where(ProviderHealthCheck.provider_id == provider_id)
        .order_by(ProviderHealthCheck.checked_at.desc())
        .limit(1)
    ).first()


def get_recent_provider_health_checks(session: Session, provider_id: str) -> list[ProviderHealthCheck]:
    return session.scalars(
        select(ProviderHealthCheck)
        .where(ProviderHealthCheck.provider_id == provider_id)
        .order_by(ProviderHealthCheck.checked_at.desc())
        .limit(20)
    ).all()


def serialize_provider_health_card(
    provider: Provider,
    latest_check: ProviderHealthCheck | None,
    recent_checks: list[ProviderHealthCheck],
    requests_today: int,
) -> dict:
    if latest_check is None:
        last_checked_at = datetime.now(UTC).isoformat()
        status_value = "offline"
        success_rate = 0.0
        error_rate = 100.0
        avg_latency = 0
        available_model_count = 0
        last_error = "No health checks run yet."
    else:
        success_count = sum(1 for check in recent_checks if check.status == "operational")
        total_count = max(1, len(recent_checks))
        success_rate = round((success_count / total_count) * 100, 1)
        error_rate = round(100 - success_rate, 1)
        successful_latencies = [check.latency_ms for check in recent_checks if check.latency_ms > 0]
        avg_latency = round(sum(successful_latencies) / len(successful_latencies)) if successful_latencies else 0
        available_model_count = latest_check.available_model_count
        last_checked_at = latest_check.checked_at.isoformat()
        status_value = latest_check.status
        last_error = latest_check.error_message

    return {
        "id": provider.id,
        "slug": provider.slug,
        "displayName": provider.display_name,
        "type": provider.provider_type,
        "status": status_value,
        "baseUrl": provider.base_url,
        "requestsToday": requests_today,
        "successRate": success_rate,
        "errorRate": error_rate,
        "avgLatencyMs": avg_latency,
        "availableModelCount": available_model_count,
        "lastCheckedAt": last_checked_at,
        "lastError": last_error,
    }


def collect_provider_health_payload(session: Session) -> dict:
    providers = session.scalars(select(Provider).order_by(Provider.id)).all()
    all_requests = list_requests(session)
    cards: list[dict] = []
    details: list[dict] = []
    now = datetime.now(UTC)
    freshness_cutoff = datetime.now(UTC) - timedelta(seconds=60)

    for provider in providers:
        latest_check = get_latest_provider_health_check(session, provider.id)
        latest_check_at = None
        if latest_check is not None:
            latest_check_at = (
                latest_check.checked_at.replace(tzinfo=UTC)
                if latest_check.checked_at.tzinfo is None
                else latest_check.checked_at
            )
        if latest_check is None or latest_check_at < freshness_cutoff:
            latest_check = run_provider_health_check(session, provider)
            session.commit()

        recent_checks = get_recent_provider_health_checks(session, provider.id)
        cards.append(
            serialize_provider_health_card(
                provider,
                latest_check,
                recent_checks,
                requests_today=requests_today_count(all_requests, provider.slug, now),
            )
        )
        details.append(build_provider_details(all_requests, provider, now))

    return {
        "cards": cards,
        "details": details,
    }


def apply_credential_secret(credential: ProviderCredential, api_key: str) -> None:
    try:
        encrypted_api_key, key_hint = encrypt_secret(api_key)
    except EncryptionConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    credential.encrypted_api_key = encrypted_api_key
    credential.key_hint = key_hint


@router.get("/provider-presets", response_model=list[ProviderPresetResponse])
def list_provider_presets(request: Request) -> list[ProviderPresetResponse]:
    config = request.app.state.config
    presets: list[ProviderPresetResponse] = []
    for slug, preset in config.providers.items():
        protocol = "anthropic" if preset.type == "anthropic_compatible" else "openai"
        presets.append(
            ProviderPresetResponse(
                slug=slug,
                display_name=preset.display_name,
                provider_type=preset.type,
                base_url=preset.base_url,
                protocol=protocol,
            )
        )
    return presets


@router.get("/providers", response_model=list[ProviderResponse])
def list_providers(session: Session = Depends(get_session)) -> list[ProviderResponse]:
    providers = session.scalars(select(Provider).order_by(Provider.id)).all()
    return [
        serialize_provider(provider, get_latest_provider_health_check(session, provider.id))
        for provider in providers
    ]


@router.get("/providers/health", response_model=ProviderHealthPayload)
def get_provider_health(session: Session = Depends(get_session)) -> ProviderHealthPayload:
    return ProviderHealthPayload.model_validate(collect_provider_health_payload(session))


@router.get("/providers/models", response_model=ProviderModelsPayload)
def list_provider_models(session: Session = Depends(get_session)) -> ProviderModelsPayload:
    providers = session.scalars(select(Provider).order_by(Provider.id)).all()
    results: list[ProviderModelsEntry] = []
    ensure_openrouter_metadata_fresh(session)
    metadata_index = load_metadata_index(session)
    pricing_index = build_pricing_index(session)
    usage_index = build_usage_index(session)
    latest_metadata = session.scalars(
        select(ModelMetadata).order_by(ModelMetadata.fetched_at.desc()).limit(1)
    ).first()

    for provider in providers:
        if not provider.enabled:
            continue

        credential = select_provider_credential(provider)
        try:
            secret = resolve_credential_secret(credential)
        except EncryptionConfigurationError as exc:
            record_provider_health_check(
                session,
                provider.id,
                "offline",
                0,
                0,
                str(exc),
            )
            continue

        if not provider_supports_anonymous_access(provider.base_url, provider.provider_type) and not secret:
            record_provider_health_check(
                session,
                provider.id,
                "offline",
                0,
                0,
                "No configured credential available.",
            )
            continue

        try:
            models, latency_ms = fetch_provider_models_from_upstream(provider, secret)
        except (httpx.HTTPError, ValueError) as exc:
            record_provider_health_check(
                session,
                provider.id,
                "offline",
                0,
                0,
                str(exc),
            )
            continue

        available_model_count = len(models)
        status_value = "operational" if available_model_count > 0 else "degraded"
        error_message = None if available_model_count > 0 else "Provider returned no available models."
        health_check = record_provider_health_check(
            session,
            provider.id,
            status_value,
            latency_ms,
            available_model_count,
            error_message,
        )

        if status_value != "operational":
            continue

        enriched_models = [
            enrich_provider_model(
                provider=provider,
                raw_model=model,
                metadata_index=metadata_index,
                pricing_index=pricing_index,
                usage_index=usage_index,
            )
            for model in models
        ]

        results.append(
            ProviderModelsEntry(
                provider_id=provider.slug,
                provider_uuid=provider.id,
                display_name=provider.display_name,
                provider_type=provider.provider_type,
                base_url=provider.base_url,
                status=status_value,
                available_model_count=available_model_count,
                fetched_at=health_check.checked_at.isoformat(),
                models=enriched_models,
            )
        )

    session.commit()

    live_model_count = sum(entry.available_model_count for entry in results)
    priced_model_count = sum(
        1
        for entry in results
        for model in entry.models
        if (model.input_per_1m_usd is not None and model.input_per_1m_usd >= 0)
        or (model.output_per_1m_usd is not None and model.output_per_1m_usd >= 0)
    )
    used_model_count = sum(
        1
        for entry in results
        for model in entry.models
        if model.usage is not None and model.usage.requestCount > 0
    )

    totals = ProviderModelsTotals(
        live_model_count=live_model_count,
        provider_count=len(results),
        priced_model_count=priced_model_count,
        used_model_count=used_model_count,
        metadata_synced_at=latest_metadata.fetched_at.isoformat() if latest_metadata else None,
    )

    return ProviderModelsPayload(totals=totals, providers=results)


@router.post("/providers", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
def create_provider(payload: ProviderCreate, session: Session = Depends(get_session)) -> ProviderResponse:
    if get_provider_by_slug(session, payload.slug) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provider already exists.")

    provider_fields = payload.model_dump(exclude={"api_key", "credential_name"})
    provider = Provider(**provider_fields)
    session.add(provider)
    session.flush()

    if payload.api_key:
        credential = ProviderCredential(
            provider_id=provider.id,
            display_name=payload.credential_name or f"{provider.display_name} API key",
            is_default=True,
            enabled=True,
        )
        apply_credential_secret(credential, payload.api_key)
        session.add(credential)

    session.commit()
    session.refresh(provider)
    return serialize_provider(provider)


@router.patch("/providers/{provider_id}", response_model=ProviderResponse)
def update_provider(
    provider_id: str,
    payload: ProviderUpdate,
    session: Session = Depends(get_session),
) -> ProviderResponse:
    provider = require_provider_by_id(session, provider_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(provider, field, value)
    session.commit()
    session.refresh(provider)
    return serialize_provider(provider)


@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider(
    provider_id: str,
    session: Session = Depends(get_session),
) -> None:
    require_provider_by_id(session, provider_id)
    delete_provider_and_related(session, provider_id)
    session.commit()


@router.get("/provider-credentials", response_model=list[ProviderCredentialResponse])
def list_provider_credentials(session: Session = Depends(get_session)) -> list[ProviderCredentialResponse]:
    credentials = session.scalars(
        select(ProviderCredential).order_by(ProviderCredential.provider_id, ProviderCredential.display_name)
    ).all()
    providers_by_id = {
        provider.id: provider
        for provider in session.scalars(select(Provider)).all()
    }
    return [
        serialize_credential(
            credential,
            provider_slug=providers_by_id[credential.provider_id].slug
            if credential.provider_id in providers_by_id
            else "",
        )
        for credential in credentials
    ]


@router.post(
    "/provider-credentials",
    response_model=ProviderCredentialResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_provider_credential(
    payload: ProviderCredentialCreate,
    session: Session = Depends(get_session),
) -> ProviderCredentialResponse:
    require_provider_by_id(session, payload.provider_id)

    credential = ProviderCredential(
        provider_id=payload.provider_id,
        display_name=payload.display_name,
        enabled=payload.enabled,
        is_default=payload.is_default,
    )
    apply_credential_secret(credential, payload.api_key)

    if credential.is_default:
        clear_default_credentials(session, payload.provider_id)
    session.add(credential)
    session.commit()
    session.refresh(credential)
    return serialize_credential(credential)


@router.patch("/provider-credentials/{credential_id}", response_model=ProviderCredentialResponse)
def update_provider_credential(
    credential_id: str,
    payload: ProviderCredentialUpdate,
    session: Session = Depends(get_session),
) -> ProviderCredentialResponse:
    credential = require_credential(session, credential_id)
    updates = payload.model_dump(exclude_unset=True)

    if "display_name" in updates:
        credential.display_name = updates["display_name"]
    if "enabled" in updates:
        credential.enabled = updates["enabled"]
    if "is_default" in updates:
        credential.is_default = updates["is_default"]
        if credential.is_default:
            clear_default_credentials(session, credential.provider_id, exclude_id=credential.id)

    if "api_key" in updates and updates["api_key"] is not None:
        apply_credential_secret(credential, updates["api_key"])

    session.commit()
    session.refresh(credential)
    return serialize_credential(credential)


@router.delete("/provider-credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider_credential(
    credential_id: str,
    session: Session = Depends(get_session),
) -> None:
    credential = require_credential(session, credential_id)
    provider_id = credential.provider_id
    was_default = credential.is_default

    session.delete(credential)
    session.flush()

    remaining_credentials = session.scalars(
        select(ProviderCredential)
        .where(ProviderCredential.provider_id == provider_id)
        .order_by(ProviderCredential.display_name)
    ).all()

    if not remaining_credentials:
        delete_provider_and_related(session, provider_id)
    elif was_default:
        remaining_credentials[0].is_default = True

    session.commit()


@router.get("/provider-credentials/{credential_id}/secret", response_model=CredentialSecretResponse)
def reveal_provider_credential(
    credential_id: str,
    session: Session = Depends(get_session),
) -> CredentialSecretResponse:
    credential = require_credential(session, credential_id)
    if not credential.encrypted_api_key:
        return CredentialSecretResponse(
            id=credential.id,
            configured=False,
            api_key=None,
        )

    try:
        api_key = decrypt_secret(credential.encrypted_api_key)
    except EncryptionConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return CredentialSecretResponse(
        id=credential.id,
        configured=True,
        api_key=api_key,
    )


@router.get("/pricing", response_model=list[PricingOverrideResponse])
def list_pricing(session: Session = Depends(get_session)) -> list[PricingOverrideResponse]:
    records = session.scalars(select(PricingOverride).order_by(PricingOverride.provider_id, PricingOverride.model)).all()
    providers_by_id = {
        provider.id: provider
        for provider in session.scalars(select(Provider)).all()
    }
    return [
        serialize_pricing(
            record,
            provider_slug=providers_by_id[record.provider_id].slug
            if record.provider_id in providers_by_id
            else None,
        )
        for record in records
    ]


@router.post("/pricing", response_model=PricingOverrideResponse, status_code=status.HTTP_201_CREATED)
def create_pricing_override(
    payload: PricingOverrideCreate,
    session: Session = Depends(get_session),
) -> PricingOverrideResponse:
    require_provider_by_id(session, payload.provider_id)
    record = PricingOverride(**payload.model_dump())
    session.add(record)
    session.commit()
    session.refresh(record)
    return serialize_pricing(record)


@router.patch("/pricing/{pricing_id}", response_model=PricingOverrideResponse)
def update_pricing_override(
    pricing_id: str,
    payload: PricingOverrideUpdate,
    session: Session = Depends(get_session),
) -> PricingOverrideResponse:
    record = require_pricing_override(session, pricing_id)
    updates = payload.model_dump(exclude_unset=True)
    if "provider_id" in updates and updates["provider_id"] is not None:
        require_provider_by_id(session, updates["provider_id"])
    for field, value in updates.items():
        setattr(record, field, value)
    session.commit()
    session.refresh(record)
    return serialize_pricing(record)


@router.patch("/settings/tracking")
def update_tracking_settings(
    payload: TrackingSettings,
    session: Session = Depends(get_session),
) -> dict:
    current = normalize_tracking_settings(get_setting(session, "tracking", {}))
    current.update(payload.model_dump(exclude_unset=True))
    set_setting(session, "tracking", current)
    session.commit()
    return current


@router.patch("/settings/appearance")
def update_appearance_settings(
    payload: AppearanceSettings,
    session: Session = Depends(get_session),
) -> dict:
    current = get_setting(session, "appearance", {})
    current.update(payload.model_dump(exclude_unset=True))
    set_setting(session, "appearance", current)
    session.commit()
    return current


@router.get("/settings", response_model=SettingsResponse)
def get_settings(session: Session = Depends(get_session)) -> SettingsResponse:
    providers = session.scalars(select(Provider).order_by(Provider.id)).all()
    credentials = session.scalars(
        select(ProviderCredential).order_by(ProviderCredential.provider_id, ProviderCredential.display_name)
    ).all()
    pricing = session.scalars(
        select(PricingOverride).order_by(PricingOverride.provider_id, PricingOverride.model)
    ).all()

    providers_by_id = {provider.id: provider for provider in providers}

    return SettingsResponse(
        providers=[serialize_provider(provider) for provider in providers],
        provider_credentials=[
            serialize_credential(
                credential,
                provider_slug=providers_by_id[credential.provider_id].slug
                if credential.provider_id in providers_by_id
                else "",
            )
            for credential in credentials
        ],
        pricing_overrides=[
            serialize_pricing(
                record,
                provider_slug=providers_by_id[record.provider_id].slug
                if record.provider_id in providers_by_id
                else None,
            )
            for record in pricing
        ],
        settings=SettingsEnvelope(
            tracking=normalize_tracking_settings(get_setting(session, "tracking", {})),
            appearance=get_setting(session, "appearance", {}),
        ),
    )
