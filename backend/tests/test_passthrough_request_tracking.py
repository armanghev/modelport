from __future__ import annotations

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import ApiRequest, build_session_factory
from app.tracking.pricing import resolve_pricing_override

from tests.test_helpers import provider_uuid


def _api_request_records(app_config) -> list[ApiRequest]:
    session_factory = build_session_factory(f"sqlite:///{app_config.parent / 'test.db'}")
    with session_factory() as session:
        return session.scalars(select(ApiRequest).order_by(ApiRequest.created_at)).all()


def test_embeddings_route_persists_request_usage_and_cost(
    client: TestClient,
    app_config,
    monkeypatch,
) -> None:
    client.post(
        "/admin/pricing",
        json={
            "provider_id": provider_uuid(client, "openai"),
            "model": "text-embedding-3-small",
            "input_per_1m_usd": 1.0,
            "output_per_1m_usd": 0.0,
            "currency": "USD",
            "enabled": True,
        },
    )

    def fake_create_embedding(provider, api_key, payload):
        return {
            "object": "list",
            "data": [{"object": "embedding", "index": 0, "embedding": [0.1]}],
            "model": "text-embedding-3-small",
            "usage": {"prompt_tokens": 1000, "total_tokens": 1000},
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

    records = _api_request_records(app_config)
    assert len(records) == 1
    record = records[0]
    assert record.endpoint == "/v1/embeddings"
    assert record.provider == "openai"
    assert record.input_tokens == 1000
    assert record.estimated_cost_usd == 0.001
    assert record.pricing_source == "admin_override"


def test_image_generations_route_persists_request_log(
    client: TestClient,
    app_config,
    monkeypatch,
) -> None:
    def fake_create_image_generation(provider, api_key, payload):
        return {"created": 1, "data": [{"b64_json": "abc"}]}

    monkeypatch.setattr("app.api.openai.create_image_generation", fake_create_image_generation)

    response = client.post(
        "/v1/images/generations",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "openai",
            "model": "gpt-image-1",
            "prompt": "A lighthouse",
        },
    )
    assert response.status_code == 200

    record = _api_request_records(app_config)[0]
    assert record.endpoint == "/v1/images/generations"
    assert record.provider == "openai"
    assert record.requested_model == "gpt-image-1"
    assert record.estimated_cost_usd is None
    assert record.input_tokens == 0


def test_audio_transcriptions_route_persists_request_log(
    client: TestClient,
    app_config,
    monkeypatch,
) -> None:
    def fake_create_audio_transcription(provider, api_key, *, form_fields, files):
        return {"text": "hello world"}

    monkeypatch.setattr("app.api.openai.create_audio_transcription", fake_create_audio_transcription)

    response = client.post(
        "/v1/audio/transcriptions",
        headers={"Authorization": "Bearer test-local-token"},
        data={"provider": "openai", "model": "whisper-1"},
        files={"file": ("audio.wav", b"wav-bytes", "audio/wav")},
    )
    assert response.status_code == 200

    record = _api_request_records(app_config)[0]
    assert record.endpoint == "/v1/audio/transcriptions"
    assert record.provider == "openai"
    assert record.requested_model == "whisper-1"
    assert record.estimated_cost_usd is None


def test_moderations_route_persists_request_log(
    client: TestClient,
    app_config,
    monkeypatch,
) -> None:
    def fake_create_moderation(provider, api_key, payload):
        return {
            "id": "modr_123",
            "model": "omni-moderation-latest",
            "results": [{"flagged": False}],
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

    record = _api_request_records(app_config)[0]
    assert record.endpoint == "/v1/moderations"
    assert record.provider == "openai"
    assert record.request_id == "modr_123"


def test_responses_route_persists_non_stream_request_usage(
    client: TestClient,
    app_config,
    monkeypatch,
) -> None:
    client.post(
        "/admin/pricing",
        json={
            "provider_id": provider_uuid(client, "openai"),
            "model": "gpt-4.1",
            "input_per_1m_usd": 2.0,
            "output_per_1m_usd": 8.0,
            "currency": "USD",
            "enabled": True,
        },
    )

    def fake_create_response(provider, api_key, payload):
        return {
            "id": "resp_tracked_123",
            "object": "response",
            "status": "completed",
            "model": "gpt-4.1",
            "output": [],
            "usage": {"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500},
        }

    monkeypatch.setattr("app.api.openai.create_response", fake_create_response)

    response = client.post(
        "/v1/responses",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "openai",
            "model": "gpt-4.1",
            "input": "hello",
        },
    )
    assert response.status_code == 200

    record = _api_request_records(app_config)[0]
    assert record.endpoint == "/v1/responses"
    assert record.request_id == "resp_tracked_123"
    assert record.input_tokens == 1000
    assert record.output_tokens == 500
    assert record.estimated_cost_usd == 0.006


def test_responses_route_persists_stream_request_log(
    client: TestClient,
    app_config,
    monkeypatch,
) -> None:
    def fake_stream_response_events(provider, api_key, payload):
        yield "event: response.created\n"
        yield (
            'data: {"type":"response.created","response":{"id":"resp_stream_tracked",'
            '"status":"in_progress","model":"gpt-4.1","object":"response","output":[]}}\n'
        )
        yield "\n"
        yield "event: response.completed\n"
        yield (
            'data: {"type":"response.completed","response":{"id":"resp_stream_tracked",'
            '"status":"completed","model":"gpt-4.1","object":"response","output":[],'
            '"usage":{"input_tokens":200,"output_tokens":50,"total_tokens":250}}}\n'
        )
        yield "\n"

    monkeypatch.setattr("app.api.openai.stream_response_events", fake_stream_response_events)

    with client.stream(
        "POST",
        "/v1/responses",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "openai",
            "model": "gpt-4.1",
            "input": "hello",
            "stream": True,
        },
    ) as response:
        assert response.status_code == 200
        assert "".join(response.iter_text())

    record = _api_request_records(app_config)[0]
    assert record.endpoint == "/v1/responses"
    assert record.streamed is True
    assert record.request_id == "resp_stream_tracked"
    assert record.input_tokens == 200
    assert record.output_tokens == 50


