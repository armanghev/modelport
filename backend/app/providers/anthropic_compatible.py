from __future__ import annotations

from urllib.parse import urljoin

import httpx

from app.database import Provider
from app.errors.upstream import (
    http_exception_from_upstream_http_error,
    http_exception_from_upstream_transport_error,
)


def build_messages_url(provider: Provider) -> str:
    normalized_base = provider.base_url.rstrip("/") + "/"
    return urljoin(normalized_base, "v1/messages")


def build_models_url(provider: Provider) -> str:
    normalized_base = provider.base_url.rstrip("/") + "/"
    return urljoin(normalized_base, "v1/models")


def build_model_url(provider: Provider, model_id: str) -> str:
    normalized_base = provider.base_url.rstrip("/") + "/"
    return urljoin(normalized_base, f"v1/models/{model_id}")


def build_message_count_tokens_url(provider: Provider) -> str:
    normalized_base = provider.base_url.rstrip("/") + "/"
    return urljoin(normalized_base, "v1/messages/count_tokens")


def build_message_batches_url(provider: Provider) -> str:
    normalized_base = provider.base_url.rstrip("/") + "/"
    return urljoin(normalized_base, "v1/messages/batches")


def build_message_batch_url(provider: Provider, batch_id: str) -> str:
    normalized_base = provider.base_url.rstrip("/") + "/"
    return urljoin(normalized_base, f"v1/messages/batches/{batch_id}")


def build_message_batch_cancel_url(provider: Provider, batch_id: str) -> str:
    normalized_base = provider.base_url.rstrip("/") + "/"
    return urljoin(normalized_base, f"v1/messages/batches/{batch_id}/cancel")


def build_message_batch_results_url(provider: Provider, batch_id: str) -> str:
    normalized_base = provider.base_url.rstrip("/") + "/"
    return urljoin(normalized_base, f"v1/messages/batches/{batch_id}/results")


def build_headers(api_key: str | None, *, stream: bool = False) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    if stream:
        headers["Accept"] = "text/event-stream"
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def create_message(
    provider: Provider,
    api_key: str | None,
    payload: dict,
) -> dict:
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                build_messages_url(provider),
                headers=build_headers(api_key),
                json=payload,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def list_models(
    provider: Provider,
    api_key: str | None,
) -> dict:
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                build_models_url(provider),
                headers=build_headers(api_key),
            )
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
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                build_model_url(provider, model_id),
                headers=build_headers(api_key),
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def count_message_tokens(
    provider: Provider,
    api_key: str | None,
    payload: dict,
) -> dict:
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                build_message_count_tokens_url(provider),
                headers=build_headers(api_key),
                json=payload,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def create_message_batch(
    provider: Provider,
    api_key: str | None,
    payload: dict,
) -> dict:
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                build_message_batches_url(provider),
                headers=build_headers(api_key),
                json=payload,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def list_message_batches(
    provider: Provider,
    api_key: str | None,
    *,
    after_id: str | None = None,
    before_id: str | None = None,
    limit: int | None = None,
) -> dict:
    params: dict[str, str | int] = {}
    if after_id is not None:
        params["after_id"] = after_id
    if before_id is not None:
        params["before_id"] = before_id
    if limit is not None:
        params["limit"] = limit

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.get(
                build_message_batches_url(provider),
                headers=build_headers(api_key),
                params=params or None,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def get_message_batch(
    provider: Provider,
    api_key: str | None,
    batch_id: str,
) -> dict:
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.get(
                build_message_batch_url(provider, batch_id),
                headers=build_headers(api_key),
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def cancel_message_batch(
    provider: Provider,
    api_key: str | None,
    batch_id: str,
) -> dict:
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                build_message_batch_cancel_url(provider, batch_id),
                headers=build_headers(api_key),
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def delete_message_batch(
    provider: Provider,
    api_key: str | None,
    batch_id: str,
) -> None:
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.delete(
                build_message_batch_url(provider, batch_id),
                headers=build_headers(api_key),
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def get_message_batch_results(
    provider: Provider,
    api_key: str | None,
    batch_id: str,
) -> tuple[bytes, str]:
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.get(
                build_message_batch_results_url(provider, batch_id),
                headers=build_headers(api_key),
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "application/x-jsonlines")
            return response.content, content_type
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def stream_message_events(
    provider: Provider,
    api_key: str | None,
    payload: dict,
):
    try:
        with httpx.Client(timeout=60.0) as client:
            with client.stream(
                "POST",
                build_messages_url(provider),
                headers=build_headers(api_key, stream=True),
                json=payload,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    if isinstance(line, bytes):
                        line = line.decode("utf-8")
                    yield line
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc
