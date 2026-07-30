from __future__ import annotations

import hmac
import json
import os
import time
from collections.abc import Callable, Generator, Iterator
from typing import Annotated, Any, TypeVar

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi import Header
from sqlalchemy.orm import Session, sessionmaker, sessionmaker

from sqlalchemy import select

from app.database import Provider, ProviderCredential, ProviderHealthCheck
from app.errors.upstream import build_logged_error_response, format_exception_detail_for_log
from app.routing.model_prefixes import (
    ResolvedModelSelection,
    infer_provider_from_model,
    normalize_upstream_for_provider,
)
from app.routing.provider_router import ResolvedProviderRoute, resolve_provider_routes
from app.security import EncryptionConfigurationError, decrypt_secret
from app.pricing.calculator import RequestContext, price, to_storage_usd
from app.pricing.resolver import resolve_rate_card
from app.tracking.io_logging import io_log_kwargs
from app.tracking.log_service import create_api_request_log
from app.tracking.usage_service import UsageSnapshot

T = TypeVar("T")

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


def pricing_service_tier(request_payload: Any) -> str:
    if isinstance(request_payload, dict):
        value = request_payload.get("service_tier")
    else:
        value = getattr(request_payload, "service_tier", None)
    if not isinstance(value, str):
        return "standard"
    normalized = value.strip().lower()
    if normalized in {"", "auto", "default", "standard", "standard_only"}:
        return "standard"
    return normalized


def pricing_operation_units(endpoint: str, response_payload: Any) -> dict[str, int]:
    if endpoint.startswith("/v1/images/") and isinstance(response_payload, dict):
        images = response_payload.get("data")
        if isinstance(images, list) and images:
            return {"image_output": len(images)}
    if endpoint.startswith("/v1/audio/") and isinstance(response_payload, dict):
        usage = response_payload.get("usage")
        if isinstance(usage, dict):
            return {
                operation: int(value)
                for operation, value in {
                    "audio_input_token": usage.get("input_audio_tokens"),
                    "audio_output_token": usage.get("output_audio_tokens"),
                }.items()
                if isinstance(value, int) and value > 0
            }
    return {}


def pricing_tool_calls(response_payload: Any) -> dict[str, int]:
    if not isinstance(response_payload, dict):
        return {}
    output = response_payload.get("output")
    if not isinstance(output, list):
        return {}
    names = {
        "web_search_call": "web_search",
        "code_interpreter_call": "code_interpreter",
        "file_search_call": "file_search_call",
    }
    calls: dict[str, int] = {}
    for item in output:
        if isinstance(item, dict) and (name := names.get(item.get("type"))):
            calls[name] = calls.get(name, 0) + 1
    return calls


def get_session(request: Request) -> Session:
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    with session_factory() as session:
        yield session


def _require_bearer_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
    *,
    token_env_name: str,
    invalid_detail: str,
) -> None:
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
            detail=invalid_detail,
        )


def require_proxy_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    _require_bearer_token(
        request,
        credentials,
        token_env_name=request.app.state.config.security.modelport_token,
        invalid_detail="Invalid proxy token.",
    )


