from __future__ import annotations

import hmac
import os
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi import Header
from sqlalchemy.orm import Session, sessionmaker

from sqlalchemy import select

from app.database import Provider, ProviderCredential, ProviderHealthCheck
from app.errors.upstream import format_exception_detail_for_log
from app.routing.model_prefixes import (
    ResolvedModelSelection,
    infer_provider_from_model,
    normalize_upstream_for_provider,
)
from app.routing.provider_router import ResolvedProviderRoute, resolve_provider_routes
from app.security import EncryptionConfigurationError, decrypt_secret
from app.tracking.cost_service import calculate_estimated_cost_usd
from app.tracking.io_logging import io_log_kwargs
from app.tracking.log_service import create_api_request_log
from app.tracking.pricing import find_pricing_override
from app.tracking.usage_service import UsageSnapshot

MODELPORT_PROVIDER_HEADER = "X-ModelPort-Provider"

ModelPortProviderHeader = Annotated[
    str | None,
    Header(
        alias=MODELPORT_PROVIDER_HEADER,
        description=(
            "Optional provider override (for example openrouter, openai, anthropic). "
            "Required for GET /v1/models and when the model id has no recognized prefix."
        ),
    ),
]

bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    description="ModelPort proxy token from the MODELPORT_TOKEN environment variable.",
)


def get_session(request: Request) -> Session:
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    with session_factory() as session:
        yield session


def require_proxy_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    token_env_name = request.app.state.config.security.modelport_token
    expected_token = os.environ.get(token_env_name)
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{token_env_name} environment variable is not configured.",
        )

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header with a Bearer token is required.",
        )

    presented_token = credentials.credentials.strip()
    if not presented_token or not hmac.compare_digest(presented_token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid proxy token.",
        )


def resolve_credential_secret(credential: ProviderCredential | None) -> str | None:
    if credential is None or not credential.encrypted_api_key:
        return None
    return decrypt_secret(credential.encrypted_api_key)


def provider_supports_anonymous_access(base_url: str, provider_type: str) -> bool:
    return provider_type == "local_openai_compatible" or "localhost" in base_url or "127.0.0.1" in base_url


def get_known_provider_ids(session: Session) -> set[str]:
    slugs = session.scalars(select(Provider.slug)).all()
    return {slug.strip().lower() for slug in slugs if slug}


def resolve_requested_provider(request: Request, provider_id: str | None) -> str:
    header_provider = request.headers.get(MODELPORT_PROVIDER_HEADER)
    resolved_provider_id = header_provider or provider_id
    if not resolved_provider_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider selection is required. Pass {MODELPORT_PROVIDER_HEADER} or provider in the request body.",
        )
    return resolved_provider_id.strip().lower()


def resolve_proxy_model_routing(
    request: Request,
    *,
    provider_id: str | None,
    requested_model: str,
    known_provider_ids: set[str],
) -> ResolvedModelSelection:
    explicit_provider = request.headers.get(MODELPORT_PROVIDER_HEADER) or provider_id
    if explicit_provider:
        normalized_provider = explicit_provider.strip().lower()
        return ResolvedModelSelection(
            provider_id=normalized_provider,
            upstream_model=normalize_upstream_for_provider(
                normalized_provider,
                requested_model,
            ),
        )

    inferred = infer_provider_from_model(requested_model, known_provider_ids)
    if inferred is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Provider selection is required. Pass {MODELPORT_PROVIDER_HEADER}, provider in the request body, "
                "or use a model id with a recognized provider or native prefix."
            ),
        )
    return inferred


def resolve_client_name(request: Request) -> str | None:
    return request.headers.get("User-Agent")


def persist_provider_health_status(
    session: Session,
    *,
    provider_id: str,
    status_value: str,
    error_message: str | None,
    latency_ms: int = 0,
    available_model_count: int = 0,
) -> None:
    session.add(
        ProviderHealthCheck(
            provider_id=provider_id,
            status=status_value,
            latency_ms=latency_ms,
            available_model_count=available_model_count,
            error_message=error_message,
        )
    )
    session.commit()


def build_upstream_payload(payload, *, upstream_model: str) -> dict:
    upstream = payload.model_dump(
        exclude={"provider", "fallback_providers"},
        exclude_none=True,
    )
    upstream["model"] = upstream_model
    return upstream


def classify_provider_failure_status(exc: HTTPException) -> str:
    if exc.status_code == status.HTTP_502_BAD_GATEWAY:
        return "degraded"
    detail = exc.detail
    if isinstance(detail, dict) and detail.get("upstream_status_code") is not None:
        return "degraded"
    if status.HTTP_400_BAD_REQUEST <= exc.status_code < status.HTTP_500_INTERNAL_SERVER_ERROR:
        return "degraded"
    return "offline"


