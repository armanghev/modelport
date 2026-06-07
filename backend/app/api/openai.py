from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, sessionmaker

from app.api.proxy_common import (
    EncryptionConfigurationError,
    ModelPortProviderHeader,
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
from app.providers.anthropic_compatible import (
    create_message as create_anthropic_message,
    get_model as get_anthropic_model,
    list_models as list_anthropic_models,
    stream_message_events as stream_anthropic_message_events,
)
from app.providers.openai_compatible import (
    cancel_response,
    create_chat_completion,
    create_embedding,
    create_response,
    get_model,
    get_response,
    list_models,
    list_response_input_items,
    stream_chat_completion_chunks,
    stream_response_events,
)
from app.responses.store import (
    PROXY_EMULATED,
    build_input_items_from_create_payload,
    cancel_emulated_response,
    get_response_resource,
    list_input_items,
    retrieve_emulated_response,
    save_emulated_response,
    save_passthrough_response,
)
from app.routing.provider_router import resolve_provider_routes
from app.schemas.openai import (
    OpenAIChatCompletionCreate,
    OpenAIChatCompletionResponse,
    OpenAIEmbeddingCreate,
    OpenAIResponse,
    OpenAIResponseCreate,
)
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


def resolve_stored_response_route(
    session: Session,
    response_id: str,
) -> tuple:
    resource = get_response_resource(session, response_id)
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Response resource '{response_id}' was not found.",
        )

    resolved_route = resolve_provider_routes(
        session,
        provider_id=resource.provider_id,
        requested_model=resource.requested_model,
        upstream_model=resource.upstream_model,
        fallback_provider_ids=[],
    )[0]
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

    return resource, resolved_route, provider_secret


def build_anthropic_upstream_payload(
    payload,
    *,
    upstream_model: str,
) -> dict:
    upstream_payload = payload.model_dump(
        exclude={"provider", "fallback_providers"},
        exclude_none=True,
    )
    upstream_payload["model"] = upstream_model
    return upstream_payload


def build_openai_upstream_payload(
    payload: OpenAIChatCompletionCreate,
    *,
    upstream_model: str,
) -> dict:
    upstream_payload = payload.model_dump(
        exclude={"provider", "fallback_providers"},
        exclude_none=True,
    )
    upstream_payload["model"] = upstream_model
    return upstream_payload


@router.get("/v1/models")
def get_models(
    request: Request,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> dict:
    resolved_route = resolve_provider_routes(
        session,
        provider_id=resolve_requested_provider(request, None),
        requested_model="",
        fallback_provider_ids=[],
    )[0]
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
    resolved_route = resolve_provider_routes(
        session,
        provider_id=resolve_requested_provider(request, None),
        requested_model=model,
        upstream_model=model,
        fallback_provider_ids=[],
    )[0]
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
    model_routing = resolve_proxy_model_routing(
        request,
        provider_id=payload.provider,
        requested_model=payload.model,
        known_provider_ids=get_known_provider_ids(session),
    )
    resolved_route = resolve_provider_routes(
        session,
        provider_id=model_routing.provider_id,
        requested_model=payload.model,
        upstream_model=model_routing.upstream_model,
        fallback_provider_ids=payload.fallback_providers,
    )[0]
    try:
        provider_secret = resolve_credential_secret(resolved_route.credential)
    except EncryptionConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    if resolved_route.provider.provider_type == "anthropic_compatible":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Selected provider does not support OpenAI embeddings compatibility.",
        )

    if not provider_supports_anonymous_access(
        resolved_route.provider.base_url,
        resolved_route.provider.provider_type,
    ) and not provider_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No configured credential available for the selected provider.",
        )

    upstream_payload = payload.model_dump(
        exclude={"provider", "fallback_providers"},
        exclude_none=True,
    )
    upstream_payload["model"] = resolved_route.upstream_model
    return create_embedding(
        resolved_route.provider,
        api_key=provider_secret,
        payload=upstream_payload,
    )


