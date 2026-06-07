from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.database import ProviderHealthCheck


def test_messages_route_requires_proxy_token(client: TestClient) -> None:
    response = client.post(
        "/v1/messages",
        json={
            "provider": "openai",
            "model": "gpt",
            "max_tokens": 32,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 401
    assert "Authorization" in response.json()["detail"]


def test_messages_route_requires_explicit_provider_selection(client: TestClient) -> None:
    response = client.post(
        "/v1/messages",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "model": "gpt-5.5",
            "max_tokens": 32,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 400
    assert "Provider selection is required" in response.json()["detail"]


def test_messages_route_translates_anthropic_request_to_openai_upstream(
    client: TestClient,
    monkeypatch,
) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "id": "chatcmpl_test_123",
                "model": "gpt-5.5",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Hello from OpenAI"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 7},
            }

    class FakeHttpClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, headers: dict | None = None, json: dict | None = None):
            assert url == "https://api.openai.com/v1/chat/completions"
            assert headers is not None
            assert headers["Authorization"] == "Bearer sk-openai-seeded"
            assert json == {
                "model": "gpt-5.5",
                "max_tokens": 128,
                "messages": [
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "How can I help?"},
                ],
                "stream": False,
            }
            return FakeResponse()

    monkeypatch.setattr("app.providers.openai_compatible.httpx.Client", FakeHttpClient)

    response = client.post(
        "/v1/messages",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "openai",
            "model": "gpt-5.5",
            "max_tokens": 128,
            "system": "You are helpful.",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": [{"type": "text", "text": "How can I help?"}]},
            ],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": "chatcmpl_test_123",
        "type": "message",
        "role": "assistant",
        "model": "gpt-5.5",
        "content": [{"type": "text", "text": "Hello from OpenAI"}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 12, "output_tokens": 7},
    }


def test_messages_route_supports_anthropic_upstream_without_openai_translation(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: dict = {}

    def fake_create_anthropic_message(provider, api_key, payload):
        captured["provider_id"] = provider.id
        captured["api_key"] = api_key
        captured["payload"] = payload
        return {
            "id": "msg_upstream_123",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-4-5-20250929",
            "content": [{"type": "text", "text": "Hello from Anthropic"}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 11, "output_tokens": 5},
        }

    monkeypatch.setattr(
        "app.api.anthropic.create_anthropic_message",
        fake_create_anthropic_message,
    )

    response = client.post(
        "/v1/messages",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "anthropic",
            "fallback_providers": ["openai"],
            "model": "claude-sonnet-4-5",
            "max_tokens": 128,
            "system": "You are helpful.",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": "msg_upstream_123",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-4-5-20250929",
        "content": [{"type": "text", "text": "Hello from Anthropic"}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 11, "output_tokens": 5},
    }
    assert captured == {
        "provider_id": "anthropic",
        "api_key": "sk-anthropic-seeded",
        "payload": {
            "model": "claude-sonnet-4-5",
            "max_tokens": 128,
            "system": "You are helpful.",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False,
        },
    }


def test_messages_route_uses_database_backed_default_credential(
    client: TestClient,
    monkeypatch,
) -> None:
    credentials_response = client.get("/admin/provider-credentials")
    default_openai_credential = next(
        credential
        for credential in credentials_response.json()
        if credential["provider_id"] == "openai" and credential["is_default"]
    )
    disable_response = client.patch(
        f"/admin/provider-credentials/{default_openai_credential['id']}",
        json={"enabled": False},
    )
    assert disable_response.status_code == 200

    create_response = client.post(
        "/admin/provider-credentials",
        json={
            "provider_id": "openai",
            "display_name": "OpenAI DB Key",
            "source": "database",
            "api_key": "sk-db-backed-secret",
            "is_default": True,
            "enabled": True,
        },
    )
    assert create_response.status_code == 201

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "id": "chatcmpl_db_123",
                "model": "gpt-5.5",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Using database credential"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 4, "completion_tokens": 5},
            }

    class FakeHttpClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, headers: dict | None = None, json: dict | None = None):
            assert headers is not None
            assert headers["Authorization"] == "Bearer sk-db-backed-secret"
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
    assert response.json()["content"][0]["text"] == "Using database credential"


