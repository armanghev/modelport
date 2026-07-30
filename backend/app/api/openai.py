from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response, StreamingResponse
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
    stream_tracked_passthrough,
    stream_tracked_proxy_routes,
)
from app.errors.upstream import build_logged_error_response, format_exception_detail_for_log, format_exception_detail_for_log
from app.providers.anthropic_compatible import (
    create_message as create_anthropic_message,
    get_model as get_anthropic_model,
    list_models as list_anthropic_models,
    stream_message_events as stream_anthropic_message_events,
)
from app.providers.openai_compatible import (
    cancel_response,
    create_audio_speech,
    create_audio_transcription,
    create_audio_translation,
    create_chat_completion,
    create_completion,
    create_embedding,
    create_image_edit,
    create_image_generation,
    create_image_variation,
    create_moderation,
    create_response,
    get_model,
    get_response,
    list_models,
    list_response_input_items,
    stream_chat_completion_chunks,
    stream_completion_chunks,
    stream_response_events,
)
from app.responses.store import (
    PROXY_EMULATED,
    build_input_items_from_create_payload,
    cancel_emulated_response,
    get_active_response_resource,
    get_response_resource,
    ingest_passthrough_response_stream_line,
    list_input_items,
    retrieve_emulated_response,
    save_emulated_response,
    save_passthrough_response,
)
from app.routing.provider_router import resolve_provider_routes
from app.schemas.openai import (
    OpenAIAudioSpeechCreate,
    OpenAIChatCompletionCreate,
    OpenAIChatCompletionResponse,
    OpenAIEmbeddingCreate,
    OpenAIImageGenerationCreate,
    OpenAILegacyCompletionCreate,
    OpenAIModerationCreate,
    OpenAIResponse,
    OpenAIResponseCreate,
)
from app.tracking.usage_service import (
    UsageSnapshot,
    build_stream_usage_snapshot,
    extract_usage_snapshot,
    normalize_anthropic_shaped_usage,
    normalize_openai_shaped_usage,
)
from app.translators.anthropic_to_openai import translate_anthropic_message_to_openai
from app.translators.models import translate_anthropic_model_to_openai, translate_anthropic_models_to_openai
from app.translators.openai_request_to_anthropic import (
    translate_openai_chat_completion_request_to_anthropic,
    translate_openai_response_create_to_anthropic,
)
from app.translators.openai_to_anthropic import (
    translate_anthropic_message_to_openai_response,
    translate_anthropic_message_to_openai_chat_completion,
    translate_anthropic_stream_event_to_openai_chunks,
    translate_anthropic_stream_line_to_openai_response_sse,
)

router = APIRouter(tags=["proxy"])

PROXY_MULTIPART_FIELDS = frozenset({"provider", "fallback_providers"})


def ensure_openai_compatible_provider(resolved_route, *, detail: str) -> None:
    if resolved_route.provider.provider_type == "anthropic_compatible":
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=detail)


async def parse_openai_multipart_passthrough(
    request: Request,
) -> tuple[str | None, str, dict[str, str], dict[str, tuple[str, bytes, str]]]:
    form = await request.form()
    provider_value = form.get("provider")
    provider_id = (
        provider_value.strip().lower()
        if isinstance(provider_value, str) and provider_value.strip()
        else None
    )

    model_value = form.get("model")
    if not isinstance(model_value, str) or not model_value.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="model form field is required.",
        )
    requested_model = model_value.strip()

    form_fields: dict[str, str] = {}
    files: dict[str, tuple[str, bytes, str]] = {}
    for key, value in form.multi_items():
        if key in PROXY_MULTIPART_FIELDS:
            continue
        if hasattr(value, "read"):
            content = await value.read()
            filename = value.filename or "upload.bin"
            content_type = value.content_type or "application/octet-stream"
            files[key] = (filename, content, content_type)
        elif isinstance(value, str):
            form_fields[key] = value

    return provider_id, requested_model, form_fields, files


def _resolve_openai_passthrough_route(
    request: Request,
    session: Session,
    *,
    provider_id: str | None,
    requested_model: str,
    fallback_provider_ids: list[str] | None = None,
    use_model_routing: bool = True,
):
    if use_model_routing:
        model_routing = resolve_proxy_model_routing(
            request,
            provider_id=provider_id,
            requested_model=requested_model,
            known_provider_ids=get_known_provider_ids(session),
        )
        return resolve_first_proxy_route(
            session,
            provider_id=model_routing.provider_id,
            requested_model=requested_model,
            upstream_model=model_routing.upstream_model,
            fallback_provider_ids=fallback_provider_ids,
        )

    resolved_provider_id = resolve_requested_provider(request, provider_id)
    return resolve_first_proxy_route(
        session,
        provider_id=resolved_provider_id,
        requested_model=requested_model,
        upstream_model=requested_model,
        fallback_provider_ids=fallback_provider_ids,
    )


def _prepare_openai_json_upstream_payload(
    payload,
    *,
    upstream_model: str,
    exclude_defaults: bool = False,
    set_upstream_model: bool = True,
) -> dict[str, Any]:
    dump_kwargs: dict[str, Any] = {
        "exclude": {"provider", "fallback_providers"},
        "exclude_none": True,
    }
    if exclude_defaults:
        dump_kwargs["exclude_defaults"] = True
    upstream_payload = payload.model_dump(**dump_kwargs)
    if set_upstream_model:
        upstream_payload["model"] = upstream_model
    return upstream_payload