@router.post("/v1/responses", response_model=OpenAIResponse)
def create_responses(
    request: Request,
    payload: OpenAIResponseCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> OpenAIResponse | StreamingResponse:
    model_routing = resolve_proxy_model_routing(
        request,
        provider_id=payload.provider,
        requested_model=payload.model,
        known_provider_ids=get_known_provider_ids(session),
    )
    resolved_route = resolve_provider_routes(
        session,
        provider_id=model_routing.provider_id,
        requested_model=payload.model,
        upstream_model=model_routing.upstream_model,
        fallback_provider_ids=payload.fallback_providers,
    )[0]
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

    if payload.stream:
        if resolved_route.provider.provider_type == "anthropic_compatible":
            anthropic_payload = translate_openai_response_create_to_anthropic(payload)
            upstream_payload = build_anthropic_upstream_payload(
                anthropic_payload,
                upstream_model=resolved_route.upstream_model,
            )
            upstream_payload["stream"] = True
            input_items = build_input_items_from_create_payload(payload)

            def anthropic_response_stream():
                stream_state: dict[str, object] = {}
                for line in stream_anthropic_message_events(
                    resolved_route.provider,
                    api_key=provider_secret,
                    payload=upstream_payload,
                ):
                    for sse_event in translate_anthropic_stream_line_to_openai_response_sse(
                        line,
                        state=stream_state,
                        requested_model=payload.model,
                    ):
                        yield sse_event

                final_response = stream_state.get("final_response")
                if isinstance(final_response, dict):
                    openai_response = OpenAIResponse.model_validate(final_response)
                    save_emulated_response(
                        session,
                        response_id=openai_response.id,
                        provider_id=resolved_route.provider.id,
                        requested_model=payload.model,
                        upstream_model=resolved_route.upstream_model,
                        response_body=openai_response.model_dump(),
                        input_items=input_items,
                        status=openai_response.status,
                    )
                    session.commit()

            return StreamingResponse(
                anthropic_response_stream(),
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

        def openai_response_stream():
            for line in stream_response_events(
                resolved_route.provider,
                api_key=provider_secret,
                payload=upstream_payload,
            ):
                yield line

        return StreamingResponse(
            openai_response_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    if resolved_route.provider.provider_type == "anthropic_compatible":
        anthropic_payload = translate_openai_response_create_to_anthropic(payload)
        upstream_payload = build_anthropic_upstream_payload(
            anthropic_payload,
            upstream_model=resolved_route.upstream_model,
        )
        upstream_response = create_anthropic_message(
            resolved_route.provider,
            api_key=provider_secret,
            payload=upstream_payload,
        )
        response_dict = translate_anthropic_message_to_openai_response(
            upstream_response,
            requested_model=payload.model,
        )
        openai_response = OpenAIResponse.model_validate(response_dict)
        save_emulated_response(
            session,
            response_id=openai_response.id,
            provider_id=resolved_route.provider.id,
            requested_model=payload.model,
            upstream_model=resolved_route.upstream_model,
            response_body=openai_response.model_dump(),
            input_items=build_input_items_from_create_payload(payload),
            status=openai_response.status,
        )
        session.commit()
        return openai_response

    upstream_payload = payload.model_dump(
        exclude={"provider", "fallback_providers"},
        exclude_defaults=True,
        exclude_none=True,
    )
    upstream_payload.pop("stream", None)
    upstream_payload["model"] = resolved_route.upstream_model
    response_dict = create_response(
        resolved_route.provider,
        api_key=provider_secret,
        payload=upstream_payload,
    )
    openai_response = OpenAIResponse.model_validate(response_dict)
    save_passthrough_response(
        session,
        response_id=openai_response.id,
        provider_id=resolved_route.provider.id,
        requested_model=payload.model,
        upstream_model=resolved_route.upstream_model,
        status=openai_response.status,
    )
    session.commit()
    return openai_response


@router.get("/v1/responses/{response_id}", response_model=OpenAIResponse)
def retrieve_response(
    response_id: str,
    request: Request,
    session: Session = Depends(get_session),
    _: None = Depends(require_proxy_token),
    _modelport_provider: ModelPortProviderHeader = None,
) -> OpenAIResponse:
    resource, resolved_route, provider_secret = resolve_stored_response_route(session, response_id)

    if resource.storage_kind == PROXY_EMULATED:
        response_dict = retrieve_emulated_response(session, response_id)
        if response_dict is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Response resource '{response_id}' was not found.",
            )
        return OpenAIResponse.model_validate(response_dict)

    if resolved_route.provider.provider_type == "anthropic_compatible":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Selected provider does not support OpenAI responses lifecycle compatibility.",
        )

    return OpenAIResponse.model_validate(
        get_response(
            resolved_route.provider,
            api_key=provider_secret,
            response_id=response_id,
        )
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

    if resource.storage_kind == PROXY_EMULATED:
        input_items = list_input_items(session, response_id)
        if input_items is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Response resource '{response_id}' was not found.",
            )
        return input_items

    if resolved_route.provider.provider_type == "anthropic_compatible":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Selected provider does not support OpenAI responses lifecycle compatibility.",
        )

    return list_response_input_items(
        resolved_route.provider,
        api_key=provider_secret,
        response_id=response_id,
        after=after,
        limit=limit,
        order=order,
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

    if resource.storage_kind == PROXY_EMULATED:
        try:
            response_dict = cancel_emulated_response(session, response_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Response resource '{response_id}' was not found.",
            ) from exc
        session.commit()
        return OpenAIResponse.model_validate(response_dict)

    if resolved_route.provider.provider_type == "anthropic_compatible":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Selected provider does not support OpenAI responses lifecycle compatibility.",
        )

    return OpenAIResponse.model_validate(
        cancel_response(
            resolved_route.provider,
            api_key=provider_secret,
            response_id=response_id,
        )
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

    if payload.stream:

        def event_stream():
            for route_index, resolved_route in enumerate(resolved_routes):
                openai_payload = build_openai_upstream_payload(
                    payload,
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
                    if not provider_supports_anonymous_access(
                        resolved_route.provider.base_url,
                        resolved_route.provider.provider_type,
                    ) and not provider_secret:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="No configured credential available for the selected provider.",
                        )

                    if resolved_route.provider.provider_type == "anthropic_compatible":
                        anthropic_payload = build_anthropic_upstream_payload(
                            internal_payload,
                            upstream_model=resolved_route.upstream_model,
                        )
                        stream_state: dict[str, object] = {
                            "id": None,
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                        }
                        for line in stream_anthropic_message_events(
                            resolved_route.provider,
                            api_key=provider_secret,
                            payload=anthropic_payload,
                        ):
                            emitted_chunks = True
                            if ttfb_ms is None:
                                ttfb_ms = max(0, round((time.perf_counter() - started_at) * 1000))
                            for chunk in translate_anthropic_stream_event_to_openai_chunks(
                                line,
                                state=stream_state,
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
                        usage_snapshot = UsageSnapshot(
                            input_tokens=int(stream_state.get("prompt_tokens", 0) or 0),
                            output_tokens=int(stream_state.get("completion_tokens", 0) or 0),
                            total_tokens=int(stream_state.get("prompt_tokens", 0) or 0)
                            + int(stream_state.get("completion_tokens", 0) or 0),
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

        if resolved_route.provider.provider_type == "anthropic_compatible":
            anthropic_payload = build_anthropic_upstream_payload(
                internal_payload,
                upstream_model=resolved_route.upstream_model,
            )
            try:
                upstream_response = create_anthropic_message(
                    resolved_route.provider,
                    api_key=provider_secret,
                    payload=anthropic_payload,
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

            openai_response = translate_anthropic_message_to_openai_chat_completion(
                upstream_response,
                requested_model=payload.model,
            )
            usage = openai_response.get("usage") if isinstance(openai_response.get("usage"), dict) else {}
            usage_snapshot = UsageSnapshot(
                input_tokens=int(usage.get("prompt_tokens", 0) or 0),
                output_tokens=int(usage.get("completion_tokens", 0) or 0),
                total_tokens=int(usage.get("total_tokens", 0) or 0),
                token_source="provider",
            )
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
            completion_reason = extract_openai_stream_completion_reason(openai_response)
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
                request_id=str(openai_response.get("id")) if openai_response.get("id") else None,
                completion_reason=completion_reason,
                **io_log_kwargs(
                    session,
                    request_payload=payload,
                    response_payload=openai_response,
                ),
            )
            return OpenAIChatCompletionResponse.model_validate(openai_response)

        openai_payload = build_openai_upstream_payload(
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