def test_messages_route_infers_openrouter_from_provider_prefixed_vendor_model(
    client: TestClient,
    monkeypatch,
) -> None:
    captured_payload: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "id": "chatcmpl_or_123",
                "model": "google/gemini-2.5-flash",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "OpenRouter vendor route"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            }

    class FakeHttpClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, headers: dict | None = None, json: dict | None = None):
            assert url == "https://openrouter.ai/api/v1/chat/completions"
            assert json is not None
            captured_payload.update(json)
            return FakeResponse()

    monkeypatch.setattr("app.providers.openai_compatible.httpx.Client", FakeHttpClient)

    response = client.post(
        "/v1/messages",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "model": "openrouter/google/gemini-2.5-flash",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 200
    assert captured_payload["model"] == "google/gemini-2.5-flash"


def test_messages_route_infers_openrouter_owned_model_without_double_prefix(
    client: TestClient,
    monkeypatch,
) -> None:
    captured_payload: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "id": "chatcmpl_or_auto_123",
                "model": "openrouter/auto",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "OpenRouter auto route"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            }

    class FakeHttpClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, headers: dict | None = None, json: dict | None = None):
            assert url == "https://openrouter.ai/api/v1/chat/completions"
            assert json is not None
            captured_payload.update(json)
            return FakeResponse()

    monkeypatch.setattr("app.providers.openai_compatible.httpx.Client", FakeHttpClient)

    response = client.post(
        "/v1/messages",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "model": "openrouter/auto",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 200
    assert captured_payload["model"] == "openrouter/auto"


def test_messages_route_infers_gemini_from_models_prefix(
    client: TestClient,
    monkeypatch,
) -> None:
    captured_payload: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "id": "chatcmpl_gemini_123",
                "model": "models/gemini-2.5-flash",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Gemini route"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            }

    class FakeHttpClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, headers: dict | None = None, json: dict | None = None):
            assert url == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            assert json is not None
            captured_payload.update(json)
            return FakeResponse()

    monkeypatch.setattr("app.providers.openai_compatible.httpx.Client", FakeHttpClient)

    response = client.post(
        "/v1/messages",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "model": "models/gemini-2.5-flash",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 200
    assert captured_payload["model"] == "models/gemini-2.5-flash"


def test_messages_route_infers_openrouter_from_native_vendor_prefix(
    client: TestClient,
    monkeypatch,
) -> None:
    captured_payload: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "id": "chatcmpl_or_native_123",
                "model": "google/gemini-2.5-flash",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Native vendor route"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            }

    class FakeHttpClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, headers: dict | None = None, json: dict | None = None):
            assert url == "https://openrouter.ai/api/v1/chat/completions"
            assert json is not None
            captured_payload.update(json)
            return FakeResponse()

    monkeypatch.setattr("app.providers.openai_compatible.httpx.Client", FakeHttpClient)

    response = client.post(
        "/v1/messages",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "model": "google/gemini-2.5-flash",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 200
    assert captured_payload["model"] == "google/gemini-2.5-flash"


def test_messages_route_infers_direct_provider_from_provider_prefixed_model(
    client: TestClient,
    monkeypatch,
) -> None:
    captured_payload: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "id": "chatcmpl_openai_123",
                "model": "gpt-4.1",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Direct OpenAI route"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            }

    class FakeHttpClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, headers: dict | None = None, json: dict | None = None):
            assert url == "https://api.openai.com/v1/chat/completions"
            assert json is not None
            captured_payload.update(json)
            return FakeResponse()

    monkeypatch.setattr("app.providers.openai_compatible.httpx.Client", FakeHttpClient)

    response = client.post(
        "/v1/messages",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "model": "openai/gpt-4.1",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 200
    assert captured_payload["model"] == "gpt-4.1"


def test_messages_route_supports_provider_header_override(
    client: TestClient,
    monkeypatch,
) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "id": "chatcmpl_fallback_123",
                "model": "gpt-4.1-mini",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Fallback route"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            }

    class FakeHttpClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, headers: dict | None = None, json: dict | None = None):
            assert url == "https://openrouter.ai/api/v1/chat/completions"
            assert headers is not None
            assert headers["Authorization"] == "Bearer sk-openrouter-seeded"
            assert json is not None
            assert json["model"] == "gpt-4.1-mini"
            return FakeResponse()

    monkeypatch.setattr("app.providers.openai_compatible.httpx.Client", FakeHttpClient)

    response = client.post(
        "/v1/messages",
        headers={
            "Authorization": "Bearer test-local-token",
            "X-ModelPort-Provider": "openrouter",
        },
        json={
            "model": "gpt-4.1-mini",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["model"] == "gpt-4.1-mini"


def test_messages_route_allows_localhost_openai_compatible_provider_without_key(
    client: TestClient,
    monkeypatch,
) -> None:
    provider_response = client.post(
        "/admin/providers",
        json={
            "id": "lmstudio",
            "display_name": "LM Studio",
            "provider_type": "openai_compatible",
            "base_url": "http://127.0.0.1:12345/v1",
        },
    )
    assert provider_response.status_code == 201

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "id": "chatcmpl_local_123",
                "model": "local-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Local provider route"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 2, "completion_tokens": 4},
            }

    class FakeHttpClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, headers: dict | None = None, json: dict | None = None):
            assert url == "http://127.0.0.1:12345/v1/chat/completions"
            assert headers == {"Content-Type": "application/json"}
            return FakeResponse()

    monkeypatch.setattr("app.providers.openai_compatible.httpx.Client", FakeHttpClient)

    response = client.post(
        "/v1/messages",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "lmstudio",
            "model": "local-model",
            "max_tokens": 32,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["content"][0]["text"] == "Local provider route"


def test_messages_route_streams_anthropic_sse_events(
    client: TestClient,
    monkeypatch,
) -> None:
    def fake_stream_chat_completion_chunks(provider, api_key, payload):
        assert payload["stream"] is True
        yield '{"id":"chatcmpl_stream_123","choices":[{"delta":{"role":"assistant","content":"Hello"},"finish_reason":null}]}'
        yield '{"id":"chatcmpl_stream_123","choices":[{"delta":{"content":" world"},"finish_reason":"stop"}],"usage":{"prompt_tokens":12,"completion_tokens":7}}'
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
            "max_tokens": 64,
            "stream": True,
            "messages": [{"role": "user", "content": "hello"}],
        },
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: message_start" in body
    assert '"text": "Hello"' in body
    assert '"text": " world"' in body
    assert '"stop_reason": "end_turn"' in body
    assert "event: message_stop" in body


