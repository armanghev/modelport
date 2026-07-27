from __future__ import annotations

from urllib.parse import urljoin

import httpx

from app.database import Provider
from app.errors.upstream import (
    http_exception_from_upstream_http_error,
    http_exception_from_upstream_transport_error,
)


def _url(provider: Provider, path: str) -> str:
    normalized_base = provider.base_url.rstrip("/") + "/"
    return urljoin(normalized_base, path)


def _auth_headers(api_key: str | None, *, stream: bool = False) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if stream:
        headers["Accept"] = "text/event-stream"
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _request_json(
    method: str,
    provider: Provider,
    api_key: str | None,
    path: str,
    *,
    timeout: float = 60.0,
    json: dict | None = None,
    params: dict | None = None,
) -> dict:
    try:
        with httpx.Client(timeout=timeout) as client:
            request_kwargs: dict = {"headers": _auth_headers(api_key)}
            if params is not None:
                request_kwargs["params"] = params
            if json is not None:
                request_kwargs["json"] = json
            response = getattr(client, method.lower())(_url(provider, path), **request_kwargs)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def _request_bytes(
    method: str,
    provider: Provider,
    api_key: str | None,
    path: str,
    *,
    timeout: float = 60.0,
    json: dict | None = None,
    default_content_type: str = "application/octet-stream",
) -> tuple[bytes, str]:
    try:
        with httpx.Client(timeout=timeout) as client:
            response = getattr(client, method.lower())(
                _url(provider, path),
                headers=_auth_headers(api_key),
                json=json,
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", default_content_type)
            return response.content, content_type
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def is_gemini_openai_provider(provider: Provider) -> bool:
    return "generativelanguage.googleapis.com" in provider.base_url


def extract_message_content(payload: dict) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""

    first_choice = choices[0] if isinstance(choices[0], dict) else {}
    message = first_choice.get("message") if isinstance(first_choice, dict) else {}
    if not isinstance(message, dict):
        return ""

    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                text_parts.append(item["text"])
        return "\n".join(text_parts)
    return ""


def should_retry_empty_gemini_completion(
    provider: Provider,
    request_payload: dict,
    response_payload: dict,
) -> bool:
    if not is_gemini_openai_provider(provider):
        return False

    max_tokens = request_payload.get("max_tokens")
    if not isinstance(max_tokens, int) or max_tokens >= 512:
        return False

    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return False

    first_choice = choices[0] if isinstance(choices[0], dict) else {}
    finish_reason = first_choice.get("finish_reason") if isinstance(first_choice, dict) else None
    usage = response_payload.get("usage") if isinstance(response_payload.get("usage"), dict) else {}
    completion_tokens = int(usage.get("completion_tokens", 0) or 0)
    content = extract_message_content(response_payload).strip()

    return finish_reason == "length" and completion_tokens == 0 and not content


def build_gemini_retry_payload(payload: dict) -> dict:
    retried_payload = dict(payload)
    retried_payload["max_tokens"] = 512
    return retried_payload


def post_chat_completion(
    client: httpx.Client,
    provider: Provider,
    headers: dict[str, str],
    payload: dict,
) -> dict:
    response = client.post(
        _url(provider, "chat/completions"),
        headers=headers,
        json=payload,
    )
    response.raise_for_status()
    return response.json()


def create_chat_completion(
    provider: Provider,
    api_key: str | None,
    payload: dict,
) -> dict:
    headers = _auth_headers(api_key)

    try:
        with httpx.Client(timeout=60.0) as client:
            response_payload = post_chat_completion(client, provider, headers, payload)
            if should_retry_empty_gemini_completion(provider, payload, response_payload):
                retry_payload = build_gemini_retry_payload(payload)
                response_payload = post_chat_completion(client, provider, headers, retry_payload)
            return response_payload
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def list_models(
    provider: Provider,
    api_key: str | None,
) -> dict:
    return _request_json("GET", provider, api_key, "models", timeout=30.0)


def get_model(
    provider: Provider,
    api_key: str | None,
    model_id: str,
) -> dict:
    return _request_json("GET", provider, api_key, f"models/{model_id}", timeout=30.0)


def create_embedding(
    provider: Provider,
    api_key: str | None,
    payload: dict,
) -> dict:
    return _request_json("POST", provider, api_key, "embeddings", json=payload)


def create_completion(
    provider: Provider,
    api_key: str | None,
    payload: dict,
) -> dict:
    return _request_json("POST", provider, api_key, "completions", json=payload)


def post_openai_multipart_json(
    provider: Provider,
    api_key: str | None,
    path: str,
    *,
    form_fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
) -> dict:
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                _url(provider, path),
                headers=headers,
                data=form_fields,
                files={
                    field_name: (filename, content, content_type)
                    for field_name, (filename, content, content_type) in files.items()
                },
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def create_image_generation(
    provider: Provider,
    api_key: str | None,
    payload: dict,
) -> dict:
    return _request_json("POST", provider, api_key, "images/generations", timeout=120.0, json=payload)


def create_image_edit(
    provider: Provider,
    api_key: str | None,
    *,
    form_fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
) -> dict:
    return post_openai_multipart_json(
        provider,
        api_key,
        "images/edits",
        form_fields=form_fields,
        files=files,
    )


def create_image_variation(
    provider: Provider,
    api_key: str | None,
    *,
    form_fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
) -> dict:
    return post_openai_multipart_json(
        provider,
        api_key,
        "images/variations",
        form_fields=form_fields,
        files=files,
    )


def create_audio_transcription(
    provider: Provider,
    api_key: str | None,
    *,
    form_fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
) -> dict:
    return post_openai_multipart_json(
        provider,
        api_key,
        "audio/transcriptions",
        form_fields=form_fields,
        files=files,
    )


def create_audio_translation(
    provider: Provider,
    api_key: str | None,
    *,
    form_fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
) -> dict:
    return post_openai_multipart_json(
        provider,
        api_key,
        "audio/translations",
        form_fields=form_fields,
        files=files,
    )


def create_audio_speech(
    provider: Provider,
    api_key: str | None,
    payload: dict,
) -> tuple[bytes, str]:
    return _request_bytes(
        "POST",
        provider,
        api_key,
        "audio/speech",
        timeout=120.0,
        json=payload,
        default_content_type="audio/mpeg",
    )


def create_moderation(
    provider: Provider,
    api_key: str | None,
    payload: dict,
) -> dict:
    return _request_json("POST", provider, api_key, "moderations", json=payload)


def create_response(
    provider: Provider,
    api_key: str | None,
    payload: dict,
) -> dict:
    return _request_json("POST", provider, api_key, "responses", json=payload)


def get_response(
    provider: Provider,
    api_key: str | None,
    response_id: str,
) -> dict:
    return _request_json("GET", provider, api_key, f"responses/{response_id}")


def list_response_input_items(
    provider: Provider,
    api_key: str | None,
    response_id: str,
    *,
    after: str | None = None,
    limit: int | None = None,
    order: str | None = None,
) -> dict:
    params: dict[str, str | int] = {}
    if after is not None:
        params["after"] = after
    if limit is not None:
        params["limit"] = limit
    if order is not None:
        params["order"] = order

    return _request_json(
        "GET",
        provider,
        api_key,
        f"responses/{response_id}/input_items",
        params=params or None,
    )


def cancel_response(
    provider: Provider,
    api_key: str | None,
    response_id: str,
) -> dict:
    return _request_json("POST", provider, api_key, f"responses/{response_id}/cancel")


def stream_response_events(
    provider: Provider,
    api_key: str | None,
    payload: dict,
):
    headers = _auth_headers(api_key, stream=True)

    try:
        with httpx.Client(timeout=60.0) as client:
            with client.stream(
                "POST",
                _url(provider, "responses"),
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if isinstance(line, bytes):
                        line = line.decode("utf-8")
                    yield f"{line}\n"
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except httpx.HTTPError as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def stream_completion_chunks(
    provider: Provider,
    api_key: str | None,
    payload: dict,
):
    headers = _auth_headers(api_key, stream=True)

    try:
        with httpx.Client(timeout=60.0) as client:
            with client.stream(
                "POST",
                _url(provider, "completions"),
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    if isinstance(line, bytes):
                        line = line.decode("utf-8")
                    if not line.startswith("data:"):
                        continue
                    yield line.removeprefix("data:").strip()
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except httpx.HTTPError as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def stream_chat_completion_chunks(
    provider: Provider,
    api_key: str | None,
    payload: dict,
):
    headers = _auth_headers(api_key, stream=True)

    try:
        with httpx.Client(timeout=60.0) as client:
            with client.stream(
                "POST",
                _url(provider, "chat/completions"),
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    if isinstance(line, bytes):
                        line = line.decode("utf-8")
                    if not line.startswith("data:"):
                        continue
                    yield line.removeprefix("data:").strip()
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except httpx.HTTPError as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc
