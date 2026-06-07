from __future__ import annotations

from urllib.parse import urljoin

import httpx

from app.database import Provider
from app.errors.upstream import (
    http_exception_from_upstream_http_error,
    http_exception_from_upstream_transport_error,
)


def build_chat_completions_url(provider: Provider) -> str:
    normalized_base = provider.base_url.rstrip("/") + "/"
    return urljoin(normalized_base, "chat/completions")


def build_models_url(provider: Provider) -> str:
    normalized_base = provider.base_url.rstrip("/") + "/"
    return urljoin(normalized_base, "models")


def build_model_url(provider: Provider, model_id: str) -> str:
    normalized_base = provider.base_url.rstrip("/") + "/"
    return urljoin(normalized_base, f"models/{model_id}")


def build_embeddings_url(provider: Provider) -> str:
    normalized_base = provider.base_url.rstrip("/") + "/"
    return urljoin(normalized_base, "embeddings")


def build_responses_url(provider: Provider) -> str:
    normalized_base = provider.base_url.rstrip("/") + "/"
    return urljoin(normalized_base, "responses")


def build_response_url(provider: Provider, response_id: str) -> str:
    normalized_base = provider.base_url.rstrip("/") + "/"
    return urljoin(normalized_base, f"responses/{response_id}")


def build_response_input_items_url(provider: Provider, response_id: str) -> str:
    normalized_base = provider.base_url.rstrip("/") + "/"
    return urljoin(normalized_base, f"responses/{response_id}/input_items")


def build_response_cancel_url(provider: Provider, response_id: str) -> str:
    normalized_base = provider.base_url.rstrip("/") + "/"
    return urljoin(normalized_base, f"responses/{response_id}/cancel")


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
        build_chat_completions_url(provider),
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
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

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
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(build_models_url(provider), headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def get_model(
    provider: Provider,
    api_key: str | None,
    model_id: str,
) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(build_model_url(provider, model_id), headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def create_embedding(
    provider: Provider,
    api_key: str | None,
    payload: dict,
) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                build_embeddings_url(provider),
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def create_response(
    provider: Provider,
    api_key: str | None,
    payload: dict,
) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                build_responses_url(provider),
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def get_response(
    provider: Provider,
    api_key: str | None,
    response_id: str,
) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.get(
                build_response_url(provider, response_id),
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def list_response_input_items(
    provider: Provider,
    api_key: str | None,
    response_id: str,
    *,
    after: str | None = None,
    limit: int | None = None,
    order: str | None = None,
) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    params: dict[str, str | int] = {}
    if after is not None:
        params["after"] = after
    if limit is not None:
        params["limit"] = limit
    if order is not None:
        params["order"] = order

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.get(
                build_response_input_items_url(provider, response_id),
                headers=headers,
                params=params or None,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def cancel_response(
    provider: Provider,
    api_key: str | None,
    response_id: str,
) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                build_response_cancel_url(provider, response_id),
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def stream_response_events(
    provider: Provider,
    api_key: str | None,
    payload: dict,
):
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with httpx.Client(timeout=60.0) as client:
            with client.stream(
                "POST",
                build_responses_url(provider),
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


def stream_chat_completion_chunks(
    provider: Provider,
    api_key: str | None,
    payload: dict,
):
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with httpx.Client(timeout=60.0) as client:
            with client.stream(
                "POST",
                build_chat_completions_url(provider),
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