def test_messages_route_streams_anthropic_upstream_events_without_openai_chunk_translation(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: dict = {}

    def fake_stream_anthropic_message_events(provider, api_key, payload):
        captured["provider_id"] = provider.id
        captured["api_key"] = api_key
        captured["payload"] = payload
        yield "event: message_start"
        yield 'data: {"type":"message_start","message":{"id":"msg_stream_123","type":"message","role":"assistant","model":"claude-sonnet-4-5-20250929","content":[],"usage":{"input_tokens":9,"output_tokens":0}}}'
        yield 'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello from Anthropic"}}'
        yield 'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":6}}'
        yield "event: message_stop"
        yield 'data: {"type":"message_stop"}'

    monkeypatch.setattr(
        "app.api.anthropic.stream_anthropic_message_events",
        fake_stream_anthropic_message_events,
    )

    with client.stream(
        "POST",
        "/v1/messages",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "anthropic",
            "fallback_providers": ["openai"],
            "model": "claude-sonnet-4-5",
            "max_tokens": 64,
            "stream": True,
            "messages": [{"role": "user", "content": "hello"}],
        },
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: message_start" in body
    assert '"type":"content_block_delta"' in body
    assert '"text":"Hello from Anthropic"' in body
    assert '"stop_reason":"end_turn"' in body
    assert "event: message_stop" in body
    assert captured == {
        "provider_id": "anthropic",
        "api_key": "sk-anthropic-seeded",
        "payload": {
            "model": "claude-sonnet-4-5",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True,
        },
    }


def test_messages_route_retries_gemini_when_low_max_tokens_return_empty_completion(
    client: TestClient,
    monkeypatch,
) -> None:
    class RetryingGeminiClient:
        call_payloads: list[dict] = []

        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, headers: dict | None = None, json: dict | None = None):
            assert url == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            assert json is not None
            type(self).call_payloads.append(json)

            class FakeResponse:
                def __init__(self, payload: dict) -> None:
                    self._payload = payload

                def raise_for_status(self) -> None:
                    return None

                def json(self) -> dict:
                    return self._payload

            if len(type(self).call_payloads) == 1:
                return FakeResponse(
                    {
                        "id": "gemini_empty_1",
                        "model": "models/gemini-2.5-pro",
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant"},
                                "finish_reason": "length",
                            }
                        ],
                        "usage": {"prompt_tokens": 7, "completion_tokens": 0, "total_tokens": 68},
                    }
                )

            return FakeResponse(
                {
                    "id": "gemini_retry_2",
                    "model": "models/gemini-2.5-pro",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "proxy ok"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 183},
                }
            )

    monkeypatch.setattr("app.providers.openai_compatible.httpx.Client", RetryingGeminiClient)

    response = client.post(
        "/v1/messages",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "gemini",
            "model": "models/gemini-2.5-pro",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "Reply with exactly: proxy ok"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["content"][0]["text"] == "proxy ok"
    assert len(RetryingGeminiClient.call_payloads) == 2
    assert RetryingGeminiClient.call_payloads[0]["max_tokens"] == 64
    assert RetryingGeminiClient.call_payloads[1]["max_tokens"] == 512


def test_chat_completions_route_returns_openai_compatible_response(
    client: TestClient,
    monkeypatch,
) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "id": "chatcmpl_openai_123",
                "object": "chat.completion",
                "created": 1_717_171_717,
                "model": "gpt-5.5",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "OpenAI route"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 7, "total_tokens": 19},
            }

    class FakeHttpClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, headers: dict | None = None, json: dict | None = None):
            assert url == "https://api.openai.com/v1/chat/completions"
            assert headers is not None
            assert headers["Authorization"] == "Bearer sk-openai-seeded"
            assert json == {
                "model": "gpt-5.5",
                "messages": [
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Prior context"},
                ],
                "stream": False,
                "max_tokens": 128,
            }
            return FakeResponse()

    monkeypatch.setattr("app.providers.openai_compatible.httpx.Client", FakeHttpClient)

    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "openai",
            "model": "gpt-5.5",
            "max_tokens": 128,
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Prior context"},
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == "chatcmpl_openai_123"
    assert response.json()["choices"][0]["message"]["content"] == "OpenAI route"
    assert response.json()["usage"]["total_tokens"] == 19


