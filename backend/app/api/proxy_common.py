from __future__ import annotations

import os

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session, sessionmaker

from app.database import ProviderCredential, resolve_env_secret
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


def resolve_requested_provider(request: Request, provider_id: str | None) -> str:
    header_provider = request.headers.get("X-ModelPort-Provider")
    resolved_provider_id = header_provider or provider_id
    if not resolved_provider_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provider selection is required. Pass X-ModelPort-Provider or provider in the request body.",
        )
    return resolved_provider_id.strip().lower()


def resolve_client_name(request: Request) -> str | None:
    return request.headers.get("User-Agent")


__all__ = [
    "EncryptionConfigurationError",
    "get_session",
    "provider_supports_anonymous_access",
    "require_proxy_token",
    "resolve_client_name",
    "resolve_credential_secret",
    "resolve_requested_provider",
]