def require_dashboard_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    _require_bearer_token(
        request,
        credentials,
        token_env_name=request.app.state.config.security.dashboard_token,
        invalid_detail="Invalid dashboard token.",
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
    pricing_context: RequestContext | None = None,
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
    uncached_input_tokens = None
    cache_read_tokens = None
    cache_write_5m_tokens = None
    cache_write_1h_tokens = None
    cost_input_usd = None
    cost_output_usd = None
    cost_cache_read_usd = None
    cost_cache_write_usd = None
    cost_tools_usd = None
    cost_modalities_usd = None
    pricing_units_json = None
    context_tier = None
    service_tier = pricing_service_tier(request_payload)

    if usage_snapshot is not None:
        input_tokens = usage_snapshot.input_tokens
        output_tokens = usage_snapshot.output_tokens
        total_tokens = usage_snapshot.total_tokens
        token_source = usage_snapshot.token_source
        uncached_input_tokens = usage_snapshot.uncached_input_tokens
        cache_read_tokens = usage_snapshot.cache_read_tokens
        cache_write_5m_tokens = usage_snapshot.cache_write_5m_tokens
        cache_write_1h_tokens = usage_snapshot.cache_write_1h_tokens

    context = pricing_context or RequestContext(
        service_tier=service_tier,
        operation_units=pricing_operation_units(endpoint, response_payload),
        tool_calls=pricing_tool_calls(response_payload),
    )
    service_tier = context.service_tier
    if usage_snapshot is not None or context.operation_units or context.tool_calls:
        try:
            card = resolve_rate_card(
                session,
                provider_id=resolved_route.provider.slug,
                resolved_model=resolved_route.upstream_model,
                requested_model=requested_model,
            )
            if card is not None:
                rates = card.rates_for(
                    context_tier=card.context_tier_for(input_tokens),
                    service_tier=context.service_tier,
                )
                has_priced_operations = any(
                    count > 0 and name in card.operation_rates
                    for name, count in context.operation_units.items()
                )
                has_priced_tools = any(
                    count > 0 and charge.name in context.tool_calls for charge in card.tools
                )
                if rates is not None or has_priced_operations or has_priced_tools:
                    breakdown = price(usage_snapshot, card, context)
                    estimated_cost_usd = to_storage_usd(breakdown.total_usd)
                    pricing_source = card.source
                    cost_input_usd = float(breakdown.input_usd)
                    cost_output_usd = float(breakdown.output_usd)
                    cost_cache_read_usd = float(breakdown.cache_read_usd)
                    cost_cache_write_usd = float(breakdown.cache_write_usd)
                    cost_tools_usd = float(breakdown.tools_usd)
                    cost_modalities_usd = float(breakdown.modalities_usd)
                    pricing_units_json = json.dumps(
                        context.operation_units,
                        separators=(",", ":"),
                        sort_keys=True,
                    ) or None
                    context_tier = breakdown.context_tier
                    service_tier = breakdown.service_tier
        except Exception:
            estimated_cost_usd = None
            pricing_source = "pricing_error"
            cost_input_usd = cost_output_usd = cost_cache_read_usd = None
            cost_cache_write_usd = cost_tools_usd = None
            cost_modalities_usd = pricing_units_json = None
            context_tier = service_tier = None

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
        uncached_input_tokens=uncached_input_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_5m_tokens=cache_write_5m_tokens,
        cache_write_1h_tokens=cache_write_1h_tokens,
        estimated_cost_usd=estimated_cost_usd,
        cost_input_usd=cost_input_usd,
        cost_output_usd=cost_output_usd,
        cost_cache_read_usd=cost_cache_read_usd,
        cost_cache_write_usd=cost_cache_write_usd,
        cost_tools_usd=cost_tools_usd,
        cost_modalities_usd=cost_modalities_usd,
        pricing_units_json=pricing_units_json,
        context_tier=context_tier,
        service_tier=service_tier,
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


def execute_tracked_non_stream_proxy_routes(
    session: Session,
    resolved_routes: list[ResolvedProviderRoute],
    *,
    attempt_route: Callable[[ResolvedProviderRoute, str | None, int], T],
    log_success: Callable[[Session, ResolvedProviderRoute, T], T],
    log_final_error: Callable[[Session, ResolvedProviderRoute, HTTPException], None],
) -> T:
    last_error: HTTPException | None = None
    for route_index, resolved_route in enumerate(resolved_routes):
        provider_secret = resolve_provider_secret(resolved_route.credential)

        try:
            ensure_provider_secret_available(resolved_route, provider_secret)
        except HTTPException as exc:
            if route_index < len(resolved_routes) - 1:
                record_provider_proxy_failure(
                    session,
                    provider_id=resolved_route.provider.id,
                    exc=exc,
                )
                last_error = exc
                continue
            raise

        try:
            result = attempt_route(resolved_route, provider_secret, route_index)
        except HTTPException as exc:
            record_provider_proxy_failure(
                session,
                provider_id=resolved_route.provider.id,
                exc=exc,
            )
            last_error = exc
            if should_try_next_provider_route(
                exc,
                route_index=route_index,
                route_count=len(resolved_routes),
            ):
                continue
            log_final_error(session, resolved_route, exc)
            raise

        return log_success(session, resolved_route, result)

    if last_error is not None:
        raise last_error
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="No provider could satisfy the request.",
    )


def stream_tracked_proxy_routes(
    session_factory: sessionmaker[Session],
    resolved_routes: list[ResolvedProviderRoute],
    *,
    attempt_route: Callable[
        [ResolvedProviderRoute, str | None, int, dict[str, Any]],
        Generator[str, None, None],
    ],
    log_success: Callable[[Session, ResolvedProviderRoute, dict[str, Any]], None],
    log_final_error: Callable[[Session, ResolvedProviderRoute, HTTPException, dict[str, Any]], None],
    render_final_error: Callable[[HTTPException], list[str]],
) -> Generator[str, None, None]:
    for route_index, resolved_route in enumerate(resolved_routes):
        stream_state: dict[str, Any] = {"emitted_chunks": False}
        provider_secret = resolve_provider_secret(resolved_route.credential)

        try:
            ensure_provider_secret_available(resolved_route, provider_secret)
            yield from attempt_route(resolved_route, provider_secret, route_index, stream_state)
            with session_factory() as log_session:
                log_success(log_session, resolved_route, stream_state)
            return
        except HTTPException as exc:
            emitted_chunks = bool(stream_state.get("emitted_chunks"))
            if should_try_next_provider_route(
                exc,
                route_index=route_index,
                route_count=len(resolved_routes),
                emitted_chunks=emitted_chunks,
            ):
                with session_factory() as health_session:
                    record_provider_proxy_failure(
                        health_session,
                        provider_id=resolved_route.provider.id,
                        exc=exc,
                    )
                continue

            with session_factory() as log_session:
                record_provider_proxy_failure(
                    log_session,
                    provider_id=resolved_route.provider.id,
                    exc=exc,
                )
                log_final_error(log_session, resolved_route, exc, stream_state)
            for event in render_final_error(exc):
                yield event
            return