def resolve_provider_secret(credential: ProviderCredential | None) -> str | None:
    try:
        return resolve_credential_secret(credential)
    except EncryptionConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


def ensure_provider_secret_available(
    resolved_route: ResolvedProviderRoute,
    provider_secret: str | None,
) -> None:
    if not provider_supports_anonymous_access(
        resolved_route.provider.base_url,
        resolved_route.provider.provider_type,
    ) and not provider_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No configured credential available for the selected provider.",
        )


def resolve_first_proxy_route(
    session: Session,
    *,
    provider_id: str,
    requested_model: str,
    upstream_model: str | None = None,
    fallback_provider_ids: list[str] | None = None,
) -> tuple[ResolvedProviderRoute, str | None]:
    resolved_route = resolve_provider_routes(
        session,
        provider_id=provider_id,
        requested_model=requested_model,
        upstream_model=upstream_model,
        fallback_provider_ids=fallback_provider_ids,
    )[0]
    provider_secret = resolve_provider_secret(resolved_route.credential)
    ensure_provider_secret_available(resolved_route, provider_secret)
    return resolved_route, provider_secret


def should_try_next_provider_route(
    exc: HTTPException,
    *,
    route_index: int,
    route_count: int,
    emitted_chunks: bool = False,
) -> bool:
    return (
        not emitted_chunks
        and exc.status_code in (status.HTTP_502_BAD_GATEWAY, status.HTTP_503_SERVICE_UNAVAILABLE)
        and route_index < route_count - 1
    )


def record_provider_proxy_failure(
    session: Session,
    *,
    provider_id: str,
    exc: HTTPException,
) -> None:
    persist_provider_health_status(
        session,
        provider_id=provider_id,
        status_value=classify_provider_failure_status(exc),
        error_message=format_exception_detail_for_log(exc.detail),
    )


def log_tracked_proxy_request(
    session: Session,
    *,
    input_format: str,
    output_format: str,
    endpoint: str,
    client_name: str | None,
    resolved_route: ResolvedProviderRoute,
    requested_model: str,
    duration_ms: int,
    status_code: int,
    streamed: bool,
    request_payload: Any,
    response_payload: Any,
    usage_snapshot: UsageSnapshot | None = None,
    error_message: str | None = None,
    request_id: str | None = None,
    ttfb_ms: int | None = None,
    completion_reason: str | None = None,
) -> None:
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    token_source = None
    estimated_cost_usd = None
    pricing_source = None

    if usage_snapshot is not None:
        input_tokens = usage_snapshot.input_tokens
        output_tokens = usage_snapshot.output_tokens
        total_tokens = usage_snapshot.total_tokens
        token_source = usage_snapshot.token_source
        pricing_override = find_pricing_override(
            session,
            provider_id=resolved_route.provider.id,
            model=resolved_route.upstream_model,
        )
        estimated_cost_usd, pricing_source = calculate_estimated_cost_usd(
            pricing_override,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    create_api_request_log(
        session,
        input_format=input_format,
        output_format=output_format,
        endpoint=endpoint,
        client_name=client_name,
        requested_model=requested_model,
        resolved_model=resolved_route.upstream_model,
        provider=resolved_route.provider.slug,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        token_source=token_source,
        estimated_cost_usd=estimated_cost_usd,
        pricing_source=pricing_source,
        duration_ms=duration_ms,
        status_code=status_code,
        error_message=error_message,
        streamed=streamed,
        request_id=request_id,
        ttfb_ms=ttfb_ms,
        completion_reason=completion_reason,
        **io_log_kwargs(
            session,
            request_payload=request_payload,
            response_payload=response_payload,
        ),
    )


__all__ = [
    "ModelPortProviderHeader",
    "MODELPORT_PROVIDER_HEADER",
    "bearer_scheme",
    "build_upstream_payload",
    "ensure_provider_secret_available",
    "get_session",
    "log_tracked_proxy_request",
    "provider_supports_anonymous_access",
    "persist_provider_health_status",
    "classify_provider_failure_status",
    "record_provider_proxy_failure",
    "require_proxy_token",
    "resolve_client_name",
    "resolve_credential_secret",
    "resolve_first_proxy_route",
    "resolve_provider_secret",
    "get_known_provider_ids",
    "resolve_proxy_model_routing",
    "resolve_requested_provider",
    "should_try_next_provider_route",
]
