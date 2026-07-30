from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.proxy_common import (
    ModelPortProviderHeader,
    build_upstream_payload,
    ensure_provider_secret_available,
    execute_tracked_non_stream_proxy_routes,
    execute_tracked_passthrough,
    get_session,
    log_tracked_proxy_request,
    require_proxy_token,
    resolve_client_name,
    resolve_first_proxy_route,
    get_known_provider_ids,
    resolve_proxy_model_routing,
    resolve_requested_provider,
    stream_tracked_proxy_routes,
)
from app.errors.upstream import build_logged_error_response, format_exception_detail_for_log
from app.database import ApiRequest
from app.pricing.calculator import RequestContext
from app.providers.anthropic_compatible import (
    cancel_message_batch,
    count_message_tokens,
    create_file,
    create_message as create_anthropic_message,
    create_message_batch,
    delete_file,
    delete_message_batch,
    get_file,
    get_file_content,
    get_message_batch,
    get_message_batch_results,
    list_files,
    list_message_batches,
    stream_message_events as stream_anthropic_message_events,
)
from app.providers.openai_compatible import create_chat_completion, stream_chat_completion_chunks
from app.routing.provider_router import resolve_provider_routes
from app.schemas.anthropic import (
    AnthropicMessageBatchCreate,
    AnthropicMessageCountTokensCreate,
    AnthropicMessageCountTokensResponse,
    AnthropicMessageCreate,
    AnthropicMessageResponse,
)
from app.tracking.usage_service import (
    UsageSnapshot,
    build_stream_usage_snapshot,
    estimate_request_tokens,
    extract_usage_snapshot,
    normalize_anthropic_shaped_usage,
)
from app.translators.anthropic_to_openai import translate_anthropic_message_to_openai
from app.translators.openai_to_anthropic import (
    AnthropicStreamTranslator,
    translate_openai_chat_completion_to_anthropic,
)

router = APIRouter(tags=["proxy"])


def resolve_anthropic_compatible_route(
    session: Session,
    request: Request,
    *,
    provider_id: str | None,
    fallback_provider_ids: list[str] | None = None,
) -> tuple:
    resolved_provider_id = resolve_requested_provider(request, provider_id)
    resolved_route, provider_secret = resolve_first_proxy_route(
        session,
        provider_id=resolved_provider_id,
        requested_model="",
        fallback_provider_ids=fallback_provider_ids or [],
    )
    if resolved_route.provider.provider_type != "anthropic_compatible":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Selected provider does not support this Anthropic-compatible route.",
        )

    return resolved_route, provider_secret


def _merge_anthropic_usage(target: dict[str, object], source: dict[str, object]) -> None:
    for key, value in source.items():
        if key == "cache_creation" and isinstance(value, dict):
            cache_creation = target.get("cache_creation")
            if isinstance(cache_creation, dict):
                cache_creation.update(value)
            else:
                target["cache_creation"] = dict(value)
        else:
            target[key] = value


def update_anthropic_stream_summary(
    line: str,
    *,
    summary: dict[str, object],
) -> None:
    if not line.startswith("data:"):
        return

    raw_payload = line.removeprefix("data:").strip()
    if not raw_payload:
        return

    try:
        payload = json.loads(raw_payload)
    except ValueError:
        return

    if not isinstance(payload, dict):
        return

    event_type = payload.get("type")
    if event_type == "message_start":
        message = payload.get("message")
        if isinstance(message, dict):
            message_id = message.get("id")
            if isinstance(message_id, str) and message_id:
                summary["request_id"] = message_id
            usage = message.get("usage")
            if isinstance(usage, dict):
                if not isinstance(summary.get("usage"), dict):
                    summary["usage"] = {}
                _merge_anthropic_usage(summary["usage"], usage)
    elif event_type == "content_block_delta":
        delta = payload.get("delta")
        if isinstance(delta, dict) and delta.get("type") == "text_delta":
            text = delta.get("text")
            if isinstance(text, str) and text:
                summary["text_parts"].append(text)
    elif event_type == "message_delta":
        delta = payload.get("delta")
        if isinstance(delta, dict):
            stop_reason = delta.get("stop_reason")
            if isinstance(stop_reason, str) and stop_reason:
                summary["stop_reason"] = stop_reason
        usage = payload.get("usage")
        if isinstance(usage, dict):
            if not isinstance(summary.get("usage"), dict):
                summary["usage"] = {}
            _merge_anthropic_usage(summary["usage"], usage)


