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


FILES_API_BETA = "files-api-2025-04-14"


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


def build_files_headers(api_key: str | None) -> dict[str, str]:
    headers = {
        "anthropic-version": "2023-06-01",
        "anthropic-beta": FILES_API_BETA,
    }
    if api_key:
        headers["x-api-key"] = api_key
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
    files: bool = False,
) -> dict:
    headers = build_files_headers(api_key) if files else build_headers(api_key)
    try:
        with httpx.Client(timeout=timeout) as client:
            request_kwargs: dict = {"headers": headers}
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
    files: bool = False,
    default_content_type: str = "application/octet-stream",
) -> tuple[bytes, str]:
    headers = build_files_headers(api_key) if files else build_headers(api_key)
    try:
        with httpx.Client(timeout=timeout) as client:
            response = getattr(client, method.lower())(_url(provider, path), headers=headers)
            response.raise_for_status()
            content_type = response.headers.get("content-type", default_content_type)
            return response.content, content_type
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def create_message(
    provider: Provider,
    api_key: str | None,
    payload: dict,
) -> dict:
    return _request_json("POST", provider, api_key, "v1/messages", json=payload)


def list_models(
    provider: Provider,
    api_key: str | None,
) -> dict:
    return _request_json("GET", provider, api_key, "v1/models", timeout=30.0)


def get_model(
    provider: Provider,
    api_key: str | None,
    model_id: str,
) -> dict:
    return _request_json("GET", provider, api_key, f"v1/models/{model_id}", timeout=30.0)


def count_message_tokens(
    provider: Provider,
    api_key: str | None,
    payload: dict,
) -> dict:
    return _request_json("POST", provider, api_key, "v1/messages/count_tokens", json=payload)


def create_message_batch(
    provider: Provider,
    api_key: str | None,
    payload: dict,
) -> dict:
    return _request_json("POST", provider, api_key, "v1/messages/batches", json=payload)


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

    return _request_json(
        "GET",
        provider,
        api_key,
        "v1/messages/batches",
        params=params or None,
    )


def get_message_batch(
    provider: Provider,
    api_key: str | None,
    batch_id: str,
) -> dict:
    return _request_json("GET", provider, api_key, f"v1/messages/batches/{batch_id}")


def cancel_message_batch(
    provider: Provider,
    api_key: str | None,
    batch_id: str,
) -> dict:
    return _request_json("POST", provider, api_key, f"v1/messages/batches/{batch_id}/cancel")


def delete_message_batch(
    provider: Provider,
    api_key: str | None,
    batch_id: str,
) -> None:
    headers = build_headers(api_key)
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.delete(
                _url(provider, f"v1/messages/batches/{batch_id}"),
                headers=headers,
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
    return _request_bytes(
        "GET",
        provider,
        api_key,
        f"v1/messages/batches/{batch_id}/results",
        default_content_type="application/x-jsonlines",
    )


def create_file(
    provider: Provider,
    api_key: str | None,
    *,
    filename: str,
    content: bytes,
    content_type: str,
) -> dict:
    files = {"file": (filename, content, content_type)}
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                _url(provider, "v1/files"),
                headers=build_files_headers(api_key),
                files=files,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise http_exception_from_upstream_http_error(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise http_exception_from_upstream_transport_error(exc) from exc


def list_files(
    provider: Provider,
    api_key: str | None,
    *,
    after_id: str | None = None,
    before_id: str | None = None,
    limit: int | None = None,
    scope_id: str | None = None,
) -> dict:
    params: dict[str, str | int] = {}
    if after_id is not None:
        params["after_id"] = after_id
    if before_id is not None:
        params["before_id"] = before_id
    if limit is not None:
        params["limit"] = limit
    if scope_id is not None:
        params["scope_id"] = scope_id

    return _request_json(
        "GET",
        provider,
        api_key,
        "v1/files",
        params=params or None,
        files=True,
    )


def get_file(
    provider: Provider,
    api_key: str | None,
    file_id: str,
) -> dict:
    return _request_json("GET", provider, api_key, f"v1/files/{file_id}", files=True)


def get_file_content(
    provider: Provider,
    api_key: str | None,
    file_id: str,
) -> tuple[bytes, str]:
    return _request_bytes("GET", provider, api_key, f"v1/files/{file_id}/content", files=True)


def delete_file(
    provider: Provider,
    api_key: str | None,
    file_id: str,
) -> dict:
    return _request_json("DELETE", provider, api_key, f"v1/files/{file_id}", files=True)


def stream_message_events(
    provider: Provider,
    api_key: str | None,
    payload: dict,
):
    try:
        with httpx.Client(timeout=60.0) as client:
            with client.stream(
                "POST",
                _url(provider, "v1/messages"),
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