def test_models_route_returns_openai_compatible_models_for_selected_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "object": "list",
                "data": [
                    {
                        "id": "openrouter/auto",
                        "object": "model",
                        "owned_by": "openrouter",
                    }
                ],
            }

    class FakeHttpClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str, headers: dict | None = None):
            assert url == "https://openrouter.ai/api/v1/models"
            assert headers is not None
            assert headers["Authorization"] == "Bearer sk-openrouter-seeded"
            return FakeResponse()

    monkeypatch.setattr("app.providers.openai_compatible.httpx.Client", FakeHttpClient)

    response = client.get(
        "/v1/models",
        headers={
            "Authorization": "Bearer test-local-token",
            "X-ModelPort-Provider": "openrouter",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "object": "list",
        "data": [
            {
                "id": "openrouter/auto",
                "object": "model",
                "owned_by": "openrouter",
            }
        ],
    }


def test_models_route_returns_anthropic_upstream_models_for_selected_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    def fake_list_anthropic_models(provider, api_key):
        assert provider.id == "anthropic"
        assert api_key == "sk-anthropic-seeded"
        return {
            "data": [
                {
                    "id": "claude-sonnet-4-5-20250929",
                    "display_name": "Claude Sonnet 4.5",
                }
            ]
        }

    monkeypatch.setattr(
        "app.api.openai.list_anthropic_models",
        fake_list_anthropic_models,
    )

    response = client.get(
        "/v1/models",
        headers={
            "Authorization": "Bearer test-local-token",
            "X-ModelPort-Provider": "anthropic",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "object": "list",
        "data": [
            {
                "id": "claude-sonnet-4-5-20250929",
                "object": "model",
                "owned_by": "anthropic",
            }
        ]
    }


def test_model_retrieve_route_returns_openai_compatible_model_for_anthropic_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    def fake_get_anthropic_model(provider, api_key, model_id):
        assert provider.id == "anthropic"
        assert api_key == "sk-anthropic-seeded"
        assert model_id == "claude-sonnet-4-5-20250929"
        return {
            "id": "claude-sonnet-4-5-20250929",
            "display_name": "Claude Sonnet 4.5",
            "created_at": "2025-09-29T00:00:00Z",
            "type": "model",
        }

    monkeypatch.setattr(
        "app.api.openai.get_anthropic_model",
        fake_get_anthropic_model,
    )

    response = client.get(
        "/v1/models/claude-sonnet-4-5-20250929",
        headers={
            "Authorization": "Bearer test-local-token",
            "X-ModelPort-Provider": "anthropic",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": "claude-sonnet-4-5-20250929",
        "object": "model",
        "owned_by": "anthropic",
        "created": 1759104000,
    }


def test_embeddings_route_proxies_openai_compatible_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    captured_payload: dict = {}

    def fake_create_embedding(provider, api_key, payload):
        captured_payload.update(payload)
        return {
            "object": "list",
            "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2]}],
            "model": "text-embedding-3-small",
            "usage": {"prompt_tokens": 5, "total_tokens": 5},
        }

    monkeypatch.setattr("app.api.openai.create_embedding", fake_create_embedding)

    response = client.post(
        "/v1/embeddings",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "openai",
            "model": "text-embedding-3-small",
            "input": "hello",
        },
    )

    assert response.status_code == 200
    assert captured_payload == {
        "model": "text-embedding-3-small",
        "input": "hello",
    }
    assert response.json()["data"][0]["embedding"] == [0.1, 0.2]


def test_embeddings_route_rejects_anthropic_provider(
    client: TestClient,
) -> None:
    response = client.post(
        "/v1/embeddings",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "anthropic",
            "model": "claude-sonnet-4-5",
            "input": "hello",
        },
    )

    assert response.status_code == 501


def test_messages_count_tokens_route_supports_anthropic_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: dict = {}

    def fake_count_message_tokens(provider, api_key, payload):
        captured.update(payload)
        return {"input_tokens": 11}

    monkeypatch.setattr(
        "app.api.anthropic.count_message_tokens",
        fake_count_message_tokens,
    )

    response = client.post(
        "/v1/messages/count_tokens",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "anthropic",
            "model": "claude-sonnet-4-5",
            "system": "You are helpful.",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )

    assert response.status_code == 200
    assert captured["model"] == "claude-sonnet-4-5"
    assert captured["system"] == "You are helpful."
    assert response.json() == {"input_tokens": 11}


def test_messages_count_tokens_route_rejects_openai_provider(
    client: TestClient,
) -> None:
    response = client.post(
        "/v1/messages/count_tokens",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "openai",
            "model": "gpt-4.1",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )

    assert response.status_code == 501


def test_chat_completions_route_supports_anthropic_upstream(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: dict = {}

    def fake_create_anthropic_message(provider, api_key, payload):
        captured["provider_id"] = provider.id
        captured["api_key"] = api_key
        captured["payload"] = payload
        return {
            "id": "msg_456",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-4-5-20250929",
            "content": [{"type": "text", "text": "Translated from Anthropic"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 6, "output_tokens": 3},
        }

    monkeypatch.setattr(
        "app.api.openai.create_anthropic_message",
        fake_create_anthropic_message,
    )

    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "anthropic",
            "model": "claude-sonnet-4-5",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "Translated from Anthropic"
    assert response.json()["usage"] == {
        "prompt_tokens": 6,
        "completion_tokens": 3,
        "total_tokens": 9,
    }
    assert captured == {
        "provider_id": "anthropic",
        "api_key": "sk-anthropic-seeded",
        "payload": {
            "model": "claude-sonnet-4-5",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
        },
    }


def test_chat_completions_route_supports_anthropic_upstream_with_sampling_and_stop_controls(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: dict = {}

    def fake_create_anthropic_message(provider, api_key, payload):
        captured.update(payload)
        return {
            "id": "msg_456",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-4-5-20250929",
            "content": [{"type": "text", "text": "Translated from Anthropic"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 6, "output_tokens": 3},
        }

    monkeypatch.setattr(
        "app.api.openai.create_anthropic_message",
        fake_create_anthropic_message,
    )

    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "anthropic",
            "model": "claude-sonnet-4-5",
            "max_tokens": 64,
            "temperature": 0.4,
            "top_p": 0.8,
            "stop": ["END"],
            "tool_choice": "none",
            "messages": [
                {"role": "system", "content": "System"},
                {"role": "developer", "content": "Developer"},
                {"role": "user", "content": "hello"},
            ],
        },
    )

    assert response.status_code == 200
    assert captured["temperature"] == 0.4
    assert captured["top_p"] == 0.8
    assert captured["stop_sequences"] == ["END"]
    assert captured["tool_choice"] == {"type": "none"}
    assert captured["system"] == "System\n\nDeveloper"


def test_chat_completions_route_retries_gemini_when_low_max_tokens_return_empty_completion(
    client: TestClient,
    monkeypatch,
) -> None:
    class RetryingGeminiClient:
        call_payloads: list[dict] = []

        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, headers: dict | None = None, json: dict | None = None):
            assert url == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            assert json is not None
            type(self).call_payloads.append(json)

            class FakeResponse:
                def __init__(self, payload: dict) -> None:
                    self._payload = payload

                def raise_for_status(self) -> None:
                    return None

                def json(self) -> dict:
                    return self._payload

            if len(type(self).call_payloads) == 1:
                return FakeResponse(
                    {
                        "id": "gemini_empty_openai_1",
                        "model": "models/gemini-2.5-pro",
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant"},
                                "finish_reason": "length",
                            }
                        ],
                        "usage": {"prompt_tokens": 7, "completion_tokens": 0, "total_tokens": 68},
                    }
                )

            return FakeResponse(
                {
                    "id": "gemini_retry_openai_2",
                    "model": "models/gemini-2.5-pro",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "proxy ok"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 183},
                }
            )

    monkeypatch.setattr("app.providers.openai_compatible.httpx.Client", RetryingGeminiClient)

    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "gemini",
            "model": "models/gemini-2.5-pro",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "Reply with exactly: proxy ok"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "proxy ok"
    assert len(RetryingGeminiClient.call_payloads) == 2
    assert RetryingGeminiClient.call_payloads[0]["max_tokens"] == 64
    assert RetryingGeminiClient.call_payloads[1]["max_tokens"] == 512