def test_count_tokens_route_persists_request_log(
    client: TestClient,
    app_config,
    monkeypatch,
) -> None:
    def fake_count_message_tokens(provider, api_key, payload):
        return {"input_tokens": 42}

    monkeypatch.setattr("app.api.anthropic.count_message_tokens", fake_count_message_tokens)

    response = client.post(
        "/v1/messages/count_tokens",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "anthropic",
            "model": "claude-sonnet-4-5",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    assert response.status_code == 200

    record = _api_request_records(app_config)[0]
    assert record.endpoint == "/v1/messages/count_tokens"
    assert record.provider == "anthropic"
    assert record.requested_model == "claude-sonnet-4-5"


def test_message_batches_route_persists_request_log(
    client: TestClient,
    app_config,
    monkeypatch,
) -> None:
    def fake_create_message_batch(provider, api_key, payload):
        return {
            "id": "msgbatch_tracked",
            "type": "message_batch",
            "processing_status": "in_progress",
        }

    monkeypatch.setattr("app.api.anthropic.create_message_batch", fake_create_message_batch)

    response = client.post(
        "/v1/messages/batches",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "anthropic",
            "requests": [
                {
                    "custom_id": "job-1",
                    "params": {
                        "model": "claude-sonnet-4-5",
                        "max_tokens": 64,
                        "messages": [{"role": "user", "content": "hello"}],
                    },
                }
            ],
        },
    )
    assert response.status_code == 200

    record = _api_request_records(app_config)[0]
    assert record.endpoint == "/v1/messages/batches"
    assert record.provider == "anthropic"
    assert record.request_id == "msgbatch_tracked"


def test_files_upload_route_persists_request_log(
    client: TestClient,
    app_config,
    monkeypatch,
) -> None:
    def fake_create_file(provider, api_key, *, filename, content, content_type):
        return {
            "id": "file_tracked",
            "type": "file",
            "filename": filename,
            "mime_type": content_type,
            "size_bytes": len(content),
        }

    monkeypatch.setattr("app.api.anthropic.create_file", fake_create_file)

    response = client.post(
        "/v1/files",
        headers={"Authorization": "Bearer test-local-token"},
        data={"provider": "anthropic"},
        files={"file": ("document.pdf", b"pdf-bytes", "application/pdf")},
    )
    assert response.status_code == 200

    record = _api_request_records(app_config)[0]
    assert record.endpoint == "/v1/files"
    assert record.provider == "anthropic"
    assert record.request_id == "file_tracked"


def test_embeddings_route_persists_failed_upstream_request(
    client: TestClient,
    app_config,
    monkeypatch,
) -> None:
    def fake_create_embedding(provider, api_key, payload):
        raise HTTPException(status_code=502, detail="Upstream provider request failed: boom")

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
    assert response.status_code == 502

    record = _api_request_records(app_config)[0]
    assert record.endpoint == "/v1/embeddings"
    assert record.status_code == 502
    assert record.error_message == "Upstream provider request failed: boom"
    assert record.input_tokens == 0


def test_live_pricing_lookup_resolves_models_prefix_variant(client: TestClient) -> None:
    client.post(
        "/admin/pricing",
        json={
            "provider_id": provider_uuid(client, "gemini"),
            "model": "gemini-2.5-flash",
            "input_per_1m_usd": 1.0,
            "output_per_1m_usd": 2.0,
            "currency": "USD",
            "enabled": True,
        },
    )

    session_factory = client.app.state.session_factory
    with session_factory() as session:
        pricing = resolve_pricing_override(
            session,
            provider_id="gemini",
            resolved_model="models/gemini-2.5-flash",
            requested_model="models/gemini-2.5-flash",
        )

    assert pricing is not None
    assert pricing.model == "gemini-2.5-flash"
