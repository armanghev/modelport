from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, sessionmaker

from app.database import ProviderCredential, resolve_env_secret
from app.providers.openai_compatible import create_chat_completion
from app.routing.provider_router import resolve_provider_route
from app.schemas.anthropic import AnthropicMessageCreate, AnthropicMessageResponse
from app.security import EncryptionConfigurationError, decrypt_secret
from app.translators.anthropic_to_openai import translate_anthropic_message_to_openai
from app.translators.openai_to_anthropic import translate_openai_chat_completion_to_anthropic

router = APIRouter(tags=["anthropic"])


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


@router.post("/v1/messages", response_model=AnthropicMessageResponse)
def create_message(
    payload: AnthropicMessageCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
) -> AnthropicMessageResponse:
    resolved_route = resolve_provider_route(session, payload.model)

    try:
        provider_secret = resolve_credential_secret(resolved_route.credential)
    except EncryptionConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    if resolved_route.provider.provider_type == "anthropic_compatible":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Anthropic-compatible upstream providers are not implemented yet.",
        )

    if not provider_supports_anonymous_access(
        resolved_route.provider.base_url,
        resolved_route.provider.provider_type,
    ) and not provider_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No configured credential available for the selected provider.",
        )

    openai_payload = translate_anthropic_message_to_openai(
        payload,
        upstream_model=resolved_route.upstream_model,
    )
    upstream_response = create_chat_completion(
        resolved_route.provider,
        api_key=provider_secret,
        payload=openai_payload,
    )
    return translate_openai_chat_completion_to_anthropic(
        upstream_response,
        requested_model=payload.model,
    )