def execute_tracked_passthrough(
    request: Request,
    session: Session,
    *,
    endpoint: str,
    input_format: str,
    output_format: str,
    requested_model: str,
    request_payload: Any,
    resolved_route: ResolvedProviderRoute,
    call_upstream: Callable[[], T],
    started_at: float | None = None,
    build_response_payload: Callable[[T], Any] | None = None,
    extract_usage_snapshot: Callable[[T], UsageSnapshot | None] | None = None,
    extract_request_id: Callable[[T], str | None] | None = None,
    streamed: bool = False,
    ttfb_ms: int | None = None,
    completion_reason: str | None = None,
) -> T:
    started = started_at if started_at is not None else time.perf_counter()
    client_name = resolve_client_name(request)

    try:
        result = call_upstream()
        response_payload = build_response_payload(result) if build_response_payload else result
        usage_snapshot = extract_usage_snapshot(result) if extract_usage_snapshot else None
        request_id = extract_request_id(result) if extract_request_id else None
        duration_ms = max(0, round((time.perf_counter() - started) * 1000))
        log_tracked_proxy_request(
            session,
            input_format=input_format,
            output_format=output_format,
            endpoint=endpoint,
            client_name=client_name,
            resolved_route=resolved_route,
            requested_model=requested_model,
            duration_ms=duration_ms,
            status_code=200,
            streamed=streamed,
            request_payload=request_payload,
            response_payload=response_payload,
            usage_snapshot=usage_snapshot,
            request_id=request_id,
            ttfb_ms=ttfb_ms,
            completion_reason=completion_reason,
        )
        return result
    except HTTPException as exc:
        record_provider_proxy_failure(
            session,
            provider_id=resolved_route.provider.id,
            exc=exc,
        )
        duration_ms = max(0, round((time.perf_counter() - started) * 1000))
        log_tracked_proxy_request(
            session,
            input_format=input_format,
            output_format=output_format,
            endpoint=endpoint,
            client_name=client_name,
            resolved_route=resolved_route,
            requested_model=requested_model,
            duration_ms=duration_ms,
            status_code=exc.status_code,
            streamed=streamed,
            request_payload=request_payload,
            response_payload=build_logged_error_response(exc),
            error_message=format_exception_detail_for_log(exc.detail),
            request_id=None,
            ttfb_ms=ttfb_ms,
        )
        raise


def stream_tracked_passthrough(
    session_factory: sessionmaker[Session],
    request: Request,
    *,
    endpoint: str,
    input_format: str,
    output_format: str,
    requested_model: str,
    request_payload: Any,
    resolved_route: ResolvedProviderRoute,
    provider_secret: str | None,
    attempt_route: Callable[
        [ResolvedProviderRoute, str | None, dict[str, Any]],
        Generator[str, None, None],
    ],
    log_success: Callable[[Session, ResolvedProviderRoute, dict[str, Any]], None],
    log_final_error: Callable[[Session, ResolvedProviderRoute, HTTPException, dict[str, Any]], None],
    render_final_error: Callable[[HTTPException], list[str]],
    started_at: float | None = None,
) -> Generator[str, None, None]:
    yield from stream_tracked_proxy_routes(
        session_factory,
        [resolved_route],
        attempt_route=lambda route, secret, route_index, stream_state: attempt_route(
            route,
            secret,
            stream_state,
        ),
        log_success=log_success,
        log_final_error=log_final_error,
        render_final_error=render_final_error,
    )


__all__ = [
    "ModelPortProviderHeader",
    "MODELPORT_PROVIDER_HEADER",
    "bearer_scheme",
    "build_upstream_payload",
    "ensure_provider_secret_available",
    "execute_tracked_non_stream_proxy_routes",
    "execute_tracked_passthrough",
    "get_session",
    "log_tracked_proxy_request",
    "provider_supports_anonymous_access",
    "persist_provider_health_status",
    "classify_provider_failure_status",
    "record_provider_proxy_failure",
    "require_dashboard_token",
    "require_proxy_token",
    "resolve_client_name",
    "resolve_credential_secret",
    "resolve_first_proxy_route",
    "resolve_provider_secret",
    "get_known_provider_ids",
    "resolve_proxy_model_routing",
    "resolve_requested_provider",
    "should_try_next_provider_route",
    "stream_tracked_passthrough",
    "stream_tracked_proxy_routes",
]