def test_chat_completions_route_streams_openai_sse_chunks(
    client: TestClient,
    monkeypatch,
) -> None:
    def fake_stream_chat_completion_chunks(provider, api_key, payload):
        assert payload["stream"] is True
        yield '{"id":"chatcmpl_openai_stream","object":"chat.completion.chunk","choices":[{"delta":{"role":"assistant","content":"Hello"},"finish_reason":null}]}'
        yield '{"id":"chatcmpl_openai_stream","object":"chat.completion.chunk","choices":[{"delta":{"content":" world"},"finish_reason":"stop"}],"usage":{"prompt_tokens":12,"completion_tokens":7}}'
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
            "max_tokens": 64,
            "stream": True,
            "messages": [{"role": "user", "content": "hello"}],
        },
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert 'data: {"id":"chatcmpl_openai_stream"' in body
    assert '"content":"Hello"' in body
    assert '"content":" world"' in body
    assert "data: [DONE]" in body


def test_chat_completions_route_streams_anthropic_upstream_as_openai_sse(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: dict = {}

    def fake_stream_anthropic_message_events(provider, api_key, payload):
        captured["provider_id"] = provider.id
        captured["api_key"] = api_key
        captured["payload"] = payload
        yield "event: message_start"
        yield 'data: {"type":"message_start","message":{"id":"msg_stream_openai_123","type":"message","role":"assistant","model":"claude-sonnet-4-5-20250929","content":[],"usage":{"input_tokens":8,"output_tokens":0}}}'
        yield 'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}'
        yield 'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}'
        yield 'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" from Anthropic"}}'
        yield 'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":4}}'
        yield "event: message_stop"
        yield 'data: {"type":"message_stop"}'

    monkeypatch.setattr(
        "app.api.openai.stream_anthropic_message_events",
        fake_stream_anthropic_message_events,
    )

    with client.stream(
        "POST",
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "anthropic",
            "model": "claude-sonnet-4-5",
            "max_tokens": 64,
            "stream": True,
            "messages": [{"role": "user", "content": "hello"}],
        },
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert 'data: {"id":"msg_stream_openai_123"' in body
    assert '"content":"Hello"' in body
    assert '"content":" from Anthropic"' in body
    assert '"finish_reason":"stop"' in body
    assert "data: [DONE]" in body
    assert captured == {
        "provider_id": "anthropic",
        "api_key": "sk-anthropic-seeded",
        "payload": {
            "model": "claude-sonnet-4-5",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True,
        },
    }


def test_chat_completions_route_streams_anthropic_tool_use_as_openai_tool_calls(
    client: TestClient,
    monkeypatch,
) -> None:
    def fake_stream_anthropic_message_events(provider, api_key, payload):
        yield 'data: {"type":"message_start","message":{"id":"msg_stream_openai_tool","type":"message","role":"assistant","model":"claude-sonnet-4-5-20250929","content":[],"usage":{"input_tokens":8,"output_tokens":0}}}'
        yield 'data: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"toolu_123","name":"Write","input":{}}}'
        yield 'data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{\\"path\\":\\"out.txt\\"}"}}'
        yield 'data: {"type":"message_delta","delta":{"stop_reason":"tool_use"},"usage":{"output_tokens":4}}'
        yield 'data: {"type":"message_stop"}'

    monkeypatch.setattr(
        "app.api.openai.stream_anthropic_message_events",
        fake_stream_anthropic_message_events,
    )

    with client.stream(
        "POST",
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "anthropic",
            "model": "claude-sonnet-4-5",
            "max_tokens": 64,
            "stream": True,
            "messages": [{"role": "user", "content": "hello"}],
        },
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"tool_calls":[{"index":0,"id":"toolu_123","type":"function","function":{"name":"Write","arguments":""}}]' in body
    assert '"tool_calls":[{"index":0,"type":"function","function":{"arguments":"{\\"path\\":\\"out.txt\\"}"}}]' in body
    assert '"finish_reason":"tool_calls"' in body


def test_messages_route_uses_fallback_provider_when_primary_is_degraded(
    client: TestClient,
    monkeypatch,
) -> None:
    session_factory = client.app.state.session_factory
    with session_factory() as session:
        session.add(
            ProviderHealthCheck(
                provider_id="openrouter",
                status="degraded",
                latency_ms=500,
                available_model_count=3,
                error_message="intermittent upstream errors",
                checked_at=datetime.now(UTC),
            )
        )
        session.add(
            ProviderHealthCheck(
                provider_id="openai",
                status="operational",
                latency_ms=120,
                available_model_count=20,
                error_message=None,
                checked_at=datetime.now(UTC),
            )
        )
        session.commit()

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "id": "chatcmpl_failover_123",
                "model": "gpt-4.1-mini",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Failover route"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            }

    class FakeHttpClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, headers: dict | None = None, json: dict | None = None):
            assert url == "https://api.openai.com/v1/chat/completions"
            assert headers is not None
            assert headers["Authorization"] == "Bearer sk-openai-seeded"
            return FakeResponse()

    monkeypatch.setattr("app.providers.openai_compatible.httpx.Client", FakeHttpClient)

    response = client.post(
        "/v1/messages",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "openrouter",
            "fallback_providers": ["openai"],
            "model": "gpt-4.1-mini",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["content"][0]["text"] == "Failover route"


def test_chat_completions_route_falls_back_after_primary_upstream_failure(
    client: TestClient,
    monkeypatch,
) -> None:
    class FirstFailThenSucceedClient:
        call_count = 0

        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, headers: dict | None = None, json: dict | None = None):
            from httpx import Request, Response, HTTPStatusError

            type(self).call_count += 1
            if "openrouter.ai" in url:
                request = Request("POST", url)
                response = Response(503, request=request, text="temporary outage")
                raise HTTPStatusError("temporary outage", request=request, response=response)

            assert url == "https://api.openai.com/v1/chat/completions"

            class FakeResponse:
                def raise_for_status(self) -> None:
                    return None

                def json(self) -> dict:
                    return {
                        "id": "chatcmpl_failover_openai_123",
                        "object": "chat.completion",
                        "created": 1_717_171_717,
                        "model": "gpt-4.1-mini",
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": "Fallback succeeded"},
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {"prompt_tokens": 6, "completion_tokens": 4, "total_tokens": 10},
                    }

            return FakeResponse()

    monkeypatch.setattr("app.providers.openai_compatible.httpx.Client", FirstFailThenSucceedClient)

    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "openrouter",
            "fallback_providers": ["openai"],
            "model": "gpt-4.1-mini",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "Fallback succeeded"
    assert FirstFailThenSucceedClient.call_count == 2


