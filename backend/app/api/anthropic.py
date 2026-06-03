from __future__ import annotations

import os
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, sessionmaker

from app.database import ProviderCredential, resolve_env_secret
from app.providers.openai_compatible import create_chat_completion
from app.routing.provider_router import resolve_provider_route
from app.schemas.anthropic import AnthropicMessageCreate, AnthropicMessageResponse
from app.security import EncryptionConfigurationError, decrypt_secret
from app.tracking.cost_service import calculate_estimated_cost_usd
from app.tracking.log_service import create_api_request_log
from app.tracking.pricing import find_pricing_override
from app.tracking.usage_service import UsageSnapshot, extract_usage_snapshot
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


def resolve_requested_provider(request: Request, payload: AnthropicMessageCreate) -> str:
    header_provider = request.headers.get("X-ModelPort-Provider")
    provider_id = header_provider or payload.provider
    if not provider_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provider selection is required. Pass X-ModelPort-Provider or provider in the request body.",
        )
    return provider_id.strip().lower()


def resolve_client_name(request: Request) -> str | None:
    return request.headers.get("User-Agent")


@router.post("/v1/messages", response_model=AnthropicMessageResponse)
def create_message(
    request: Request,
    payload: AnthropicMessageCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
) -> AnthropicMessageResponse:
    started_at = time.perf_counter()
    resolved_route = resolve_provider_route(
        session,
        provider_id=resolve_requested_provider(request, payload),
        requested_model=payload.model,
    )

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
    try:
        upstream_response = create_chat_completion(
            resolved_route.provider,
            api_key=provider_secret,
            payload=openai_payload,
        )
    except HTTPException as exc:
        duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
        create_api_request_log(
            session,
            input_format="anthropic",
            output_format="anthropic",
            endpoint="/v1/messages",
            client_name=resolve_client_name(request),
            requested_model=payload.model,
            resolved_model=resolved_route.upstream_model,
            provider=resolved_route.provider.id,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            token_source=None,
            estimated_cost_usd=None,
            pricing_source=None,
            duration_ms=duration_ms,
            status_code=exc.status_code,
            error_message=str(exc.detail),
            streamed=payload.stream,
            request_id=None,
        )
        raise

    usage_snapshot: UsageSnapshot = extract_usage_snapshot(openai_payload, upstream_response)
    pricing_override = find_pricing_override(
        session,
        provider_id=resolved_route.provider.id,
        model=resolved_route.upstream_model,
    )
    estimated_cost_usd, pricing_source = calculate_estimated_cost_usd(
        pricing_override,
        input_tokens=usage_snapshot.input_tokens,
        output_tokens=usage_snapshot.output_tokens,
    )
    duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
    create_api_request_log(
        session,
        input_format="anthropic",
        output_format="anthropic",
        endpoint="/v1/messages",
        client_name=resolve_client_name(request),
        requested_model=payload.model,
        resolved_model=resolved_route.upstream_model,
        provider=resolved_route.provider.id,
        input_tokens=usage_snapshot.input_tokens,
        output_tokens=usage_snapshot.output_tokens,
        total_tokens=usage_snapshot.total_tokens,
        token_source=usage_snapshot.token_source,
        estimated_cost_usd=estimated_cost_usd,
        pricing_source=pricing_source,
        duration_ms=duration_ms,
        status_code=200,
        error_message=None,
        streamed=payload.stream,
        request_id=str(upstream_response.get("id")) if upstream_response.get("id") else None,
    )
    return translate_openai_chat_completion_to_anthropic(
        upstream_response,
        requested_model=payload.model,
    )
