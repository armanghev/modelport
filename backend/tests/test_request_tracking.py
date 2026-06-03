from __future__ import annotations

from fastapi.testclient import TestClient

from app.database import ApiRequest, build_session_factory


def test_messages_route_persists_request_usage_and_cost(
    client: TestClient,
    app_config,
    monkeypatch,
) -> None:
    pricing_response = client.post(
        "/admin/pricing",
        json={
            "provider_id": "openai",
            "model": "gpt-5.5",
            "input_per_1m_usd": 2.0,
            "output_per_1m_usd": 8.0,
            "currency": "USD",
            "enabled": True,
        },
    )
    assert pricing_response.status_code == 201

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "id": "chatcmpl_req_123",
                "model": "gpt-5.5",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Tracked response"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 500},
            }

    class FakeHttpClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, headers: dict | None = None, json: dict | None = None):
            return FakeResponse()

    monkeypatch.setattr("app.providers.openai_compatible.httpx.Client", FakeHttpClient)

    response = client.post(
        "/v1/messages",
        headers={
            "Authorization": "Bearer test-local-token",
            "User-Agent": "Claude-Code/1.0",
        },
        json={
            "provider": "openai",
            "model": "gpt-5.5",
            "max_tokens": 256,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 200

    session_factory = build_session_factory(f"sqlite:///{app_config.parent / 'test.db'}")
    with session_factory() as session:
        records = session.query(ApiRequest).all()
        assert len(records) == 1
        record = records[0]
        assert record.input_format == "anthropic"
        assert record.output_format == "anthropic"
        assert record.endpoint == "/v1/messages"
        assert record.client_name == "Claude-Code/1.0"
        assert record.requested_model == "gpt-5.5"
        assert record.resolved_model == "gpt-5.5"
        assert record.provider == "openai"
        assert record.input_tokens == 1000
        assert record.output_tokens == 500
        assert record.total_tokens == 1500
        assert record.token_source == "provider_reported"
        assert record.estimated_cost_usd == 0.006
        assert record.pricing_source == "admin_override"
        assert record.status_code == 200
        assert record.error_message is None
        assert record.request_id == "chatcmpl_req_123"
        assert record.streamed is False
        assert record.duration_ms >= 0


def test_messages_route_persists_request_when_pricing_is_missing(
    client: TestClient,
    app_config,
    monkeypatch,
) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "id": "chatcmpl_req_456",
                "model": "gpt-5.5",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "No pricing"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 250, "completion_tokens": 250},
            }

    class FakeHttpClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, headers: dict | None = None, json: dict | None = None):
            return FakeResponse()

    monkeypatch.setattr("app.providers.openai_compatible.httpx.Client", FakeHttpClient)

    response = client.post(
        "/v1/messages",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "openai",
            "model": "gpt-5.5",
            "max_tokens": 32,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 200

    session_factory = build_session_factory(f"sqlite:///{app_config.parent / 'test.db'}")
    with session_factory() as session:
        records = session.query(ApiRequest).all()
        assert len(records) == 1
        record = records[0]
        assert record.estimated_cost_usd is None
        assert record.pricing_source is None


def test_messages_route_persists_failed_request(
    client: TestClient,
    app_config,
    monkeypatch,
) -> None:
    from fastapi import HTTPException

    def fake_create_chat_completion(provider, api_key, payload):
        raise HTTPException(status_code=502, detail="Upstream provider request failed: boom")

    monkeypatch.setattr("app.api.anthropic.create_chat_completion", fake_create_chat_completion)

    response = client.post(
        "/v1/messages",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "openai",
            "model": "gpt-5.5",
            "max_tokens": 32,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 502

    session_factory = build_session_factory(f"sqlite:///{app_config.parent / 'test.db'}")
    with session_factory() as session:
        records = session.query(ApiRequest).all()
        assert len(records) == 1
        record = records[0]
        assert record.provider == "openai"
        assert record.requested_model == "gpt-5.5"
        assert record.status_code == 502
        assert record.error_message == "Upstream provider request failed: boom"
        assert record.input_tokens == 0
        assert record.output_tokens == 0
        assert record.total_tokens == 0


def test_messages_route_persists_stream_request_metadata(
    client: TestClient,
    app_config,
    monkeypatch,
) -> None:
    pricing_response = client.post(
        "/admin/pricing",
        json={
            "provider_id": "openai",
            "model": "gpt-5.5",
            "input_per_1m_usd": 2.0,
            "output_per_1m_usd": 8.0,
            "currency": "USD",
            "enabled": True,
        },
    )
    assert pricing_response.status_code == 201

    def fake_stream_chat_completion_chunks(provider, api_key, payload):
        yield '{"id":"chatcmpl_stream_456","choices":[{"delta":{"role":"assistant","content":"Hello"},"finish_reason":null}]}'
        yield '{"id":"chatcmpl_stream_456","choices":[{"delta":{"content":" world"},"finish_reason":"stop"}],"usage":{"prompt_tokens":1000,"completion_tokens":500}}'
        yield "[DONE]"

    monkeypatch.setattr(
        "app.api.anthropic.stream_chat_completion_chunks",
        fake_stream_chat_completion_chunks,
    )

    with client.stream(
        "POST",
        "/v1/messages",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "openai",
            "model": "gpt-5.5",
            "max_tokens": 128,
            "stream": True,
            "messages": [{"role": "user", "content": "hello"}],
        },
    ) as response:
        _ = "".join(response.iter_text())

    assert response.status_code == 200

    session_factory = build_session_factory(f"sqlite:///{app_config.parent / 'test.db'}")
    with session_factory() as session:
        records = session.query(ApiRequest).all()
        assert len(records) == 1
        record = records[0]
        assert record.provider == "openai"
        assert record.streamed is True
        assert record.request_id == "chatcmpl_stream_456"
        assert record.input_tokens == 1000
        assert record.output_tokens == 500
        assert record.total_tokens == 1500
        assert record.estimated_cost_usd == 0.006
        assert record.status_code == 200
        assert record.completion_reason == "stop"
        assert record.ttfb_ms is not None
