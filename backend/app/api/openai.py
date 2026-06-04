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
    get_known_provider_ids,
    resolve_proxy_model_routing,
    resolve_requested_provider,
)
from app.errors.upstream import build_logged_error_response, format_exception_detail_for_log
from app.providers.openai_compatible import create_chat_completion, list_models, stream_chat_completion_chunks
from app.routing.provider_router import resolve_provider_routes
from app.schemas.openai import OpenAIChatCompletionCreate, OpenAIChatCompletionResponse
from app.tracking.cost_service import calculate_estimated_cost_usd
from app.tracking.io_logging import io_log_kwargs
from app.tracking.log_service import create_api_request_log
from app.tracking.pricing import find_pricing_override
from app.tracking.usage_service import (
    UsageSnapshot,
    build_stream_usage_snapshot,
    extract_usage_snapshot,
)
from app.translators.anthropic_to_openai import translate_anthropic_message_to_openai
from app.translators.openai_request_to_anthropic import (
    translate_openai_chat_completion_request_to_anthropic,
)

router = APIRouter(tags=["openai"])


@router.get("/v1/models")
def get_models(
    request: Request,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
) -> dict:
    resolved_route = resolve_provider_routes(
        session,
        provider_id=resolve_requested_provider(request, None),
        requested_model="",
        fallback_provider_ids=[],
    )[0]
    if resolved_route.provider.provider_type == "anthropic_compatible":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Anthropic-compatible upstream providers are not implemented yet.",
        )

    try:
        provider_secret = resolve_credential_secret(resolved_route.credential)
    except EncryptionConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    if not provider_supports_anonymous_access(
        resolved_route.provider.base_url,
        resolved_route.provider.provider_type,
    ) and not provider_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No configured credential available for the selected provider.",
        )

    return list_models(resolved_route.provider, api_key=provider_secret)


def extract_openai_stream_delta_text(chunk: dict) -> str:
    choices = chunk.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first_choice = choices[0] if isinstance(choices[0], dict) else {}
    delta = first_choice.get("delta") if isinstance(first_choice, dict) else {}
    if not isinstance(delta, dict):
        return ""
    content = delta.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                text_parts.append(item["text"])
        return "\n".join(text_parts)
    return ""


def extract_openai_stream_completion_reason(chunk: dict) -> str | None:
    choices = chunk.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first_choice = choices[0] if isinstance(choices[0], dict) else {}
    finish_reason = first_choice.get("finish_reason") if isinstance(first_choice, dict) else None
    return str(finish_reason) if finish_reason else None


@router.post("/v1/chat/completions", response_model=OpenAIChatCompletionResponse)
def create_chat_completions(
    request: Request,
    payload: OpenAIChatCompletionCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
) -> OpenAIChatCompletionResponse | StreamingResponse:
    started_at = time.perf_counter()
    internal_payload = translate_openai_chat_completion_request_to_anthropic(payload)
    model_routing = resolve_proxy_model_routing(
        request,
        provider_id=payload.provider,
        requested_model=payload.model,
        known_provider_ids=get_known_provider_ids(session),
    )
    resolved_routes = resolve_provider_routes(
        session,
        provider_id=model_routing.provider_id,
        requested_model=payload.model,
        upstream_model=model_routing.upstream_model,
        fallback_provider_ids=payload.fallback_providers,
    )
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    client_name = resolve_client_name(request)

    if payload.stream:

        def event_stream():
            for route_index, resolved_route in enumerate(resolved_routes):
                openai_payload = translate_anthropic_message_to_openai(
                    internal_payload,
                    upstream_model=resolved_route.upstream_model,
                )
                ttfb_ms: int | None = None
                upstream_request_id: str | None = None
                final_usage: dict | None = None
                completion_reason: str | None = None
                text_parts: list[str] = []
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

                        if ttfb_ms is None:
                            ttfb_ms = max(0, round((time.perf_counter() - started_at) * 1000))

                        try:
                            chunk = json.loads(raw_chunk)
                        except ValueError:
                            emitted_chunks = True
                            yield f"data: {raw_chunk}\n\n"
                            continue

                        emitted_chunks = True
                        if chunk.get("id"):
                            upstream_request_id = str(chunk["id"])
                        if isinstance(chunk.get("usage"), dict):
                            final_usage = chunk["usage"]
                        delta_text = extract_openai_stream_delta_text(chunk)
                        if delta_text:
                            text_parts.append(delta_text)
                        completion_reason = extract_openai_stream_completion_reason(chunk) or completion_reason

                        yield f"data: {json.dumps(chunk, separators=(',', ':'))}\n\n"

                    yield "data: [DONE]\n\n"

                    usage_snapshot = build_stream_usage_snapshot(
                        openai_payload,
                        "".join(text_parts),
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
                            input_format="openai",
                            output_format="openai",
                            endpoint="/v1/chat/completions",
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
                            completion_reason=completion_reason,
                            **io_log_kwargs(
                                log_session,
                                request_payload=payload,
                                response_payload={
                                    "streamed": True,
                                    "id": upstream_request_id,
                                    "model": resolved_route.upstream_model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "message": {
                                                "role": "assistant",
                                                "content": "".join(text_parts),
                                            },
                                            "finish_reason": completion_reason,
                                        }
                                    ],
                                    "usage": final_usage,
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
                                error_message=format_exception_detail_for_log(exc.detail),
                            )
                        continue

                    duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
                    with session_factory() as log_session:
                        persist_provider_health_status(
                            log_session,
                            provider_id=resolved_route.provider.id,
                            status_value=classify_provider_failure_status(exc),
                            error_message=format_exception_detail_for_log(exc.detail),
                        )
                        create_api_request_log(
                            log_session,
                            input_format="openai",
                            output_format="openai",
                            endpoint="/v1/chat/completions",
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
                            error_message=format_exception_detail_for_log(exc.detail),
                            streamed=True,
                            request_id=upstream_request_id,
                            ttfb_ms=ttfb_ms,
                            **io_log_kwargs(
                                log_session,
                                request_payload=payload,
                                response_payload=build_logged_error_response(exc),
                            ),
                        )
                    error_payload = build_logged_error_response(exc)
                    yield f"data: {json.dumps(error_payload, separators=(',', ':'))}\n\n"
                    yield "data: [DONE]\n\n"
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
                    error_message=format_exception_detail_for_log(exc.detail),
                )
                last_error = exc
                continue
            raise exc

        openai_payload = translate_anthropic_message_to_openai(
            internal_payload,
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
                error_message=format_exception_detail_for_log(exc.detail),
            )
            last_error = exc
            if exc.status_code in (502, 503) and route_index < len(resolved_routes) - 1:
                continue

            duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
            create_api_request_log(
                session,
                input_format="openai",
                output_format="openai",
                endpoint="/v1/chat/completions",
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
                error_message=format_exception_detail_for_log(exc.detail),
                streamed=False,
                request_id=None,
                **io_log_kwargs(
                    session,
                    request_payload=payload,
                    response_payload=build_logged_error_response(exc),
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
        completion_reason = extract_openai_stream_completion_reason(upstream_response)
        create_api_request_log(
            session,
            input_format="openai",
            output_format="openai",
            endpoint="/v1/chat/completions",
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
            completion_reason=completion_reason,
            **io_log_kwargs(
                session,
                request_payload=payload,
                response_payload=upstream_response,
            ),
        )
        return OpenAIChatCompletionResponse.model_validate(upstream_response)

    if last_error is not None:
        raise last_error
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="No provider could satisfy the request.",
    )
