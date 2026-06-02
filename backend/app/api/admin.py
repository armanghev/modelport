from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urljoin

import httpx

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.database import (
    AppSetting,
    ModelAlias,
    PricingOverride,
    Provider,
    ProviderCredential,
    ProviderHealthCheck,
    RoutingRule,
    clear_default_credentials,
    get_setting,
    is_credential_configured,
    resolve_env_secret,
    resolved_key_hint,
    set_setting,
)
from app.schemas.admin import (
    AppearanceSettings,
    CredentialSecretResponse,
    DefaultRoutingSettings,
    ModelAliasCreate,
    ModelAliasResponse,
    ModelAliasUpdate,
    PricingOverrideCreate,
    PricingOverrideResponse,
    PricingOverrideUpdate,
    ProviderCreate,
    ProviderCredentialCreate,
    ProviderCredentialResponse,
    ProviderCredentialUpdate,
    ProviderHealthPayload,
    ProviderResponse,
    ProviderUpdate,
    ProviderRoutingRuleSummary,
    RoutingRuleCreate,
    RoutingRuleResponse,
    RoutingRuleUpdate,
    SettingsEnvelope,
    SettingsResponse,
    TrackingSettings,
)
from app.security import EncryptionConfigurationError, decrypt_secret, encrypt_secret

router = APIRouter(prefix="/admin", tags=["admin"])


def get_session(request: Request) -> Session:
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    with session_factory() as session:
        yield session


def require_provider(session: Session, provider_id: str) -> Provider:
    provider = session.get(Provider, provider_id)
    if provider is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found.")
    return provider


def require_credential(session: Session, credential_id: str) -> ProviderCredential:
    credential = session.get(ProviderCredential, credential_id)
    if credential is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found.")
    return credential


def require_alias(session: Session, alias: str) -> ModelAlias:
    record = session.get(ModelAlias, alias)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model alias not found.")
    return record