def _proxy_openai_json_passthrough(
    request: Request,
    session: Session,
    payload,
    *,
    endpoint: str,
    capability_detail: str,
    provider_call: Callable[..., Any],
    require_secret: bool = False,
    exclude_defaults: bool = False,
    use_model_routing: bool = True,
    set_upstream_model: bool = True,
    requested_model: str | None = None,
    usage_from_response: bool = False,
    build_response_payload: Callable[[Any], Any] | None = None,
    extract_request_id: Callable[[Any], str | None] | None = None,
) -> Any:
    resolved_model = requested_model if requested_model is not None else payload.model
    resolved_route, provider_secret = _resolve_openai_passthrough_route(
        request,
        session,
        provider_id=payload.provider,
        requested_model=resolved_model,
        fallback_provider_ids=payload.fallback_providers,
        use_model_routing=use_model_routing,
    )
    ensure_openai_compatible_provider(resolved_route, detail=capability_detail)
    if require_secret:
        ensure_provider_secret_available(resolved_route, provider_secret)
    upstream_payload = _prepare_openai_json_upstream_payload(
        payload,
        upstream_model=resolved_route.upstream_model,
        exclude_defaults=exclude_defaults,
        set_upstream_model=set_upstream_model,
    )

    def call_upstream() -> Any:
        return provider_call(
            resolved_route.provider,
            api_key=provider_secret,
            payload=upstream_payload,
        )

    extract_usage = None
    if usage_from_response:
        def extract_usage(result: Any) -> UsageSnapshot | None:
            if isinstance(result, dict):
                return extract_usage_snapshot(upstream_payload, result)
            return None

    default_extract_request_id = None
    if extract_request_id is None:
        def default_extract_request_id(result: Any) -> str | None:
            if isinstance(result, dict) and result.get("id"):
                return str(result["id"])
            return None

    return execute_tracked_passthrough(
        request,
        session,
        endpoint=endpoint,
        input_format="openai",
        output_format="openai",
        requested_model=resolved_model,
        request_payload=payload,
        resolved_route=resolved_route,
        call_upstream=call_upstream,
        build_response_payload=build_response_payload,
        extract_usage_snapshot=extract_usage,
        extract_request_id=extract_request_id or default_extract_request_id,
    )


async def _proxy_openai_multipart_passthrough(
    request: Request,
    session: Session,
    *,
    endpoint: str,
    capability_detail: str,
    provider_call: Callable[..., Any],
) -> Any:
    provider_id, requested_model, form_fields, files = await parse_openai_multipart_passthrough(request)
    resolved_route, provider_secret = _resolve_openai_passthrough_route(
        request,
        session,
        provider_id=provider_id,
        requested_model=requested_model,
        fallback_provider_ids=[],
    )
    ensure_openai_compatible_provider(resolved_route, detail=capability_detail)
    ensure_provider_secret_available(resolved_route, provider_secret)
    form_fields["model"] = resolved_route.upstream_model
    request_payload = {
        "model": requested_model,
        "form_fields": form_fields,
        "files": list(files.keys()),
    }

    def call_upstream() -> Any:
        return provider_call(
            resolved_route.provider,
            api_key=provider_secret,
            form_fields=form_fields,
            files=files,
        )

    def default_extract_request_id(result: Any) -> str | None:
        if isinstance(result, dict) and result.get("id"):
            return str(result["id"])
        return None

    return execute_tracked_passthrough(
        request,
        session,
        endpoint=endpoint,
        input_format="openai",
        output_format="openai",
        requested_model=requested_model,
        request_payload=request_payload,
        resolved_route=resolved_route,
        call_upstream=call_upstream,
        extract_request_id=default_extract_request_id,
    )


def resolve_stored_response_route(
    session: Session,
    response_id: str,
) -> tuple:
    resource = get_active_response_resource(session, response_id)
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Response resource '{response_id}' was not found or has expired.",
        )

    resolved_route, provider_secret = resolve_first_proxy_route(
        session,
        provider_id=resource.provider_id,
        requested_model=resource.requested_model,
        upstream_model=resource.upstream_model,
        fallback_provider_ids=[],
    )

    return resource, resolved_route, provider_secret


