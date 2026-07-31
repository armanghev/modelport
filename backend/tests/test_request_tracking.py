from __future__ import annotations

from fastapi.testclient import TestClient

from app.database import ApiRequest, build_session_factory

from tests.test_helpers import seed_pricing


def test_messages_route_persists_request_usage_and_cost(
    client: TestClient,
    app_config,
    monkeypatch,
) -> None:
    seed_pricing(
        client,
        provider_slug="openai",
        model="gpt-5.5",
        input_per_1m_usd=2.0,
        output_per_1m_usd=8.0,
    )

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
        assert record.pricing_source == "fixture"
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


def test_messages_route_persists_stream_request_with_gemini_usage_and_reasoning(
    client: TestClient,
    app_config,
    monkeypatch,
) -> None:
    seed_pricing(
        client,
        provider_slug="gemini",
        model="models/gemini-2.5-pro",
        input_per_1m_usd=1.25,
        output_per_1m_usd=10.0,
    )

    def fake_stream_chat_completion_chunks(provider, api_key, payload):
        assert payload.get("stream_options") == {"include_usage": True}
        yield '{"id":"chatcmpl_gemini_stream","choices":[{"delta":{"role":"assistant","content":"Hi"},"finish_reason":null}]}'
        yield (
            '{"id":"chatcmpl_gemini_stream","choices":[{"delta":{"content":"!"},"finish_reason":"stop"}],'
            '"usage":{"prompt_tokens":102475,"completion_tokens":45,"total_tokens":102924,'
            '"completion_tokens_details":{"reasoning_tokens":404}}}'
        )
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
            "provider": "gemini",
            "model": "models/gemini-2.5-pro",
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
        assert record.provider == "gemini"
        assert record.streamed is True
        assert record.token_source == "provider_reported"
        assert record.input_tokens == 102_475
        assert record.output_tokens == 449
        assert record.total_tokens == 102_924
        assert record.estimated_cost_usd == round(
            (102_475 / 1_000_000) * 1.25 + (449 / 1_000_000) * 10.0,
            6,
        )


def test_messages_route_persists_stream_request_metadata(
    client: TestClient,
    app_config,
    monkeypatch,
) -> None:
    seed_pricing(
        client,
        provider_slug="openai",
        model="gpt-5.5",
        input_per_1m_usd=2.0,
        output_per_1m_usd=8.0,
    )

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


def test_chat_completions_route_persists_request_usage_and_cost(
    client: TestClient,
    app_config,
    monkeypatch,
) -> None:
    seed_pricing(
        client,
        provider_slug="openai",
        model="gpt-5.5",
        input_per_1m_usd=2.0,
        output_per_1m_usd=8.0,
    )

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "id": "chatcmpl_openai_req_123",
                "object": "chat.completion",
                "created": 1_717_171_717,
                "model": "gpt-5.5",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Tracked openai response"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
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
        "/v1/chat/completions",
        headers={
            "Authorization": "Bearer test-local-token",
            "User-Agent": "OpenAI-Python/1.0",
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
        assert record.input_format == "openai"
        assert record.output_format == "openai"
        assert record.endpoint == "/v1/chat/completions"
        assert record.client_name == "OpenAI-Python/1.0"
        assert record.requested_model == "gpt-5.5"
        assert record.resolved_model == "gpt-5.5"
        assert record.provider == "openai"
        assert record.input_tokens == 1000
        assert record.output_tokens == 500
        assert record.total_tokens == 1500
        assert record.estimated_cost_usd == 0.006
        assert record.status_code == 200
        assert record.request_id == "chatcmpl_openai_req_123"
        assert record.streamed is False


def test_chat_completions_route_persists_stream_request_metadata(
    client: TestClient,
    app_config,
    monkeypatch,
) -> None:
    def fake_stream_chat_completion_chunks(provider, api_key, payload):
        yield '{"id":"chatcmpl_openai_stream_456","choices":[{"delta":{"role":"assistant","content":"Hello"},"finish_reason":null}]}'
        yield '{"id":"chatcmpl_openai_stream_456","choices":[{"delta":{"content":" world"},"finish_reason":"stop"}],"usage":{"prompt_tokens":1000,"completion_tokens":500}}'
        yield "[DONE]"

    monkeypatch.setattr(
        "app.api.openai.stream_chat_completion_chunks",
        fake_stream_chat_completion_chunks,
    )

    with client.stream(
        "POST",
        "/v1/chat/completions",
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
        assert record.endpoint == "/v1/chat/completions"
        assert record.input_format == "openai"
        assert record.output_format == "openai"
        assert record.provider == "openai"
        assert record.streamed is True
        assert record.request_id == "chatcmpl_openai_stream_456"
        assert record.input_tokens == 1000
        assert record.output_tokens == 500
        assert record.total_tokens == 1500
        assert record.status_code == 200
        assert record.completion_reason == "stop"
        assert record.ttfb_ms is not None


def test_messages_route_stores_io_when_logging_enabled(
    client: TestClient,
    app_config,
    monkeypatch,
) -> None:
    enable_io = client.patch("/admin/settings/tracking", json={"io_logging": True})
    assert enable_io.status_code == 200

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "id": "chatcmpl_io_123",
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
        headers={"Authorization": "Bearer test-local-token"},
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
        record = session.query(ApiRequest).one()
        assert record.request_body is not None
        assert '"hello"' in record.request_body
        assert record.response_body is not None
        assert "Tracked response" in record.response_body

    analytics = client.get("/analytics/requests")
    assert analytics.status_code == 200
    row = analytics.json()["rows"][0]
    assert "io" not in row

    detail = client.get(f"/analytics/requests/{row['id']}")
    assert detail.status_code == 200
    assert detail.json()["io"]["input"] == record.request_body
    assert detail.json()["io"]["output"] == record.response_body


def test_messages_route_does_not_store_io_when_logging_disabled(
    client: TestClient,
    app_config,
    monkeypatch,
) -> None:
    disable_io = client.patch("/admin/settings/tracking", json={"io_logging": False})
    assert disable_io.status_code == 200

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "id": "chatcmpl_no_io_123",
                "model": "gpt-5.5",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "No io"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
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
        record = session.query(ApiRequest).one()
        assert record.request_body is None
        assert record.response_body is None

    analytics = client.get("/analytics/requests")
    assert analytics.status_code == 200
    row = analytics.json()["rows"][0]
    assert not row.get("io") or (not row["io"].get("input") and not row["io"].get("output"))