def test_messages_route_forwards_tools_to_openai_upstream(
    client: TestClient,
    monkeypatch,
) -> None:
    captured_payload: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "id": "chatcmpl_tools",
                "model": "models/gemini-2.5-pro",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_write",
                                    "type": "function",
                                    "function": {
                                        "name": "Write",
                                        "arguments": '{"path":"claude.html","contents":"<html>"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 50, "completion_tokens": 10},
            }

    class FakeHttpClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, headers: dict | None = None, json: dict | None = None):
            captured_payload.update(json or {})
            return FakeResponse()

    monkeypatch.setattr("app.providers.openai_compatible.httpx.Client", FakeHttpClient)

    response = client.post(
        "/v1/messages",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "gemini",
            "model": "models/gemini-2.5-pro",
            "max_tokens": 1024,
            "tool_choice": {"type": "auto"},
            "tools": [
                {
                    "name": "Write",
                    "description": "Write a file",
                    "input_schema": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                    },
                }
            ],
            "messages": [{"role": "user", "content": "Create claude.html"}],
        },
    )

    assert response.status_code == 200
    assert captured_payload["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "Write",
                "description": "Write a file",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                },
            },
        }
    ]
    assert captured_payload["tool_choice"] == "auto"
    assert response.json()["stop_reason"] == "tool_use"
    assert response.json()["content"] == [
        {
            "type": "tool_use",
            "id": "call_write",
            "name": "Write",
            "input": {"path": "claude.html", "contents": "<html>"},
        }
    ]


