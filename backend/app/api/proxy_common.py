from __future__ import annotations

import os

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session, sessionmaker

from sqlalchemy import select

from app.database import Provider, ProviderCredential, ProviderHealthCheck, resolve_env_secret
from app.routing.model_prefixes import (
    ResolvedModelSelection,
    infer_provider_from_model,
    normalize_upstream_for_provider,
)
from app.security import EncryptionConfigurationError, decrypt_secret


def get_session(request: Request) -> Session:
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    with session_factory() as session:
        yield session


def require_proxy_token(request: Request) -> None:
    token_env_name = request.app.state.config.security.modelport_token
    expected_token = os.environ.get(token_env_name)
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{token_env_name} environment variable is not configured.",
        )

    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header with a Bearer token is required.",
        )

    presented_token = authorization.removeprefix("Bearer ").strip()
    if not presented_token or presented_token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid proxy token.",
        )


def resolve_credential_secret(credential: ProviderCredential | None) -> str | None:
    if credential is None:
        return None
    if credential.source == "env":
        return resolve_env_secret(credential)
    if credential.encrypted_api_key:
        return decrypt_secret(credential.encrypted_api_key)
    return None


def provider_supports_anonymous_access(base_url: str, provider_type: str) -> bool:
    return provider_type == "local_openai_compatible" or "localhost" in base_url or "127.0.0.1" in base_url


def get_known_provider_ids(session: Session) -> set[str]:
    provider_ids = session.scalars(select(Provider.id)).all()
    return {provider_id.strip().lower() for provider_id in provider_ids if provider_id}


def resolve_requested_provider(request: Request, provider_id: str | None) -> str:
    header_provider = request.headers.get("X-ModelPort-Provider")
    resolved_provider_id = header_provider or provider_id
    if not resolved_provider_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provider selection is required. Pass X-ModelPort-Provider or provider in the request body.",
        )
    return resolved_provider_id.strip().lower()


def resolve_proxy_model_routing(
    request: Request,
    *,
    provider_id: str | None,
    requested_model: str,
    known_provider_ids: set[str],
) -> ResolvedModelSelection:
    explicit_provider = request.headers.get("X-ModelPort-Provider") or provider_id
    if explicit_provider:
        normalized_provider = explicit_provider.strip().lower()
        return ResolvedModelSelection(
            provider_id=normalized_provider,
            upstream_model=normalize_upstream_for_provider(
                normalized_provider,
                requested_model,
                known_provider_ids,
            ),
        )

    inferred = infer_provider_from_model(requested_model, known_provider_ids)
    if inferred is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Provider selection is required. Pass X-ModelPort-Provider, provider in the request body, "
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


def classify_provider_failure_status(exc: HTTPException) -> str:
    if exc.status_code == status.HTTP_502_BAD_GATEWAY:
        return "degraded"
    return "offline"


__all__ = [
    "EncryptionConfigurationError",
    "get_session",
    "provider_supports_anonymous_access",
    "persist_provider_health_status",
    "classify_provider_failure_status",
    "require_proxy_token",
    "resolve_client_name",
    "resolve_credential_secret",
    "get_known_provider_ids",
    "resolve_proxy_model_routing",
    "resolve_requested_provider",
]