def require_routing_rule(session: Session, rule_id: str) -> RoutingRule:
    record = session.get(RoutingRule, rule_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routing rule not found.")
    return record


def require_pricing_override(session: Session, pricing_id: str) -> PricingOverride:
    record = session.get(PricingOverride, pricing_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pricing override not found.")
    return record


def serialize_provider(provider: Provider) -> ProviderResponse:
    default_credential = next((credential for credential in provider.credentials if credential.is_default), None)
    return ProviderResponse.model_validate(
        {
            "id": provider.id,
            "display_name": provider.display_name,
            "provider_type": provider.provider_type,
            "base_url": provider.base_url,
            "enabled": provider.enabled,
            "created_at": provider.created_at,
            "updated_at": provider.updated_at,
            "default_credential_id": default_credential.id if default_credential else None,
        }
    )


def serialize_credential(credential: ProviderCredential) -> ProviderCredentialResponse:
    return ProviderCredentialResponse.model_validate(
        {
            "id": credential.id,
            "provider_id": credential.provider_id,
            "display_name": credential.display_name,
            "source": credential.source,
            "api_key_env": credential.api_key_env,
            "key_hint": resolved_key_hint(credential),
            "configured": is_credential_configured(credential),
            "is_default": credential.is_default,
            "enabled": credential.enabled,
            "created_at": credential.created_at,
            "updated_at": credential.updated_at,
        }
    )


def serialize_alias(record: ModelAlias) -> ModelAliasResponse:
    return ModelAliasResponse.model_validate(record)


def serialize_routing_rule(record: RoutingRule) -> RoutingRuleResponse:
    return RoutingRuleResponse.model_validate(
        {
            "id": record.id,
            "match": record.match,
            "priority": record.priority,
            "primary_provider_id": record.primary_provider_id,
            "primary_alias": record.primary_alias,
            "fallback_provider_ids": json.loads(record.fallback_provider_ids_json),
            "enabled": record.enabled,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def serialize_pricing(record: PricingOverride) -> PricingOverrideResponse:
    return PricingOverrideResponse.model_validate(record)


def resolve_credential_secret(credential: ProviderCredential | None) -> str | None:
    if credential is None:
        return None
    if credential.source == "env":
        return resolve_env_secret(credential)
    if credential.encrypted_api_key:
        return decrypt_secret(credential.encrypted_api_key)
    return None


def get_default_credential(provider: Provider) -> ProviderCredential | None:
    enabled_credentials = [credential for credential in provider.credentials if credential.enabled]
    configured_credentials = [
        credential for credential in enabled_credentials if is_credential_configured(credential)
    ]

    default_configured = next(
        (credential for credential in configured_credentials if credential.is_default),
        None,
    )
    if default_configured is not None:
        return default_configured

    if configured_credentials:
        return configured_credentials[0]

    default_enabled = next((credential for credential in enabled_credentials if credential.is_default), None)
    if default_enabled is not None:
        return default_enabled

    if enabled_credentials:
        return enabled_credentials[0]

    return provider.credentials[0] if provider.credentials else None


def build_health_check_url(provider: Provider) -> str:
    normalized_base = provider.base_url.rstrip("/") + "/"
    if provider.provider_type == "anthropic_compatible":
        return urljoin(normalized_base, "v1/models")
    return urljoin(normalized_base, "models")


def provider_supports_anonymous_health_check(provider: Provider) -> bool:
    return provider.provider_type == "local_openai_compatible" or (
        "localhost" in provider.base_url or "127.0.0.1" in provider.base_url
    )


def parse_model_count(payload: dict) -> int:
    data = payload.get("data")
    if isinstance(data, list):
        return len(data)
    models = payload.get("models")
    if isinstance(models, list):
        return len(models)
    return 0


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

    credential = get_default_credential(provider)
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

    if not provider_supports_anonymous_health_check(provider) and not secret:
        return record_provider_health_check(
            session,
            provider.id,
            "offline",
            0,
            0,
            "No configured credential available.",
        )

    headers: dict[str, str] = {}
    if provider.provider_type == "anthropic_compatible":
        headers["anthropic-version"] = "2023-06-01"
        if secret:
            headers["x-api-key"] = secret
    elif secret:
        headers["Authorization"] = f"Bearer {secret}"

    start = time.perf_counter()
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(build_health_check_url(provider), headers=headers)
            response.raise_for_status()
            payload = response.json()
        latency_ms = max(1, round((time.perf_counter() - start) * 1000))
        available_model_count = parse_model_count(payload)
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
        "displayName": provider.display_name,
        "type": provider.provider_type,
        "status": status_value,
        "baseUrl": provider.base_url,
        "requestsToday": 0,
        "successRate": success_rate,
        "errorRate": error_rate,
        "avgLatencyMs": avg_latency,
        "availableModelCount": available_model_count,
        "lastCheckedAt": last_checked_at,
        "lastError": last_error,
    }


def collect_provider_health_payload(session: Session) -> dict:
    providers = session.scalars(select(Provider).order_by(Provider.id)).all()
    cards: list[dict] = []
    freshness_cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=60)

    for provider in providers:
        latest_check = get_latest_provider_health_check(session, provider.id)
        if latest_check is None or latest_check.checked_at < freshness_cutoff:
            latest_check = run_provider_health_check(session, provider)
            session.commit()

        recent_checks = get_recent_provider_health_checks(session, provider.id)
        cards.append(serialize_provider_health_card(provider, latest_check, recent_checks))

    routing_rules = session.scalars(
        select(RoutingRule).order_by(RoutingRule.priority.desc(), RoutingRule.match)
    ).all()

    return {
        "cards": cards,
        "routingRules": [
            ProviderRoutingRuleSummary(
                match=rule.match,
                primaryProvider=rule.primary_provider_id,
                fallbackProviders=json.loads(rule.fallback_provider_ids_json),
            ).model_dump()
            for rule in routing_rules
        ],
        "details": [],
    }


def validate_fallback_providers(session: Session, provider_ids: list[str]) -> None:
    for provider_id in provider_ids:
        require_provider(session, provider_id)


def apply_credential_secret(credential: ProviderCredential, api_key: str) -> None:
    try:
        encrypted_api_key, key_hint = encrypt_secret(api_key)
    except EncryptionConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    credential.source = "database"
    credential.api_key_env = None
    credential.encrypted_api_key = encrypted_api_key
    credential.key_hint = key_hint


@router.get("/providers", response_model=list[ProviderResponse])
def list_providers(session: Session = Depends(get_session)) -> list[ProviderResponse]:
    providers = session.scalars(select(Provider).order_by(Provider.id)).all()
    return [serialize_provider(provider) for provider in providers]


@router.get("/providers/health", response_model=ProviderHealthPayload)
def get_provider_health(session: Session = Depends(get_session)) -> ProviderHealthPayload:
    return ProviderHealthPayload.model_validate(collect_provider_health_payload(session))


@router.post("/providers", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
def create_provider(payload: ProviderCreate, session: Session = Depends(get_session)) -> ProviderResponse:
    if session.get(Provider, payload.id) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provider already exists.")

    provider = Provider(**payload.model_dump())
    session.add(provider)
    session.commit()
    session.refresh(provider)
    return serialize_provider(provider)


@router.patch("/providers/{provider_id}", response_model=ProviderResponse)
def update_provider(
    provider_id: str,
    payload: ProviderUpdate,
    session: Session = Depends(get_session),
) -> ProviderResponse:
    provider = require_provider(session, provider_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(provider, field, value)
    session.commit()
    session.refresh(provider)
    return serialize_provider(provider)


@router.get("/provider-credentials", response_model=list[ProviderCredentialResponse])
def list_provider_credentials(session: Session = Depends(get_session)) -> list[ProviderCredentialResponse]:
    credentials = session.scalars(
        select(ProviderCredential).order_by(ProviderCredential.provider_id, ProviderCredential.display_name)
    ).all()
    return [serialize_credential(credential) for credential in credentials]


@router.post(
    "/provider-credentials",
    response_model=ProviderCredentialResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_provider_credential(
    payload: ProviderCredentialCreate,
    session: Session = Depends(get_session),
) -> ProviderCredentialResponse:
    require_provider(session, payload.provider_id)
    if payload.source == "env" and not payload.api_key_env:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Env credentials require api_key_env.")
    if payload.source == "database" and not payload.api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Database credentials require api_key.")

    credential = ProviderCredential(
        provider_id=payload.provider_id,
        display_name=payload.display_name,
        source=payload.source,
        api_key_env=payload.api_key_env,
        enabled=payload.enabled,
        is_default=payload.is_default,
    )
    if payload.source == "database":
        apply_credential_secret(credential, payload.api_key or "")

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
    elif "source" in updates and updates["source"] == "env":
        api_key_env = updates.get("api_key_env", credential.api_key_env)
        if not api_key_env:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Env credentials require api_key_env.")
        credential.source = "env"
        credential.api_key_env = api_key_env
        credential.encrypted_api_key = None
        credential.key_hint = None
    elif "api_key_env" in updates:
        if credential.source != "env":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="api_key_env can only be edited for env credentials.",
            )
        credential.api_key_env = updates["api_key_env"]

    session.commit()
    session.refresh(credential)
    return serialize_credential(credential)


@router.get("/provider-credentials/{credential_id}/secret", response_model=CredentialSecretResponse)
def reveal_provider_credential(
    credential_id: str,
    session: Session = Depends(get_session),
) -> CredentialSecretResponse:
    credential = require_credential(session, credential_id)
    if credential.source == "env":
        from app.database import resolve_env_secret

        api_key = resolve_env_secret(credential)
        return CredentialSecretResponse(
            id=credential.id,
            source="env",
            configured=bool(api_key),
            api_key=api_key,
        )

    if not credential.encrypted_api_key:
        return CredentialSecretResponse(
            id=credential.id,
            source="database",
            configured=False,
            api_key=None,
        )

    try:
        api_key = decrypt_secret(credential.encrypted_api_key)
    except EncryptionConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return CredentialSecretResponse(
        id=credential.id,
        source="database",
        configured=True,
        api_key=api_key,
    )


@router.get("/model-aliases", response_model=list[ModelAliasResponse])
def list_model_aliases(session: Session = Depends(get_session)) -> list[ModelAliasResponse]:
    aliases = session.scalars(select(ModelAlias).order_by(ModelAlias.alias)).all()
    return [serialize_alias(record) for record in aliases]


@router.post("/model-aliases", response_model=ModelAliasResponse, status_code=status.HTTP_201_CREATED)
def create_model_alias(payload: ModelAliasCreate, session: Session = Depends(get_session)) -> ModelAliasResponse:
    require_provider(session, payload.provider_id)
    if payload.credential_id:
        require_credential(session, payload.credential_id)
    if session.get(ModelAlias, payload.alias) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Model alias already exists.")

    record = ModelAlias(**payload.model_dump())
    session.add(record)
    session.commit()
    session.refresh(record)
    return serialize_alias(record)


@router.patch("/model-aliases/{alias}", response_model=ModelAliasResponse)
def update_model_alias(
    alias: str,
    payload: ModelAliasUpdate,
    session: Session = Depends(get_session),
) -> ModelAliasResponse:
    record = require_alias(session, alias)
    updates = payload.model_dump(exclude_unset=True)
    if "provider_id" in updates and updates["provider_id"] is not None:
        require_provider(session, updates["provider_id"])
    if "credential_id" in updates and updates["credential_id"] is not None:
        require_credential(session, updates["credential_id"])
    for field, value in updates.items():
        setattr(record, field, value)
    session.commit()
    session.refresh(record)
    return serialize_alias(record)


@router.get("/routing-rules", response_model=list[RoutingRuleResponse])
def list_routing_rules(session: Session = Depends(get_session)) -> list[RoutingRuleResponse]:
    records = session.scalars(select(RoutingRule).order_by(RoutingRule.priority.desc(), RoutingRule.match)).all()
    return [serialize_routing_rule(record) for record in records]


@router.post("/routing-rules", response_model=RoutingRuleResponse, status_code=status.HTTP_201_CREATED)
def create_routing_rule(payload: RoutingRuleCreate, session: Session = Depends(get_session)) -> RoutingRuleResponse:
    require_provider(session, payload.primary_provider_id)
    validate_fallback_providers(session, payload.fallback_provider_ids)

    record = RoutingRule(
        match=payload.match,
        priority=payload.priority,
        primary_provider_id=payload.primary_provider_id,
        primary_alias=payload.primary_alias,
        fallback_provider_ids_json=json.dumps(payload.fallback_provider_ids),
        enabled=payload.enabled,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return serialize_routing_rule(record)


@router.patch("/routing-rules/{rule_id}", response_model=RoutingRuleResponse)
def update_routing_rule(
    rule_id: str,
    payload: RoutingRuleUpdate,
    session: Session = Depends(get_session),
) -> RoutingRuleResponse:
    record = require_routing_rule(session, rule_id)
    updates = payload.model_dump(exclude_unset=True)
    if "primary_provider_id" in updates and updates["primary_provider_id"] is not None:
        require_provider(session, updates["primary_provider_id"])
    if "fallback_provider_ids" in updates and updates["fallback_provider_ids"] is not None:
        validate_fallback_providers(session, updates["fallback_provider_ids"])
        record.fallback_provider_ids_json = json.dumps(updates.pop("fallback_provider_ids"))
    for field, value in updates.items():
        setattr(record, field, value)
    session.commit()
    session.refresh(record)
    return serialize_routing_rule(record)


@router.get("/pricing", response_model=list[PricingOverrideResponse])
def list_pricing(session: Session = Depends(get_session)) -> list[PricingOverrideResponse]:
    records = session.scalars(select(PricingOverride).order_by(PricingOverride.provider_id, PricingOverride.model)).all()
    return [serialize_pricing(record) for record in records]


@router.post("/pricing", response_model=PricingOverrideResponse, status_code=status.HTTP_201_CREATED)
def create_pricing_override(
    payload: PricingOverrideCreate,
    session: Session = Depends(get_session),
) -> PricingOverrideResponse:
    require_provider(session, payload.provider_id)
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
        require_provider(session, updates["provider_id"])
    for field, value in updates.items():
        setattr(record, field, value)
    session.commit()
    session.refresh(record)
    return serialize_pricing(record)


@router.patch("/settings/default-routing")
def update_default_routing(
    payload: DefaultRoutingSettings,
    session: Session = Depends(get_session),
) -> dict:
    current = get_setting(session, "default_routing", {})
    current.update(payload.model_dump(exclude_unset=True))
    set_setting(session, "default_routing", current)
    session.commit()
    return current


@router.patch("/settings/tracking")
def update_tracking_settings(
    payload: TrackingSettings,
    session: Session = Depends(get_session),
) -> dict:
    current = get_setting(session, "tracking", {})
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
    aliases = session.scalars(select(ModelAlias).order_by(ModelAlias.alias)).all()
    routing_rules = session.scalars(
        select(RoutingRule).order_by(RoutingRule.priority.desc(), RoutingRule.match)
    ).all()
    pricing = session.scalars(
        select(PricingOverride).order_by(PricingOverride.provider_id, PricingOverride.model)
    ).all()

    return SettingsResponse(
        providers=[serialize_provider(provider) for provider in providers],
        provider_credentials=[serialize_credential(credential) for credential in credentials],
        model_aliases=[serialize_alias(record) for record in aliases],
        routing_rules=[serialize_routing_rule(record) for record in routing_rules],
        pricing_overrides=[serialize_pricing(record) for record in pricing],
        settings=SettingsEnvelope(
            default_routing=get_setting(session, "default_routing", {}),
            tracking=get_setting(session, "tracking", {}),
            appearance=get_setting(session, "appearance", {}),
        ),
    )