def test_messages_route_preserves_sampling_and_stop_sequences_for_openai_upstream(
    client: TestClient,
    monkeypatch,
) -> None:
    captured_payload: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "id": "chatcmpl_tools",
                "model": "models/gemini-2.5-pro",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3},
            }

    class FakeHttpClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, headers: dict | None = None, json: dict | None = None):
            captured_payload.update(json or {})
            return FakeResponse()

    monkeypatch.setattr("app.providers.openai_compatible.httpx.Client", FakeHttpClient)

    response = client.post(
        "/v1/messages",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "gemini",
            "model": "models/gemini-2.5-pro",
            "max_tokens": 1024,
            "temperature": 0.4,
            "top_p": 0.8,
            "stop_sequences": ["END"],
            "tool_choice": {"type": "none"},
            "messages": [{"role": "user", "content": "Create claude.html"}],
        },
    )

    assert response.status_code == 200
    assert captured_payload["temperature"] == 0.4
    assert captured_payload["top_p"] == 0.8
    assert captured_payload["stop"] == ["END"]
    assert captured_payload["tool_choice"] == "none"


def test_messages_route_streams_tool_use_sse_events(
    client: TestClient,
    monkeypatch,
) -> None:
    def fake_stream_chat_completion_chunks(provider, api_key, payload):
        assert payload.get("tools") is not None
        assert payload["stream"] is True
        yield (
            '{"id":"chatcmpl_stream_tool","choices":[{"delta":{"tool_calls":[{"index":0,'
            '"id":"call_write","type":"function","function":{"name":"Write","arguments":""}}]},'
            '"finish_reason":null}]}'
        )
        yield (
            '{"id":"chatcmpl_stream_tool","choices":[{"delta":{"tool_calls":[{"index":0,'
            '"function":{"arguments":"{\\"path\\":\\"claude.html\\"}"}}]},'
            '"finish_reason":"tool_calls"}],"usage":{"prompt_tokens":50,"completion_tokens":10}}'
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
            "max_tokens": 1024,
            "stream": True,
            "tools": [
                {
                    "name": "Write",
                    "input_schema": {"type": "object"},
                }
            ],
            "messages": [{"role": "user", "content": "Create claude.html"}],
        },
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "event: message_start" in body
    assert '"type": "tool_use"' in body
    assert '"name": "Write"' in body
    assert '"partial_json"' in body
    assert '"stop_reason": "tool_use"' in body
    assert "event: message_stop" in body
