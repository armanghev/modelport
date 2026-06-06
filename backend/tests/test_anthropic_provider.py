from __future__ import annotations

from collections.abc import Iterable

from app.database import Provider
from app.providers.anthropic_compatible import (
    build_headers,
    build_messages_url,
    build_models_url,
    create_message,
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

    assert build_messages_url(provider) == "https://api.anthropic.com/v1/messages"
    assert build_models_url(provider) == "https://api.anthropic.com/v1/models"


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
