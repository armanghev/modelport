from __future__ import annotations

from collections.abc import Iterable

import httpx
import pytest
from fastapi import HTTPException

from app.database import Provider
from app.providers.anthropic_compatible import (
    FILES_API_BETA,
    _url,
    build_files_headers,
    build_headers,
    cancel_message_batch,
    count_message_tokens,
    create_file,
    create_message,
    create_message_batch,
    get_model,
    list_models,
    stream_message_events,
)


def make_anthropic_provider() -> Provider:
    return Provider(
        id="anthropic",
        display_name="Anthropic",
        provider_type="anthropic_compatible",
        base_url="https://api.anthropic.com",
        enabled=True,
    )


def test_build_urls_for_anthropic_upstream() -> None:
    provider = make_anthropic_provider()

    assert _url(provider, "v1/messages") == "https://api.anthropic.com/v1/messages"
    assert _url(provider, "v1/models") == "https://api.anthropic.com/v1/models"
    assert _url(provider, "v1/models/claude-sonnet-4-5-20250929") == "https://api.anthropic.com/v1/models/claude-sonnet-4-5-20250929"
    assert _url(provider, "v1/messages/count_tokens") == "https://api.anthropic.com/v1/messages/count_tokens"
    assert _url(provider, "v1/messages/batches") == "https://api.anthropic.com/v1/messages/batches"
    assert (
        _url(provider, "v1/messages/batches/msgbatch_123")
        == "https://api.anthropic.com/v1/messages/batches/msgbatch_123"
    )
    assert (
        _url(provider, "v1/messages/batches/msgbatch_123/cancel")
        == "https://api.anthropic.com/v1/messages/batches/msgbatch_123/cancel"
    )
    assert (
        _url(provider, "v1/messages/batches/msgbatch_123/results")
        == "https://api.anthropic.com/v1/messages/batches/msgbatch_123/results"
    )
    assert _url(provider, "v1/files") == "https://api.anthropic.com/v1/files"
    assert _url(provider, "v1/files/file_123") == "https://api.anthropic.com/v1/files/file_123"
    assert _url(provider, "v1/files/file_123/content") == "https://api.anthropic.com/v1/files/file_123/content"


def test_build_headers_for_anthropic_requests() -> None:
    assert build_headers(None) == {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    assert build_headers("sk-anthropic-seeded", stream=True) == {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
        "Accept": "text/event-stream",
        "x-api-key": "sk-anthropic-seeded",
    }
    assert build_files_headers("sk-anthropic-seeded") == {
        "anthropic-version": "2023-06-01",
        "anthropic-beta": FILES_API_BETA,
        "x-api-key": "sk-anthropic-seeded",
    }


def test_create_message_uses_anthropic_headers_and_messages_url(monkeypatch) -> None:
    provider = make_anthropic_provider()
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"id": "msg_123", "type": "message"}

    class FakeRequestContext:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, headers: dict | None = None, json: dict | None = None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            captured["timeout"] = timeout

        def __enter__(self):
            return FakeRequestContext()

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr("app.providers.anthropic_compatible.httpx.Client", FakeClient)

    response = create_message(
        provider,
        api_key="sk-anthropic-seeded",
        payload={"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "hello"}]},
    )

    assert response == {"id": "msg_123", "type": "message"}
    assert captured["timeout"] == 60.0
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["headers"]["x-api-key"] == "sk-anthropic-seeded"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert captured["json"] == {
        "model": "claude-sonnet-4-5",
        "messages": [{"role": "user", "content": "hello"}],
    }


def test_list_models_uses_models_url_and_anthropic_headers(monkeypatch) -> None:
    provider = make_anthropic_provider()
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"data": [{"id": "claude-sonnet-4-5"}]}

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str, headers: dict | None = None):
            captured["url"] = url
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr("app.providers.anthropic_compatible.httpx.Client", FakeClient)

    response = list_models(provider, api_key="sk-anthropic-seeded")

    assert response == {"data": [{"id": "claude-sonnet-4-5"}]}
    assert captured["timeout"] == 30.0
    assert captured["url"] == "https://api.anthropic.com/v1/models"
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["headers"]["x-api-key"] == "sk-anthropic-seeded"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"


