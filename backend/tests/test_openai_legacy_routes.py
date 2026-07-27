from __future__ import annotations

from fastapi.testclient import TestClient


def test_completions_route_proxies_openai_compatible_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: dict = {}

    def fake_create_completion(provider, api_key, payload):
        captured["payload"] = payload
        return {
            "id": "cmpl_123",
            "object": "text_completion",
            "model": "gpt-3.5-turbo-instruct",
            "choices": [{"text": "Hello", "index": 0, "finish_reason": "stop"}],
        }

    monkeypatch.setattr("app.api.openai.create_completion", fake_create_completion)

    response = client.post(
        "/v1/completions",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "openai",
            "model": "gpt-3.5-turbo-instruct",
            "prompt": "Say hello",
            "max_tokens": 16,
        },
    )

    assert response.status_code == 200
    assert captured["payload"] == {
        "model": "gpt-3.5-turbo-instruct",
        "prompt": "Say hello",
        "max_tokens": 16,
    }
    assert response.json()["choices"][0]["text"] == "Hello"


def test_completions_route_streams_openai_compatible_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    def fake_stream_completion_chunks(provider, api_key, payload):
        assert payload["stream"] is True
        yield '{"id":"cmpl_stream","choices":[{"text":"Hi","index":0,"finish_reason":null}]}'
        yield "[DONE]"

    monkeypatch.setattr("app.api.openai.stream_completion_chunks", fake_stream_completion_chunks)

    with client.stream(
        "POST",
        "/v1/completions",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "openai",
            "model": "gpt-3.5-turbo-instruct",
            "prompt": "Say hello",
            "stream": True,
        },
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"text":"Hi"' in body
    assert "data: [DONE]" in body


def test_completions_route_rejects_anthropic_provider(client: TestClient) -> None:
    response = client.post(
        "/v1/completions",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "anthropic",
            "model": "claude-sonnet-4-5",
            "prompt": "Say hello",
        },
    )

    assert response.status_code == 501


def test_moderations_route_proxies_openai_compatible_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: dict = {}

    def fake_create_moderation(provider, api_key, payload):
        captured["payload"] = payload
        return {
            "id": "modr_123",
            "model": "omni-moderation-latest",
            "results": [{"flagged": False, "categories": {}, "category_scores": {}}],
        }

    monkeypatch.setattr("app.api.openai.create_moderation", fake_create_moderation)

    response = client.post(
        "/v1/moderations",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "openai",
            "model": "omni-moderation-latest",
            "input": "hello",
        },
    )

    assert response.status_code == 200
    assert captured["payload"] == {
        "model": "omni-moderation-latest",
        "input": "hello",
    }
    assert response.json()["id"] == "modr_123"


def test_moderations_route_rejects_anthropic_provider(client: TestClient) -> None:
    response = client.post(
        "/v1/moderations",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "anthropic",
            "input": "hello",
        },
    )

    assert response.status_code == 501