@router.get("/v1/models")
def get_models(
    request: Request,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> dict:
    resolved_route, provider_secret = resolve_first_proxy_route(
        session,
        provider_id=resolve_requested_provider(request, None),
        requested_model="",
        fallback_provider_ids=[],
    )
    if resolved_route.provider.provider_type == "anthropic_compatible":
        return translate_anthropic_models_to_openai(
            list_anthropic_models(resolved_route.provider, api_key=provider_secret)
        )

    return list_models(resolved_route.provider, api_key=provider_secret)


@router.get("/v1/models/{model}")
def get_model_by_id(
    model: str,
    request: Request,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> dict:
    resolved_route, provider_secret = resolve_first_proxy_route(
        session,
        provider_id=resolve_requested_provider(request, None),
        requested_model=model,
        upstream_model=model,
        fallback_provider_ids=[],
    )
    if resolved_route.provider.provider_type == "anthropic_compatible":
        return translate_anthropic_model_to_openai(
            get_anthropic_model(
                resolved_route.provider,
                api_key=provider_secret,
                model_id=resolved_route.upstream_model,
            )
        )

    return get_model(
        resolved_route.provider,
        api_key=provider_secret,
        model_id=resolved_route.upstream_model,
    )


@router.post("/v1/embeddings")
def create_embeddings(
    request: Request,
    payload: OpenAIEmbeddingCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> dict:
    return _proxy_openai_json_passthrough(
        request,
        session,
        payload,
        endpoint="/v1/embeddings",
        capability_detail="Selected provider does not support OpenAI embeddings compatibility.",
        provider_call=create_embedding,
        usage_from_response=True,
    )


@router.post("/v1/completions", response_model=None)
def create_completions(
    request: Request,
    payload: OpenAILegacyCompletionCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> dict | StreamingResponse:
    started_at = time.perf_counter()
    resolved_route, provider_secret = _resolve_openai_passthrough_route(
        request,
        session,
        provider_id=payload.provider,
        requested_model=payload.model,
        fallback_provider_ids=payload.fallback_providers,
    )
    ensure_openai_compatible_provider(
        resolved_route,
        detail="Selected provider does not support OpenAI legacy completions compatibility.",
    )
    upstream_payload = _prepare_openai_json_upstream_payload(
        payload,
        upstream_model=resolved_route.upstream_model,
        exclude_defaults=True,
    )
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    client_name = resolve_client_name(request)

    if payload.stream:
        def attempt_route(route, secret, stream_state):
            ttfb_ms: int | None = None
            upstream_request_id: str | None = None
            final_usage: dict | None = None
            completion_reason: str | None = None
            text_parts: list[str] = []

            for raw_chunk in stream_completion_chunks(
                route.provider,
                api_key=secret,
                payload=upstream_payload,
            ):
                if raw_chunk == "[DONE]":
                    yield "data: [DONE]\n\n"
                    continue

                if ttfb_ms is None:
                    ttfb_ms = max(0, round((time.perf_counter() - started_at) * 1000))

                try:
                    chunk = json.loads(raw_chunk)
                except ValueError:
                    stream_state["emitted_chunks"] = True
                    yield f"data: {raw_chunk}\n\n"
                    continue

                stream_state["emitted_chunks"] = True
                if chunk.get("id"):
                    upstream_request_id = str(chunk["id"])
                if isinstance(chunk.get("usage"), dict):
                    final_usage = chunk["usage"]
                choices = chunk.get("choices")
                if isinstance(choices, list) and choices:
                    first_choice = choices[0] if isinstance(choices[0], dict) else {}
                    text = first_choice.get("text")
                    if isinstance(text, str) and text:
                        text_parts.append(text)
                    finish_reason = first_choice.get("finish_reason")
                    if finish_reason:
                        completion_reason = str(finish_reason)

                yield f"data: {json.dumps(chunk, separators=(',', ':'))}\n\n"

            usage_snapshot = build_stream_usage_snapshot(
                upstream_payload,
                "".join(text_parts),
                final_usage,
            )
            stream_state.update(
                {
                    "ttfb_ms": ttfb_ms,
                    "upstream_request_id": upstream_request_id,
                    "final_usage": final_usage,
                    "completion_reason": completion_reason,
                    "text_parts": text_parts,
                    "usage_snapshot": usage_snapshot,
                }
            )

        def log_success(log_session, route, stream_state):
            duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
            log_tracked_proxy_request(
                log_session,
                input_format="openai",
                output_format="openai",
                endpoint="/v1/completions",
                client_name=client_name,
                resolved_route=route,
                requested_model=payload.model,
                duration_ms=duration_ms,
                status_code=200,
                streamed=True,
                request_payload=payload,
                response_payload={
                    "streamed": True,
                    "id": stream_state.get("upstream_request_id"),
                    "model": route.upstream_model,
                    "choices": [
                        {
                            "index": 0,
                            "text": "".join(stream_state.get("text_parts", [])),
                            "finish_reason": stream_state.get("completion_reason"),
                        }
                    ],
                    "usage": stream_state.get("final_usage"),
                },
                usage_snapshot=stream_state.get("usage_snapshot"),
                request_id=stream_state.get("upstream_request_id"),
                ttfb_ms=stream_state.get("ttfb_ms"),
                completion_reason=stream_state.get("completion_reason"),
            )

        def log_final_error(log_session, route, exc, stream_state):
            duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
            log_tracked_proxy_request(
                log_session,
                input_format="openai",
                output_format="openai",
                endpoint="/v1/completions",
                client_name=client_name,
                resolved_route=route,
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

        def render_final_error(exc):
            error_payload = build_logged_error_response(exc)
            return [
                f"data: {json.dumps(error_payload, separators=(',', ':'))}\n\n",
                "data: [DONE]\n\n",
            ]

        return StreamingResponse(
            stream_tracked_passthrough(
                session_factory,
                request,
                endpoint="/v1/completions",
                input_format="openai",
                output_format="openai",
                requested_model=payload.model,
                request_payload=payload,
                resolved_route=resolved_route,
                provider_secret=provider_secret,
                attempt_route=attempt_route,
                log_success=log_success,
                log_final_error=log_final_error,
                render_final_error=render_final_error,
                started_at=started_at,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    def call_upstream():
        return create_completion(
            resolved_route.provider,
            api_key=provider_secret,
            payload=upstream_payload,
        )

    return execute_tracked_passthrough(
        request,
        session,
        endpoint="/v1/completions",
        input_format="openai",
        output_format="openai",
        requested_model=payload.model,
        request_payload=payload,
        resolved_route=resolved_route,
        call_upstream=call_upstream,
        started_at=started_at,
        extract_usage_snapshot=lambda result: extract_usage_snapshot(upstream_payload, result)
        if isinstance(result, dict)
        else None,
        extract_request_id=lambda result: str(result["id"]) if isinstance(result, dict) and result.get("id") else None,
    )


@router.post("/v1/moderations")
def create_moderations(
    request: Request,
    payload: OpenAIModerationCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> dict:
    return _proxy_openai_json_passthrough(
        request,
        session,
        payload,
        endpoint="/v1/moderations",
        capability_detail="Selected provider does not support OpenAI moderations compatibility.",
        provider_call=create_moderation,
        use_model_routing=False,
        requested_model=payload.model or "",
        set_upstream_model=bool(payload.model),
    )


@router.post("/v1/images/generations")
def create_image_generations(
    request: Request,
    payload: OpenAIImageGenerationCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> dict:
    return _proxy_openai_json_passthrough(
        request,
        session,
        payload,
        endpoint="/v1/images/generations",
        capability_detail="Selected provider does not support OpenAI image generation compatibility.",
        provider_call=create_image_generation,
        require_secret=True,
        exclude_defaults=True,
    )


@router.post("/v1/images/edits")
async def create_image_edits(
    request: Request,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> dict:
    return await _proxy_openai_multipart_passthrough(
        request,
        session,
        endpoint="/v1/images/edits",
        capability_detail="Selected provider does not support OpenAI image edit compatibility.",
        provider_call=create_image_edit,
    )


@router.post("/v1/images/variations")
async def create_image_variations(
    request: Request,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> dict:
    return await _proxy_openai_multipart_passthrough(
        request,
        session,
        endpoint="/v1/images/variations",
        capability_detail="Selected provider does not support OpenAI image variation compatibility.",
        provider_call=create_image_variation,
    )


@router.post("/v1/audio/transcriptions")
async def create_audio_transcriptions(
    request: Request,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> dict:
    return await _proxy_openai_multipart_passthrough(
        request,
        session,
        endpoint="/v1/audio/transcriptions",
        capability_detail="Selected provider does not support OpenAI audio transcription compatibility.",
        provider_call=create_audio_transcription,
    )


@router.post("/v1/audio/translations")
async def create_audio_translations(
    request: Request,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> dict:
    return await _proxy_openai_multipart_passthrough(
        request,
        session,
        endpoint="/v1/audio/translations",
        capability_detail="Selected provider does not support OpenAI audio translation compatibility.",
        provider_call=create_audio_translation,
    )


@router.post("/v1/audio/speech")
def create_audio_speech_route(
    request: Request,
    payload: OpenAIAudioSpeechCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> Response:
    content, content_type = _proxy_openai_json_passthrough(
        request,
        session,
        payload,
        endpoint="/v1/audio/speech",
        capability_detail="Selected provider does not support OpenAI text-to-speech compatibility.",
        provider_call=create_audio_speech,
        require_secret=True,
        exclude_defaults=True,
        build_response_payload=lambda result: {
            "content_type": result[1],
            "content_length": len(result[0]),
        },
        extract_request_id=lambda _result: None,
    )
    return Response(content=content, media_type=content_type)


def extract_openai_response_usage(response_payload: dict) -> UsageSnapshot | None:
    usage = response_payload.get("usage")
    if not isinstance(usage, dict):
        return None
    snapshot = normalize_openai_shaped_usage(usage)
    if snapshot.input_tokens == 0 and snapshot.output_tokens == 0 and snapshot.total_tokens == 0:
        return None
    return snapshot


@router.post("/v1/responses", response_model=OpenAIResponse)
def create_responses(
    request: Request,
    payload: OpenAIResponseCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> OpenAIResponse | StreamingResponse:
    started_at = time.perf_counter()
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
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    client_name = resolve_client_name(request)

    if payload.stream:
        if resolved_route.provider.provider_type == "anthropic_compatible":
            anthropic_payload = translate_openai_response_create_to_anthropic(payload)
            upstream_payload = build_upstream_payload(
                anthropic_payload,
                upstream_model=resolved_route.upstream_model,
            )
            upstream_payload["stream"] = True
            input_items = build_input_items_from_create_payload(payload)

            def attempt_route(route, secret, stream_state):
                from app.api.anthropic import update_anthropic_stream_summary

                ttfb_ms: int | None = None
                upstream_request_id: str | None = None
                translator_state: dict[str, object] = {}
                anthropic_usage_summary: dict[str, object] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "text_parts": [],
                }

                for line in stream_anthropic_message_events(
                    route.provider,
                    api_key=secret,
                    payload=upstream_payload,
                ):
                    stream_state["emitted_chunks"] = True
                    if ttfb_ms is None:
                        ttfb_ms = max(0, round((time.perf_counter() - started_at) * 1000))
                    update_anthropic_stream_summary(line, summary=anthropic_usage_summary)
                    for sse_event in translate_anthropic_stream_line_to_openai_response_sse(
                        line,
                        state=translator_state,
                        requested_model=payload.model,
                    ):
                        yield sse_event

                final_response = translator_state.get("final_response")
                usage_snapshot: UsageSnapshot | None = None
                if isinstance(final_response, dict):
                    openai_response = OpenAIResponse.model_validate(final_response)
                    upstream_request_id = openai_response.id
                    save_emulated_response(
                        session,
                        response_id=openai_response.id,
                        provider_id=route.provider.slug,
                        requested_model=payload.model,
                        upstream_model=route.upstream_model,
                        response_body=openai_response.model_dump(),
                        input_items=input_items,
                        status=openai_response.status,
                    )
                    session.commit()
                    usage_raw = anthropic_usage_summary.get("usage")
                    if isinstance(usage_raw, dict):
                        if (
                            "output_tokens" not in usage_raw
                            and anthropic_usage_summary.get("output_tokens") is not None
                        ):
                            usage_raw = {
                                **usage_raw,
                                "output_tokens": int(anthropic_usage_summary["output_tokens"]),
                            }
                        usage_snapshot = normalize_anthropic_shaped_usage(usage_raw)
                    else:
                        usage_snapshot = extract_openai_response_usage(openai_response.model_dump())

                stream_state.update(
                    {
                        "ttfb_ms": ttfb_ms,
                        "upstream_request_id": upstream_request_id,
                        "usage_snapshot": usage_snapshot,
                        "final_response": final_response,
                    }
                )

            def log_success(log_session, route, stream_state):
                duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
                log_tracked_proxy_request(
                    log_session,
                    input_format="openai",
                    output_format="openai",
                    endpoint="/v1/responses",
                    client_name=client_name,
                    resolved_route=route,
                    requested_model=payload.model,
                    duration_ms=duration_ms,
                    status_code=200,
                    streamed=True,
                    request_payload=payload,
                    response_payload={
                        "streamed": True,
                        "id": stream_state.get("upstream_request_id"),
                        "model": payload.model,
                        "response": stream_state.get("final_response"),
                    },
                    usage_snapshot=stream_state.get("usage_snapshot"),
                    request_id=stream_state.get("upstream_request_id"),
                    ttfb_ms=stream_state.get("ttfb_ms"),
                )

            def log_final_error(log_session, route, exc, stream_state):
                duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
                log_tracked_proxy_request(
                    log_session,
                    input_format="openai",
                    output_format="openai",
                    endpoint="/v1/responses",
                    client_name=client_name,
                    resolved_route=route,
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

            def render_final_error(exc):
                logged_error = build_logged_error_response(exc)["error"]
                return [f"event: error\ndata: {json.dumps({'type': 'error', 'error': logged_error})}\n\n"]

            return StreamingResponse(
                stream_tracked_passthrough(
                    session_factory,
                    request,
                    endpoint="/v1/responses",
                    input_format="openai",
                    output_format="openai",
                    requested_model=payload.model,
                    request_payload=payload,
                    resolved_route=resolved_route,
                    provider_secret=provider_secret,
                    attempt_route=attempt_route,
                    log_success=log_success,
                    log_final_error=log_final_error,
                    render_final_error=render_final_error,
                    started_at=started_at,
                ),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        upstream_payload = payload.model_dump(
            exclude={"provider", "fallback_providers"},
            exclude_defaults=True,
            exclude_none=True,
        )
        upstream_payload["model"] = resolved_route.upstream_model
        upstream_payload["stream"] = True

        def attempt_route(route, secret, stream_state):
            ttfb_ms: int | None = None
            passthrough_state: dict[str, object] = {}
            for line in stream_response_events(
                route.provider,
                api_key=secret,
                payload=upstream_payload,
            ):
                stream_state["emitted_chunks"] = True
                if ttfb_ms is None:
                    ttfb_ms = max(0, round((time.perf_counter() - started_at) * 1000))
                ingest_passthrough_response_stream_line(line, passthrough_state)
                yield line

            response_id = passthrough_state.get("response_id")
            status_value = passthrough_state.get("status")
            final_response = passthrough_state.get("final_response")
            usage_snapshot: UsageSnapshot | None = None
            if isinstance(final_response, dict):
                usage_snapshot = extract_openai_response_usage(final_response)
            if isinstance(response_id, str) and isinstance(status_value, str):
                save_passthrough_response(
                    session,
                    response_id=response_id,
                    provider_id=route.provider.slug,
                    requested_model=payload.model,
                    upstream_model=route.upstream_model,
                    status=status_value,
                )
                session.commit()

            stream_state.update(
                {
                    "ttfb_ms": ttfb_ms,
                    "upstream_request_id": response_id if isinstance(response_id, str) else None,
                    "usage_snapshot": usage_snapshot,
                    "final_response": final_response,
                }
            )

        def log_success(log_session, route, stream_state):
            duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
            log_tracked_proxy_request(
                log_session,
                input_format="openai",
                output_format="openai",
                endpoint="/v1/responses",
                client_name=client_name,
                resolved_route=route,
                requested_model=payload.model,
                duration_ms=duration_ms,
                status_code=200,
                streamed=True,
                request_payload=payload,
                response_payload={
                    "streamed": True,
                    "id": stream_state.get("upstream_request_id"),
                    "model": payload.model,
                    "response": stream_state.get("final_response"),
                },
                usage_snapshot=stream_state.get("usage_snapshot"),
                request_id=stream_state.get("upstream_request_id"),
                ttfb_ms=stream_state.get("ttfb_ms"),
            )

        def log_final_error(log_session, route, exc, stream_state):
            duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
            log_tracked_proxy_request(
                log_session,
                input_format="openai",
                output_format="openai",
                endpoint="/v1/responses",
                client_name=client_name,
                resolved_route=route,
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

        def render_final_error(exc):
            logged_error = build_logged_error_response(exc)["error"]
            return [f"event: error\ndata: {json.dumps({'type': 'error', 'error': logged_error})}\n\n"]

        return StreamingResponse(
            stream_tracked_passthrough(
                session_factory,
                request,
                endpoint="/v1/responses",
                input_format="openai",
                output_format="openai",
                requested_model=payload.model,
                request_payload=payload,
                resolved_route=resolved_route,
                provider_secret=provider_secret,
                attempt_route=attempt_route,
                log_success=log_success,
                log_final_error=log_final_error,
                render_final_error=render_final_error,
                started_at=started_at,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    if resolved_route.provider.provider_type == "anthropic_compatible":
        anthropic_payload = translate_openai_response_create_to_anthropic(payload)
        upstream_payload = build_upstream_payload(
            anthropic_payload,
            upstream_model=resolved_route.upstream_model,
        )

        captured_usage: list[UsageSnapshot | None] = [None]

        def call_upstream():
            upstream_response = create_anthropic_message(
                resolved_route.provider,
                api_key=provider_secret,
                payload=upstream_payload,
            )
            raw_usage = upstream_response.get("usage") if isinstance(upstream_response, dict) else None
            if isinstance(raw_usage, dict):
                captured_usage[0] = normalize_anthropic_shaped_usage(raw_usage)
            response_dict = translate_anthropic_message_to_openai_response(
                upstream_response,
                requested_model=payload.model,
            )
            openai_response = OpenAIResponse.model_validate(response_dict)
            save_emulated_response(
                session,
                response_id=openai_response.id,
                provider_id=resolved_route.provider.slug,
                requested_model=payload.model,
                upstream_model=resolved_route.upstream_model,
                response_body=openai_response.model_dump(),
                input_items=build_input_items_from_create_payload(payload),
                status=openai_response.status,
            )
            session.commit()
            return openai_response

        openai_response = execute_tracked_passthrough(
            request,
            session,
            endpoint="/v1/responses",
            input_format="openai",
            output_format="openai",
            requested_model=payload.model,
            request_payload=payload,
            resolved_route=resolved_route,
            call_upstream=call_upstream,
            started_at=started_at,
            build_response_payload=lambda response: response.model_dump(),
            extract_usage_snapshot=lambda response: (
                captured_usage[0] or extract_openai_response_usage(response.model_dump())
            ),
            extract_request_id=lambda response: response.id,
        )
        return openai_response

    upstream_payload = payload.model_dump(
        exclude={"provider", "fallback_providers"},
        exclude_defaults=True,
        exclude_none=True,
    )
    upstream_payload.pop("stream", None)
    upstream_payload["model"] = resolved_route.upstream_model

    def call_upstream():
        response_dict = create_response(
            resolved_route.provider,
            api_key=provider_secret,
            payload=upstream_payload,
        )
        openai_response = OpenAIResponse.model_validate(response_dict)
        save_passthrough_response(
            session,
            response_id=openai_response.id,
            provider_id=resolved_route.provider.slug,
            requested_model=payload.model,
            upstream_model=resolved_route.upstream_model,
            status=openai_response.status,
        )
        session.commit()
        return openai_response

    return execute_tracked_passthrough(
        request,
        session,
        endpoint="/v1/responses",
        input_format="openai",
        output_format="openai",
        requested_model=payload.model,
        request_payload=payload,
        resolved_route=resolved_route,
        call_upstream=call_upstream,
        started_at=started_at,
        build_response_payload=lambda response: response.model_dump(),
        extract_usage_snapshot=lambda response: extract_openai_response_usage(response.model_dump()),
        extract_request_id=lambda response: response.id,
    )


@router.get("/v1/responses/{response_id}", response_model=OpenAIResponse)
def retrieve_response(
    response_id: str,
    request: Request,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> OpenAIResponse:
    resource, resolved_route, provider_secret = resolve_stored_response_route(session, response_id)
    request_payload = {"response_id": response_id}

    if resource.storage_kind == PROXY_EMULATED:
        def call_upstream():
            response_dict = retrieve_emulated_response(session, response_id)
            if response_dict is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Response resource '{response_id}' was not found.",
                )
            return OpenAIResponse.model_validate(response_dict)

        return execute_tracked_passthrough(
            request,
            session,
            endpoint="/v1/responses/{response_id}",
            input_format="openai",
            output_format="openai",
            requested_model=resource.requested_model,
            request_payload=request_payload,
            resolved_route=resolved_route,
            call_upstream=call_upstream,
            build_response_payload=lambda response: response.model_dump(),
            extract_request_id=lambda response: response.id,
        )

    if resolved_route.provider.provider_type == "anthropic_compatible":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Selected provider does not support OpenAI responses lifecycle compatibility.",
        )

    def call_upstream():
        return OpenAIResponse.model_validate(
            get_response(
                resolved_route.provider,
                api_key=provider_secret,
                response_id=response_id,
            )
        )

    return execute_tracked_passthrough(
        request,
        session,
        endpoint="/v1/responses/{response_id}",
        input_format="openai",
        output_format="openai",
        requested_model=resource.requested_model,
        request_payload=request_payload,
        resolved_route=resolved_route,
        call_upstream=call_upstream,
        build_response_payload=lambda response: response.model_dump(),
        extract_request_id=lambda response: response.id,
    )


@router.get("/v1/responses/{response_id}/input_items")
def retrieve_response_input_items(
    response_id: str,
    request: Request,
    after: str | None = None,
    limit: int | None = None,
    order: str | None = None,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> dict:
    resource, resolved_route, provider_secret = resolve_stored_response_route(session, response_id)
    request_payload = {
        "response_id": response_id,
        "after": after,
        "limit": limit,
        "order": order,
    }

    if resource.storage_kind == PROXY_EMULATED:
        def call_upstream():
            input_items = list_input_items(session, response_id)
            if input_items is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Response resource '{response_id}' was not found.",
                )
            return input_items

        return execute_tracked_passthrough(
            request,
            session,
            endpoint="/v1/responses/{response_id}/input_items",
            input_format="openai",
            output_format="openai",
            requested_model=resource.requested_model,
            request_payload=request_payload,
            resolved_route=resolved_route,
            call_upstream=call_upstream,
        )

    if resolved_route.provider.provider_type == "anthropic_compatible":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Selected provider does not support OpenAI responses lifecycle compatibility.",
        )

    def call_upstream():
        return list_response_input_items(
            resolved_route.provider,
            api_key=provider_secret,
            response_id=response_id,
            after=after,
            limit=limit,
            order=order,
        )

    return execute_tracked_passthrough(
        request,
        session,
        endpoint="/v1/responses/{response_id}/input_items",
        input_format="openai",
        output_format="openai",
        requested_model=resource.requested_model,
        request_payload=request_payload,
        resolved_route=resolved_route,
        call_upstream=call_upstream,
    )


@router.post("/v1/responses/{response_id}/cancel", response_model=OpenAIResponse)
def cancel_stored_response(
    response_id: str,
    request: Request,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> OpenAIResponse:
    resource, resolved_route, provider_secret = resolve_stored_response_route(session, response_id)
    request_payload = {"response_id": response_id}

    if resource.storage_kind == PROXY_EMULATED:
        def call_upstream():
            try:
                response_dict = cancel_emulated_response(session, response_id)
            except KeyError as exc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Response resource '{response_id}' was not found.",
                ) from exc
            session.commit()
            return OpenAIResponse.model_validate(response_dict)

        return execute_tracked_passthrough(
            request,
            session,
            endpoint="/v1/responses/{response_id}/cancel",
            input_format="openai",
            output_format="openai",
            requested_model=resource.requested_model,
            request_payload=request_payload,
            resolved_route=resolved_route,
            call_upstream=call_upstream,
            build_response_payload=lambda response: response.model_dump(),
            extract_request_id=lambda response: response.id,
        )

    if resolved_route.provider.provider_type == "anthropic_compatible":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Selected provider does not support OpenAI responses lifecycle compatibility.",
        )

    def call_upstream():
        return OpenAIResponse.model_validate(
            cancel_response(
                resolved_route.provider,
                api_key=provider_secret,
                response_id=response_id,
            )
        )

    return execute_tracked_passthrough(
        request,
        session,
        endpoint="/v1/responses/{response_id}/cancel",
        input_format="openai",
        output_format="openai",
        requested_model=resource.requested_model,
        request_payload=request_payload,
        resolved_route=resolved_route,
        call_upstream=call_upstream,
        build_response_payload=lambda response: response.model_dump(),
        extract_request_id=lambda response: response.id,
    )


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
    _modelport_provider: ModelPortProviderHeader = None,
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

    def stream_attempt_route(
        resolved_route,
        provider_secret,
        route_index,
        stream_state,
    ):
        openai_payload = build_upstream_payload(
            payload,
            upstream_model=resolved_route.upstream_model,
        )
        ttfb_ms: int | None = None
        upstream_request_id: str | None = None
        final_usage: dict | None = None
        completion_reason: str | None = None
        text_parts: list[str] = []

        if resolved_route.provider.provider_type == "anthropic_compatible":
            from app.api.anthropic import update_anthropic_stream_summary

            anthropic_payload = build_upstream_payload(
                internal_payload,
                upstream_model=resolved_route.upstream_model,
            )
            anthropic_stream_state: dict[str, object] = {
                "id": None,
                "prompt_tokens": 0,
                "completion_tokens": 0,
            }
            anthropic_usage_summary: dict[str, object] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "text_parts": [],
            }
            for line in stream_anthropic_message_events(
                resolved_route.provider,
                api_key=provider_secret,
                payload=anthropic_payload,
            ):
                stream_state["emitted_chunks"] = True
                if ttfb_ms is None:
                    ttfb_ms = max(0, round((time.perf_counter() - started_at) * 1000))
                update_anthropic_stream_summary(line, summary=anthropic_usage_summary)
                for chunk in translate_anthropic_stream_event_to_openai_chunks(
                    line,
                    state=anthropic_stream_state,
                    requested_model=payload.model,
                ):
                    if chunk.get("id"):
                        upstream_request_id = str(chunk["id"])
                    usage = chunk.get("usage")
                    if isinstance(usage, dict):
                        final_usage = usage
                    delta_text = extract_openai_stream_delta_text(chunk)
                    if delta_text:
                        text_parts.append(delta_text)
                    completion_reason = extract_openai_stream_completion_reason(chunk) or completion_reason
                    yield f"data: {json.dumps(chunk, separators=(',', ':'))}\n\n"
            yield "data: [DONE]\n\n"
            usage_raw = anthropic_usage_summary.get("usage")
            if isinstance(usage_raw, dict):
                if "output_tokens" not in usage_raw and anthropic_usage_summary.get("output_tokens") is not None:
                    usage_raw = {
                        **usage_raw,
                        "output_tokens": int(anthropic_usage_summary["output_tokens"]),
                    }
                usage_snapshot = normalize_anthropic_shaped_usage(usage_raw)
            else:
                input_tokens = int(anthropic_usage_summary.get("input_tokens", 0) or 0)
                output_tokens = int(anthropic_usage_summary.get("output_tokens", 0) or 0)
                usage_snapshot = UsageSnapshot.flat(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                    token_source="provider",
                )
        else:
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
                    stream_state["emitted_chunks"] = True
                    yield f"data: {raw_chunk}\n\n"
                    continue

                stream_state["emitted_chunks"] = True
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

        stream_state.update(
            {
                "ttfb_ms": ttfb_ms,
                "upstream_request_id": upstream_request_id,
                "final_usage": final_usage,
                "completion_reason": completion_reason,
                "text_parts": text_parts,
                "usage_snapshot": usage_snapshot,
            }
        )

    def stream_log_success(log_session, resolved_route, stream_state):
        duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
        log_tracked_proxy_request(
            log_session,
            input_format="openai",
            output_format="openai",
            endpoint="/v1/chat/completions",
            client_name=client_name,
            resolved_route=resolved_route,
            requested_model=payload.model,
            duration_ms=duration_ms,
            status_code=200,
            streamed=True,
            request_payload=payload,
            response_payload={
                "streamed": True,
                "id": stream_state.get("upstream_request_id"),
                "model": resolved_route.upstream_model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "".join(stream_state.get("text_parts", [])),
                        },
                        "finish_reason": stream_state.get("completion_reason"),
                    }
                ],
                "usage": stream_state.get("final_usage"),
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
            input_format="openai",
            output_format="openai",
            endpoint="/v1/chat/completions",
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
        error_payload = build_logged_error_response(exc)
        return [
            f"data: {json.dumps(error_payload, separators=(',', ':'))}\n\n",
            "data: [DONE]\n\n",
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
                internal_payload,
                upstream_model=resolved_route.upstream_model,
            )
            upstream_response = create_anthropic_message(
                resolved_route.provider,
                api_key=provider_secret,
                payload=anthropic_payload,
            )
            openai_response = translate_anthropic_message_to_openai_chat_completion(
                upstream_response,
                requested_model=payload.model,
            )
            raw_usage = upstream_response.get("usage")
            if isinstance(raw_usage, dict):
                usage_snapshot = normalize_anthropic_shaped_usage(raw_usage)
            else:
                usage = openai_response.get("usage") if isinstance(openai_response.get("usage"), dict) else {}
                usage_snapshot = UsageSnapshot.flat(
                    input_tokens=int(usage.get("prompt_tokens", 0) or 0),
                    output_tokens=int(usage.get("completion_tokens", 0) or 0),
                    total_tokens=int(usage.get("total_tokens", 0) or 0),
                    token_source="provider",
                )
            return openai_response, usage_snapshot

        openai_payload = build_upstream_payload(
            payload,
            upstream_model=resolved_route.upstream_model,
        )
        upstream_response = create_chat_completion(
            resolved_route.provider,
            api_key=provider_secret,
            payload=openai_payload,
        )
        usage_snapshot = extract_usage_snapshot(openai_payload, upstream_response)
        return upstream_response, usage_snapshot

    def log_success(log_session, resolved_route, result):
        response, usage_snapshot = result
        duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
        completion_reason = extract_openai_stream_completion_reason(response)
        log_tracked_proxy_request(
            log_session,
            input_format="openai",
            output_format="openai",
            endpoint="/v1/chat/completions",
            client_name=client_name,
            resolved_route=resolved_route,
            requested_model=payload.model,
            duration_ms=duration_ms,
            status_code=200,
            streamed=False,
            request_payload=payload,
            response_payload=response,
            usage_snapshot=usage_snapshot,
            request_id=str(response.get("id")) if response.get("id") else None,
            completion_reason=completion_reason,
        )
        return OpenAIChatCompletionResponse.model_validate(response)

    def log_final_error(log_session, resolved_route, exc):
        duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
        log_tracked_proxy_request(
            log_session,
            input_format="openai",
            output_format="openai",
            endpoint="/v1/chat/completions",
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