def test_get_model_uses_model_url_and_anthropic_headers(monkeypatch) -> None:
    provider = make_anthropic_provider()
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"id": "claude-sonnet-4-5-20250929", "type": "model"}

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str, headers: dict | None = None):
            captured["url"] = url
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr("app.providers.anthropic_compatible.httpx.Client", FakeClient)

    response = get_model(provider, api_key="sk-anthropic-seeded", model_id="claude-sonnet-4-5-20250929")

    assert response == {"id": "claude-sonnet-4-5-20250929", "type": "model"}
    assert captured["url"] == "https://api.anthropic.com/v1/models/claude-sonnet-4-5-20250929"
    assert captured["headers"]["x-api-key"] == "sk-anthropic-seeded"


def test_count_message_tokens_uses_count_tokens_url_and_headers(monkeypatch) -> None:
    provider = make_anthropic_provider()
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"input_tokens": 11}

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, headers: dict | None = None, json: dict | None = None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr("app.providers.anthropic_compatible.httpx.Client", FakeClient)

    response = count_message_tokens(
        provider,
        api_key="sk-anthropic-seeded",
        payload={"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "hello"}]},
    )

    assert response == {"input_tokens": 11}
    assert captured["url"] == "https://api.anthropic.com/v1/messages/count_tokens"
    assert captured["headers"]["x-api-key"] == "sk-anthropic-seeded"
    assert captured["json"]["model"] == "claude-sonnet-4-5"


def test_create_file_uses_files_url_beta_header_and_multipart_upload(monkeypatch) -> None:
    provider = make_anthropic_provider()
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"id": "file_123", "type": "file"}

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, headers: dict | None = None, files=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["files"] = files
            return FakeResponse()

    monkeypatch.setattr("app.providers.anthropic_compatible.httpx.Client", FakeClient)

    response = create_file(
        provider,
        api_key="sk-anthropic-seeded",
        filename="document.pdf",
        content=b"pdf-bytes",
        content_type="application/pdf",
    )

    assert response == {"id": "file_123", "type": "file"}
    assert captured["url"] == "https://api.anthropic.com/v1/files"
    assert captured["headers"]["anthropic-beta"] == FILES_API_BETA
    assert captured["files"]["file"][0] == "document.pdf"
    assert captured["files"]["file"][1] == b"pdf-bytes"
    assert captured["files"]["file"][2] == "application/pdf"


def test_stream_message_events_passes_through_sse_lines(monkeypatch) -> None:
    provider = make_anthropic_provider()
    captured: dict = {}

    class FakeStreamResponse:
        def raise_for_status(self) -> None:
            return None

        def iter_lines(self) -> Iterable[str]:
            return [
                'event: message_start',
                'data: {"type":"message_start"}',
                '',
                'data: {"type":"message_delta"}',
            ]

    class FakeStreamContext:
        def __enter__(self):
            return FakeStreamResponse()

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def stream(self, method: str, url: str, headers: dict | None = None, json: dict | None = None):
            captured["method"] = method
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeStreamContext()

    monkeypatch.setattr("app.providers.anthropic_compatible.httpx.Client", FakeClient)

    events = list(
        stream_message_events(
            provider,
            api_key="sk-anthropic-seeded",
            payload={"model": "claude-sonnet-4-5", "stream": True},
        )
    )

    assert events == [
        'event: message_start',
        'data: {"type":"message_start"}',
        'data: {"type":"message_delta"}',
    ]
    assert captured["timeout"] == 60.0
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["headers"]["Accept"] == "text/event-stream"
    assert captured["headers"]["x-api-key"] == "sk-anthropic-seeded"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert captured["json"] == {"model": "claude-sonnet-4-5", "stream": True}


@pytest.mark.parametrize("factory", ["http_status", "transport", "value"])
def test_create_message_maps_upstream_errors(monkeypatch, factory: str) -> None:
    provider = make_anthropic_provider()
    request = httpx.Request("POST", _url(provider, "v1/messages"))
    response = httpx.Response(503, request=request, text="temporary outage")
    expected = HTTPException(status_code=502, detail={"message": f"mapped {factory}"})
    captured: dict[str, object] = {}

    def fake_http_error_mapper(exc: httpx.HTTPStatusError) -> HTTPException:
        captured["http_error"] = exc
        return expected

    def fake_transport_error_mapper(exc: httpx.HTTPError | ValueError) -> HTTPException:
        captured["transport_error"] = exc
        return expected

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, headers: dict | None = None, json: dict | None = None):
            if factory == "http_status":
                raise httpx.HTTPStatusError("temporary outage", request=request, response=response)
            if factory == "transport":
                raise httpx.ConnectError("network down", request=request)
            raise ValueError("invalid upstream payload")

    monkeypatch.setattr("app.providers.anthropic_compatible.httpx.Client", FakeClient)
    monkeypatch.setattr(
        "app.providers.anthropic_compatible.http_exception_from_upstream_http_error",
        fake_http_error_mapper,
    )
    monkeypatch.setattr(
        "app.providers.anthropic_compatible.http_exception_from_upstream_transport_error",
        fake_transport_error_mapper,
    )

    with pytest.raises(HTTPException) as exc_info:
        create_message(provider, api_key="sk-anthropic-seeded", payload={"model": "claude"})

    assert exc_info.value is expected
    if factory == "http_status":
        assert isinstance(captured["http_error"], httpx.HTTPStatusError)
        assert "transport_error" not in captured
    else:
        assert isinstance(captured["transport_error"], httpx.HTTPError | ValueError)
        assert "http_error" not in captured


