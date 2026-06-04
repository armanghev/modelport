from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, sessionmaker

from app.api.proxy_common import (
    EncryptionConfigurationError,
    classify_provider_failure_status,
    get_session,
    persist_provider_health_status,
    provider_supports_anonymous_access,
    require_proxy_token,
    resolve_client_name,
    resolve_credential_secret,
    resolve_requested_provider,
)
from app.providers.openai_compatible import create_chat_completion, stream_chat_completion_chunks
from app.routing.provider_router import resolve_provider_routes
from app.schemas.anthropic import AnthropicMessageCreate, AnthropicMessageResponse
from app.tracking.cost_service import calculate_estimated_cost_usd
from app.tracking.io_logging import io_log_kwargs
from app.tracking.log_service import create_api_request_log
from app.tracking.pricing import find_pricing_override
from app.tracking.usage_service import (
    UsageSnapshot,
    build_stream_usage_snapshot,
    estimate_request_tokens,
    extract_usage_snapshot,
)
from app.translators.anthropic_to_openai import translate_anthropic_message_to_openai
from app.translators.openai_to_anthropic import (
    AnthropicStreamTranslator,
    translate_openai_chat_completion_to_anthropic,
)

router = APIRouter(tags=["anthropic"])


@router.post("/v1/messages", response_model=AnthropicMessageResponse)
def create_message(
    request: Request,
    payload: AnthropicMessageCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
) -> AnthropicMessageResponse | StreamingResponse:
    started_at = time.perf_counter()
    resolved_routes = resolve_provider_routes(
        session,
        provider_id=resolve_requested_provider(request, payload.provider),
        requested_model=payload.model,
        fallback_provider_ids=payload.fallback_providers,
    )
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    client_name = resolve_client_name(request)

    if payload.stream:

        def event_stream():
            for route_index, resolved_route in enumerate(resolved_routes):
                openai_payload = translate_anthropic_message_to_openai(
                    payload,
                    upstream_model=resolved_route.upstream_model,
                )
                translator = AnthropicStreamTranslator(
                    requested_model=payload.model,
                    input_tokens=estimate_request_tokens(openai_payload),
                )
                ttfb_ms: int | None = None
                upstream_request_id: str | None = None
                final_usage: dict | None = None
                emitted_chunks = False

                try:
                    provider_secret = resolve_credential_secret(resolved_route.credential)
                except EncryptionConfigurationError as exc:
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

                try:
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

                    for raw_chunk in stream_chat_completion_chunks(
                        resolved_route.provider,
                        api_key=provider_secret,
                        payload=openai_payload,
                    ):
                        if raw_chunk == "[DONE]":
                            continue

                        try:
                            chunk = json.loads(raw_chunk)
                        except ValueError:
                            continue

                        emitted_chunks = True
                        if ttfb_ms is None:
                            ttfb_ms = max(0, round((time.perf_counter() - started_at) * 1000))
                        if chunk.get("id"):
                            upstream_request_id = str(chunk["id"])
                        if isinstance(chunk.get("usage"), dict):
                            final_usage = chunk["usage"]

                        for event in translator.consume_chunk(chunk):
                            yield event

                    for event in translator.finish_events():
                        yield event

                    usage_snapshot = build_stream_usage_snapshot(
                        openai_payload,
                        "".join(translator.text_parts),
                        final_usage,
                    )
                    duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))

                    with session_factory() as log_session:
                        pricing_override = find_pricing_override(
                            log_session,
                            provider_id=resolved_route.provider.id,
                            model=resolved_route.upstream_model,
                        )
                        estimated_cost_usd, pricing_source = calculate_estimated_cost_usd(
                            pricing_override,
                            input_tokens=usage_snapshot.input_tokens,
                            output_tokens=usage_snapshot.output_tokens,
                        )
                        create_api_request_log(
                            log_session,
                            input_format="anthropic",
                            output_format="anthropic",
                            endpoint="/v1/messages",
                            client_name=client_name,
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
                            streamed=True,
                            request_id=upstream_request_id,
                            ttfb_ms=ttfb_ms,
                            completion_reason=translator.completion_reason,
                            **io_log_kwargs(
                                log_session,
                                request_payload=payload,
                                response_payload={
                                    "streamed": True,
                                    "model": payload.model,
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": "".join(translator.text_parts),
                                        }
                                    ],
                                    "stop_reason": translator.completion_reason,
                                },
                            ),
                        )
                    return
                except HTTPException as exc:
                    if not emitted_chunks and exc.status_code in (502, 503) and route_index < len(resolved_routes) - 1:
                        with session_factory() as health_session:
                            persist_provider_health_status(
                                health_session,
                                provider_id=resolved_route.provider.id,
                                status_value=classify_provider_failure_status(exc),
                                error_message=str(exc.detail),
                            )
                        continue

                    duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
                    with session_factory() as log_session:
                        persist_provider_health_status(
                            log_session,
                            provider_id=resolved_route.provider.id,
                            status_value=classify_provider_failure_status(exc),
                            error_message=str(exc.detail),
                        )
                        create_api_request_log(
                            log_session,
                            input_format="anthropic",
                            output_format="anthropic",
                            endpoint="/v1/messages",
                            client_name=client_name,
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
                            streamed=True,
                            request_id=upstream_request_id,
                            ttfb_ms=ttfb_ms,
                            **io_log_kwargs(
                                log_session,
                                request_payload=payload,
                                response_payload={
                                    "error": {
                                        "message": str(exc.detail),
                                        "status_code": exc.status_code,
                                    }
                                },
                            ),
                        )
                    yield f"event: error\ndata: {json.dumps({'type': 'error', 'error': {'type': 'api_error', 'message': str(exc.detail)}})}\n\n"
                    return

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    last_error: HTTPException | None = None
    for route_index, resolved_route in enumerate(resolved_routes):
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
            exc = HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No configured credential available for the selected provider.",
            )
            if route_index < len(resolved_routes) - 1:
                persist_provider_health_status(
                    session,
                    provider_id=resolved_route.provider.id,
                    status_value=classify_provider_failure_status(exc),
                    error_message=str(exc.detail),
                )
                last_error = exc
                continue
            raise exc

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
            persist_provider_health_status(
                session,
                provider_id=resolved_route.provider.id,
                status_value=classify_provider_failure_status(exc),
                error_message=str(exc.detail),
            )
            last_error = exc
            if exc.status_code in (502, 503) and route_index < len(resolved_routes) - 1:
                continue

            duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
            create_api_request_log(
                session,
                input_format="anthropic",
                output_format="anthropic",
                endpoint="/v1/messages",
                client_name=client_name,
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
                streamed=False,
                request_id=None,
                **io_log_kwargs(
                    session,
                    request_payload=payload,
                    response_payload={
                        "error": {
                            "message": str(exc.detail),
                            "status_code": exc.status_code,
                        }
                    },
                ),
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
        anthropic_response = translate_openai_chat_completion_to_anthropic(
            upstream_response,
            requested_model=payload.model,
        )
        create_api_request_log(
            session,
            input_format="anthropic",
            output_format="anthropic",
            endpoint="/v1/messages",
            client_name=client_name,
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
            streamed=False,
            request_id=str(upstream_response.get("id")) if upstream_response.get("id") else None,
            **io_log_kwargs(
                session,
                request_payload=payload,
                response_payload=anthropic_response,
            ),
        )
        return anthropic_response

    if last_error is not None:
        raise last_error
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="No provider could satisfy the request.",
    )