@router.post("/v1/messages/count_tokens", response_model=AnthropicMessageCountTokensResponse)
def create_message_count_tokens(
    request: Request,
    payload: AnthropicMessageCountTokensCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> AnthropicMessageCountTokensResponse:
    model_routing = resolve_proxy_model_routing(
        request,
        provider_id=payload.provider,
        requested_model=payload.model,
        known_provider_ids=get_known_provider_ids(session),
    )
    resolved_route, provider_secret = resolve_first_proxy_route(
        session,
        provider_id=model_routing.provider_id,
        requested_model=payload.model,
        upstream_model=model_routing.upstream_model,
        fallback_provider_ids=payload.fallback_providers,
    )

    if resolved_route.provider.provider_type != "anthropic_compatible":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Selected provider does not support Anthropic token counting compatibility.",
        )

    upstream_payload = payload.model_dump(
        exclude={"provider", "fallback_providers"},
        exclude_none=True,
    )
    upstream_payload["model"] = resolved_route.upstream_model

    def call_upstream():
        return AnthropicMessageCountTokensResponse.model_validate(
            count_message_tokens(
                resolved_route.provider,
                api_key=provider_secret,
                payload=upstream_payload,
            )
        )

    return execute_tracked_passthrough(
        request,
        session,
        endpoint="/v1/messages/count_tokens",
        input_format="anthropic",
        output_format="anthropic",
        requested_model=payload.model,
        request_payload=payload,
        resolved_route=resolved_route,
        call_upstream=call_upstream,
        build_response_payload=lambda response: response.model_dump(),
    )