@pytest.mark.parametrize("factory", ["http_status", "transport", "value"])
def test_list_models_maps_upstream_errors(monkeypatch, factory: str) -> None:
    provider = make_anthropic_provider()
    request = httpx.Request("GET", _url(provider, "v1/models"))
    response = httpx.Response(502, request=request, text="bad gateway")
    expected = HTTPException(status_code=502, detail={"message": f"mapped {factory}"})
    captured: dict[str, object] = {}

    def fake_http_error_mapper(exc: httpx.HTTPStatusError) -> HTTPException:
        captured["http_error"] = exc
        return expected

    def fake_transport_error_mapper(exc: httpx.HTTPError | ValueError) -> HTTPException:
        captured["transport_error"] = exc
        return expected

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str, headers: dict | None = None):
            if factory == "http_status":
                raise httpx.HTTPStatusError("bad gateway", request=request, response=response)
            if factory == "transport":
                raise httpx.ReadError("socket closed", request=request)
            raise ValueError("invalid models payload")

    monkeypatch.setattr("app.providers.anthropic_compatible.httpx.Client", FakeClient)
    monkeypatch.setattr(
        "app.providers.anthropic_compatible.http_exception_from_upstream_http_error",
        fake_http_error_mapper,
    )
    monkeypatch.setattr(
        "app.providers.anthropic_compatible.http_exception_from_upstream_transport_error",
        fake_transport_error_mapper,
    )

    with pytest.raises(HTTPException) as exc_info:
        list_models(provider, api_key="sk-anthropic-seeded")

    assert exc_info.value is expected
    if factory == "http_status":
        assert isinstance(captured["http_error"], httpx.HTTPStatusError)
        assert "transport_error" not in captured
    else:
        assert isinstance(captured["transport_error"], httpx.HTTPError | ValueError)
        assert "http_error" not in captured


@pytest.mark.parametrize("factory", ["http_status", "transport"])
def test_stream_message_events_maps_upstream_errors(monkeypatch, factory: str) -> None:
    provider = make_anthropic_provider()
    request = httpx.Request("POST", _url(provider, "v1/messages"))
    response = httpx.Response(504, request=request, text="gateway timeout")
    expected = HTTPException(status_code=502, detail={"message": f"mapped {factory}"})
    captured: dict[str, object] = {}

    def fake_http_error_mapper(exc: httpx.HTTPStatusError) -> HTTPException:
        captured["http_error"] = exc
        return expected

    def fake_transport_error_mapper(exc: httpx.HTTPError | ValueError) -> HTTPException:
        captured["transport_error"] = exc
        return expected

    class FakeStreamContext:
        def __enter__(self):
            if factory == "http_status":
                raise httpx.HTTPStatusError("gateway timeout", request=request, response=response)
            raise httpx.ReadTimeout("timed out", request=request)

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def stream(self, method: str, url: str, headers: dict | None = None, json: dict | None = None):
            return FakeStreamContext()

    monkeypatch.setattr("app.providers.anthropic_compatible.httpx.Client", FakeClient)
    monkeypatch.setattr(
        "app.providers.anthropic_compatible.http_exception_from_upstream_http_error",
        fake_http_error_mapper,
    )
    monkeypatch.setattr(
        "app.providers.anthropic_compatible.http_exception_from_upstream_transport_error",
        fake_transport_error_mapper,
    )

    with pytest.raises(HTTPException) as exc_info:
        list(stream_message_events(provider, api_key="sk-anthropic-seeded", payload={"model": "claude", "stream": True}))

    assert exc_info.value is expected
    if factory == "http_status":
        assert isinstance(captured["http_error"], httpx.HTTPStatusError)
        assert "transport_error" not in captured
    else:
        assert isinstance(captured["transport_error"], httpx.HTTPError)
        assert "http_error" not in captured