@router.post("/v1/messages/batches")
def create_message_batches(
    request: Request,
    payload: AnthropicMessageBatchCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> dict:
    resolved_route, provider_secret = resolve_anthropic_compatible_route(
        session,
        request,
        provider_id=payload.provider,
        fallback_provider_ids=payload.fallback_providers,
    )
    upstream_payload = payload.model_dump(
        exclude={"provider", "fallback_providers"},
        exclude_none=True,
    )

    def call_upstream():
        return create_message_batch(
            resolved_route.provider,
            api_key=provider_secret,
            payload=upstream_payload,
        )

    return execute_tracked_passthrough(
        request,
        session,
        endpoint="/v1/messages/batches",
        input_format="anthropic",
        output_format="anthropic",
        requested_model="",
        request_payload=payload,
        resolved_route=resolved_route,
        call_upstream=call_upstream,
        extract_request_id=lambda result: str(result["id"]) if isinstance(result, dict) and result.get("id") else None,
    )


@router.get("/v1/messages/batches")
def list_message_batches_route(
    request: Request,
    after_id: str | None = None,
    before_id: str | None = None,
    limit: int | None = None,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> dict:
    resolved_route, provider_secret = resolve_anthropic_compatible_route(
        session,
        request,
        provider_id=None,
    )
    def call_upstream():
        return list_message_batches(
            resolved_route.provider,
            api_key=provider_secret,
            after_id=after_id,
            before_id=before_id,
            limit=limit,
        )

    return execute_tracked_passthrough(
        request,
        session,
        endpoint="/v1/messages/batches",
        input_format="anthropic",
        output_format="anthropic",
        requested_model="",
        request_payload={
            "after_id": after_id,
            "before_id": before_id,
            "limit": limit,
        },
        resolved_route=resolved_route,
        call_upstream=call_upstream,
    )


@router.get("/v1/messages/batches/{message_batch_id}")
def retrieve_message_batch(
    message_batch_id: str,
    request: Request,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> dict:
    resolved_route, provider_secret = resolve_anthropic_compatible_route(
        session,
        request,
        provider_id=None,
    )
    def call_upstream():
        return get_message_batch(
            resolved_route.provider,
            api_key=provider_secret,
            batch_id=message_batch_id,
        )

    return execute_tracked_passthrough(
        request,
        session,
        endpoint="/v1/messages/batches/{message_batch_id}",
        input_format="anthropic",
        output_format="anthropic",
        requested_model="",
        request_payload={"message_batch_id": message_batch_id},
        resolved_route=resolved_route,
        call_upstream=call_upstream,
        extract_request_id=lambda result: str(result["id"]) if isinstance(result, dict) and result.get("id") else None,
    )


@router.post("/v1/messages/batches/{message_batch_id}/cancel")
def cancel_message_batch_route(
    message_batch_id: str,
    request: Request,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> dict:
    resolved_route, provider_secret = resolve_anthropic_compatible_route(
        session,
        request,
        provider_id=None,
    )
    def call_upstream():
        return cancel_message_batch(
            resolved_route.provider,
            api_key=provider_secret,
            batch_id=message_batch_id,
        )

    return execute_tracked_passthrough(
        request,
        session,
        endpoint="/v1/messages/batches/{message_batch_id}/cancel",
        input_format="anthropic",
        output_format="anthropic",
        requested_model="",
        request_payload={"message_batch_id": message_batch_id},
        resolved_route=resolved_route,
        call_upstream=call_upstream,
        extract_request_id=lambda result: str(result["id"]) if isinstance(result, dict) and result.get("id") else None,
    )


@router.delete("/v1/messages/batches/{message_batch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message_batch_route(
    message_batch_id: str,
    request: Request,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> None:
    resolved_route, provider_secret = resolve_anthropic_compatible_route(
        session,
        request,
        provider_id=None,
    )
    def call_upstream():
        delete_message_batch(
            resolved_route.provider,
            api_key=provider_secret,
            batch_id=message_batch_id,
        )
        return None

    execute_tracked_passthrough(
        request,
        session,
        endpoint="/v1/messages/batches/{message_batch_id}",
        input_format="anthropic",
        output_format="anthropic",
        requested_model="",
        request_payload={"message_batch_id": message_batch_id},
        resolved_route=resolved_route,
        call_upstream=call_upstream,
        build_response_payload=lambda _result: None,
    )


@router.get("/v1/messages/batches/{message_batch_id}/results")
def retrieve_message_batch_results(
    message_batch_id: str,
    request: Request,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> Response:
    resolved_route, provider_secret = resolve_anthropic_compatible_route(
        session,
        request,
        provider_id=None,
    )
    def call_upstream():
        content, content_type = get_message_batch_results(
            resolved_route.provider,
            api_key=provider_secret,
            batch_id=message_batch_id,
        )
        return content, content_type

    content, content_type = execute_tracked_passthrough(
        request,
        session,
        endpoint="/v1/messages/batches/{message_batch_id}/results",
        input_format="anthropic",
        output_format="anthropic",
        requested_model="",
        request_payload={"message_batch_id": message_batch_id},
        resolved_route=resolved_route,
        call_upstream=call_upstream,
        build_response_payload=lambda result: {
            "content_type": result[1],
            "content_length": len(result[0]),
        },
        extract_request_id=lambda _result: None,
    )
    for line in content.decode("utf-8").splitlines():
        try:
            item = json.loads(line)
            custom_id = item.get("custom_id")
            message = item.get("result", {}).get("message", {})
            usage = message.get("usage")
            model = message.get("model")
            if not isinstance(custom_id, str) or not isinstance(usage, dict) or not isinstance(model, str):
                continue
            request_id = f"batch:{message_batch_id}:{custom_id}"
            if session.scalar(select(ApiRequest.id).where(ApiRequest.request_id == request_id)):
                continue
            log_tracked_proxy_request(
                session,
                input_format="anthropic",
                output_format="anthropic",
                endpoint="/v1/messages/batches/{message_batch_id}/results/item",
                client_name=resolve_client_name(request),
                resolved_route=resolved_route,
                requested_model=model,
                duration_ms=0,
                status_code=200,
                streamed=False,
                request_payload={"message_batch_id": message_batch_id, "custom_id": custom_id},
                response_payload=item,
                usage_snapshot=normalize_anthropic_shaped_usage(usage),
                pricing_context=RequestContext(service_tier="batch"),
                request_id=request_id,
            )
        except (UnicodeDecodeError, ValueError, TypeError):
            continue
    return Response(content=content, media_type=content_type)


@router.post("/v1/files")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    provider: str | None = Form(None),
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> dict:
    resolved_route, provider_secret = resolve_anthropic_compatible_route(
        session,
        request,
        provider_id=provider,
    )
    content = await file.read()
    filename = file.filename or "upload.bin"
    content_type = file.content_type or "application/octet-stream"

    def call_upstream():
        return create_file(
            resolved_route.provider,
            api_key=provider_secret,
            filename=filename,
            content=content,
            content_type=content_type,
        )

    return execute_tracked_passthrough(
        request,
        session,
        endpoint="/v1/files",
        input_format="anthropic",
        output_format="anthropic",
        requested_model="",
        request_payload={"filename": filename, "content_type": content_type},
        resolved_route=resolved_route,
        call_upstream=call_upstream,
        extract_request_id=lambda result: str(result["id"]) if isinstance(result, dict) and result.get("id") else None,
    )


@router.get("/v1/files")
def list_files_route(
    request: Request,
    after_id: str | None = None,
    before_id: str | None = None,
    limit: int | None = None,
    scope_id: str | None = None,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> dict:
    resolved_route, provider_secret = resolve_anthropic_compatible_route(
        session,
        request,
        provider_id=None,
    )
    def call_upstream():
        return list_files(
            resolved_route.provider,
            api_key=provider_secret,
            after_id=after_id,
            before_id=before_id,
            limit=limit,
            scope_id=scope_id,
        )

    return execute_tracked_passthrough(
        request,
        session,
        endpoint="/v1/files",
        input_format="anthropic",
        output_format="anthropic",
        requested_model="",
        request_payload={
            "after_id": after_id,
            "before_id": before_id,
            "limit": limit,
            "scope_id": scope_id,
        },
        resolved_route=resolved_route,
        call_upstream=call_upstream,
    )


@router.get("/v1/files/{file_id}")
def retrieve_file(
    file_id: str,
    request: Request,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> dict:
    resolved_route, provider_secret = resolve_anthropic_compatible_route(
        session,
        request,
        provider_id=None,
    )
    def call_upstream():
        return get_file(
            resolved_route.provider,
            api_key=provider_secret,
            file_id=file_id,
        )

    return execute_tracked_passthrough(
        request,
        session,
        endpoint="/v1/files/{file_id}",
        input_format="anthropic",
        output_format="anthropic",
        requested_model="",
        request_payload={"file_id": file_id},
        resolved_route=resolved_route,
        call_upstream=call_upstream,
        extract_request_id=lambda result: str(result["id"]) if isinstance(result, dict) and result.get("id") else None,
    )


@router.get("/v1/files/{file_id}/content")
def retrieve_file_content(
    file_id: str,
    request: Request,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> Response:
    resolved_route, provider_secret = resolve_anthropic_compatible_route(
        session,
        request,
        provider_id=None,
    )
    def call_upstream():
        content, content_type = get_file_content(
            resolved_route.provider,
            api_key=provider_secret,
            file_id=file_id,
        )
        return content, content_type

    content, content_type = execute_tracked_passthrough(
        request,
        session,
        endpoint="/v1/files/{file_id}/content",
        input_format="anthropic",
        output_format="anthropic",
        requested_model="",
        request_payload={"file_id": file_id},
        resolved_route=resolved_route,
        call_upstream=call_upstream,
        build_response_payload=lambda result: {
            "content_type": result[1],
            "content_length": len(result[0]),
        },
        extract_request_id=lambda _result: None,
    )
    return Response(content=content, media_type=content_type)


@router.delete("/v1/files/{file_id}")
def delete_file_route(
    file_id: str,
    request: Request,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> dict:
    resolved_route, provider_secret = resolve_anthropic_compatible_route(
        session,
        request,
        provider_id=None,
    )
    def call_upstream():
        return delete_file(
            resolved_route.provider,
            api_key=provider_secret,
            file_id=file_id,
        )

    return execute_tracked_passthrough(
        request,
        session,
        endpoint="/v1/files/{file_id}",
        input_format="anthropic",
        output_format="anthropic",
        requested_model="",
        request_payload={"file_id": file_id},
        resolved_route=resolved_route,
        call_upstream=call_upstream,
        extract_request_id=lambda result: str(result["id"]) if isinstance(result, dict) and result.get("id") else None,
    )


@router.post("/v1/messages", response_model=AnthropicMessageResponse)
def create_message(
    request: Request,
    payload: AnthropicMessageCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> AnthropicMessageResponse | StreamingResponse:
    started_at = time.perf_counter()
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

    def stream_attempt_route(
        resolved_route,
        provider_secret,
        route_index,
        stream_state,
    ):
        ttfb_ms: int | None = None
        upstream_request_id: str | None = None
        final_usage: dict | None = None
        completion_reason: str | None = None
        streamed_text_parts: list[str] = []

        if resolved_route.provider.provider_type == "anthropic_compatible":
            anthropic_payload = build_upstream_payload(
                payload,
                upstream_model=resolved_route.upstream_model,
            )
            stream_summary: dict[str, object] = {
                "request_id": None,
                "usage": {},
                "stop_reason": None,
                "text_parts": streamed_text_parts,
            }
            for line in stream_anthropic_message_events(
                resolved_route.provider,
                api_key=provider_secret,
                payload=anthropic_payload,
            ):
                stream_state["emitted_chunks"] = True
                if ttfb_ms is None:
                    ttfb_ms = max(0, round((time.perf_counter() - started_at) * 1000))
                update_anthropic_stream_summary(line, summary=stream_summary)
                yield f"{line}\n"
                if line.startswith("data:"):
                    yield "\n"

            upstream_request_id = (
                str(stream_summary["request_id"])
                if isinstance(stream_summary.get("request_id"), str)
                else None
            )
            completion_reason = (
                str(stream_summary["stop_reason"])
                if isinstance(stream_summary.get("stop_reason"), str)
                else None
            )
            raw_usage = stream_summary.get("usage")
            if isinstance(raw_usage, dict) and raw_usage:
                usage_snapshot = normalize_anthropic_shaped_usage(raw_usage)
            else:
                usage_snapshot = UsageSnapshot.flat(
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    token_source="provider",
                )
        else:
            openai_payload = translate_anthropic_message_to_openai(
                payload,
                upstream_model=resolved_route.upstream_model,
            )
            translator = AnthropicStreamTranslator(
                requested_model=payload.model,
                input_tokens=estimate_request_tokens(openai_payload),
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

                stream_state["emitted_chunks"] = True
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

            completion_reason = translator.completion_reason
            streamed_text_parts.extend(translator.text_parts)
            usage_snapshot = build_stream_usage_snapshot(
                openai_payload,
                "".join(translator.text_parts),
                final_usage,
            )

        stream_state.update(
            {
                "ttfb_ms": ttfb_ms,
                "upstream_request_id": upstream_request_id,
                "completion_reason": completion_reason,
                "streamed_text_parts": streamed_text_parts,
                "usage_snapshot": usage_snapshot,
            }
        )

    def stream_log_success(log_session, resolved_route, stream_state):
        duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
        log_tracked_proxy_request(
            log_session,
            input_format="anthropic",
            output_format="anthropic",
            endpoint="/v1/messages",
            client_name=client_name,
            resolved_route=resolved_route,
            requested_model=payload.model,
            duration_ms=duration_ms,
            status_code=200,
            streamed=True,
            request_payload=payload,
            response_payload={
                "streamed": True,
                "model": payload.model,
                "content": [
                    {
                        "type": "text",
                        "text": "".join(stream_state.get("streamed_text_parts", [])),
                    }
                ],
                "stop_reason": stream_state.get("completion_reason"),
            },
            usage_snapshot=stream_state.get("usage_snapshot"),
            request_id=stream_state.get("upstream_request_id"),
            ttfb_ms=stream_state.get("ttfb_ms"),
            completion_reason=stream_state.get("completion_reason"),
        )

    def stream_log_final_error(log_session, resolved_route, exc, stream_state):
        duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
        log_tracked_proxy_request(
            log_session,
            input_format="anthropic",
            output_format="anthropic",
            endpoint="/v1/messages",
            client_name=client_name,
            resolved_route=resolved_route,
            requested_model=payload.model,
            duration_ms=duration_ms,
            status_code=exc.status_code,
            streamed=True,
            request_payload=payload,
            response_payload=build_logged_error_response(exc),
            error_message=format_exception_detail_for_log(exc.detail),
            request_id=stream_state.get("upstream_request_id"),
            ttfb_ms=stream_state.get("ttfb_ms"),
        )

    def stream_render_final_error(exc):
        logged_error = build_logged_error_response(exc)["error"]
        return [
            f"event: error\ndata: {json.dumps({'type': 'error', 'error': logged_error})}\n\n",
        ]

    if payload.stream:
        return StreamingResponse(
            stream_tracked_proxy_routes(
                session_factory,
                resolved_routes,
                attempt_route=stream_attempt_route,
                log_success=stream_log_success,
                log_final_error=stream_log_final_error,
                render_final_error=stream_render_final_error,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    def attempt_route(resolved_route, provider_secret, route_index):
        if resolved_route.provider.provider_type == "anthropic_compatible":
            anthropic_payload = build_upstream_payload(
                payload,
                upstream_model=resolved_route.upstream_model,
            )
            upstream_response = create_anthropic_message(
                resolved_route.provider,
                api_key=provider_secret,
                payload=anthropic_payload,
            )
            anthropic_response = AnthropicMessageResponse.model_validate(upstream_response)
            raw_usage = upstream_response.get("usage")
            if isinstance(raw_usage, dict):
                usage_snapshot = normalize_anthropic_shaped_usage(raw_usage)
            else:
                usage_snapshot = UsageSnapshot.flat(
                    input_tokens=anthropic_response.usage.input_tokens,
                    output_tokens=anthropic_response.usage.output_tokens,
                    total_tokens=anthropic_response.usage.input_tokens + anthropic_response.usage.output_tokens,
                    token_source="provider",
                )
            return anthropic_response, usage_snapshot

        openai_payload = translate_anthropic_message_to_openai(
            payload,
            upstream_model=resolved_route.upstream_model,
        )
        upstream_response = create_chat_completion(
            resolved_route.provider,
            api_key=provider_secret,
            payload=openai_payload,
        )
        usage_snapshot = extract_usage_snapshot(openai_payload, upstream_response)
        anthropic_response = translate_openai_chat_completion_to_anthropic(
            upstream_response,
            requested_model=payload.model,
        )
        return anthropic_response, usage_snapshot, upstream_response

    def log_success(log_session, resolved_route, result):
        if len(result) == 3:
            anthropic_response, usage_snapshot, upstream_response = result
            request_id = str(upstream_response.get("id")) if upstream_response.get("id") else None
        else:
            anthropic_response, usage_snapshot = result
            request_id = anthropic_response.id

        duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
        log_tracked_proxy_request(
            log_session,
            input_format="anthropic",
            output_format="anthropic",
            endpoint="/v1/messages",
            client_name=client_name,
            resolved_route=resolved_route,
            requested_model=payload.model,
            duration_ms=duration_ms,
            status_code=200,
            streamed=False,
            request_payload=payload,
            response_payload=anthropic_response,
            usage_snapshot=usage_snapshot,
            request_id=request_id,
        )
        return anthropic_response

    def log_final_error(log_session, resolved_route, exc):
        duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
        log_tracked_proxy_request(
            log_session,
            input_format="anthropic",
            output_format="anthropic",
            endpoint="/v1/messages",
            client_name=client_name,
            resolved_route=resolved_route,
            requested_model=payload.model,
            duration_ms=duration_ms,
            status_code=exc.status_code,
            streamed=False,
            request_payload=payload,
            response_payload=build_logged_error_response(exc),
            error_message=format_exception_detail_for_log(exc.detail),
        )

    return execute_tracked_non_stream_proxy_routes(
        session,
        resolved_routes,
        attempt_route=attempt_route,
        log_success=log_success,
        log_final_error=log_final_error,
    )
