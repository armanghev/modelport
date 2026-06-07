from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient


def test_message_batches_create_route_proxies_anthropic_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: dict = {}

    def fake_create_message_batch(provider, api_key, payload):
        captured["provider_id"] = provider.id
        captured["api_key"] = api_key
        captured["payload"] = payload
        return {
            "id": "msgbatch_123",
            "type": "message_batch",
            "processing_status": "in_progress",
            "request_counts": {
                "processing": 1,
                "succeeded": 0,
                "errored": 0,
                "canceled": 0,
                "expired": 0,
            },
        }

    monkeypatch.setattr(
        "app.api.anthropic.create_message_batch",
        fake_create_message_batch,
    )

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
    assert captured["provider_id"] == "anthropic"
    assert captured["payload"] == {
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
    }
    assert response.json()["id"] == "msgbatch_123"


def test_message_batches_retrieve_route_proxies_anthropic_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    def fake_get_message_batch(provider, api_key, batch_id):
        assert provider.id == "anthropic"
        assert batch_id == "msgbatch_123"
        return {
            "id": "msgbatch_123",
            "type": "message_batch",
            "processing_status": "ended",
        }

    monkeypatch.setattr(
        "app.api.anthropic.get_message_batch",
        fake_get_message_batch,
    )

    response = client.get(
        "/v1/messages/batches/msgbatch_123",
        headers={
            "Authorization": "Bearer test-local-token",
            "X-ModelPort-Provider": "anthropic",
        },
    )

    assert response.status_code == 200
    assert response.json()["processing_status"] == "ended"


def test_message_batches_list_route_proxies_anthropic_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: dict = {}

    def fake_list_message_batches(provider, api_key, *, after_id=None, before_id=None, limit=None):
        captured.update(
            {
                "provider_id": provider.id,
                "after_id": after_id,
                "before_id": before_id,
                "limit": limit,
            }
        )
        return {
            "data": [{"id": "msgbatch_123", "type": "message_batch", "processing_status": "ended"}],
            "has_more": False,
        }

    monkeypatch.setattr(
        "app.api.anthropic.list_message_batches",
        fake_list_message_batches,
    )

    response = client.get(
        "/v1/messages/batches",
        headers={
            "Authorization": "Bearer test-local-token",
            "X-ModelPort-Provider": "anthropic",
        },
        params={"limit": 10},
    )

    assert response.status_code == 200
    assert captured["provider_id"] == "anthropic"
    assert captured["limit"] == 10
    assert response.json()["data"][0]["id"] == "msgbatch_123"


def test_message_batches_cancel_route_proxies_anthropic_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    def fake_cancel_message_batch(provider, api_key, batch_id):
        assert batch_id == "msgbatch_123"
        return {
            "id": "msgbatch_123",
            "type": "message_batch",
            "processing_status": "canceling",
        }

    monkeypatch.setattr(
        "app.api.anthropic.cancel_message_batch",
        fake_cancel_message_batch,
    )

    response = client.post(
        "/v1/messages/batches/msgbatch_123/cancel",
        headers={
            "Authorization": "Bearer test-local-token",
            "X-ModelPort-Provider": "anthropic",
        },
    )

    assert response.status_code == 200
    assert response.json()["processing_status"] == "canceling"


def test_message_batches_results_route_proxies_anthropic_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    result_line = json.dumps(
        {
            "custom_id": "job-1",
            "result": {"type": "succeeded", "message": {"id": "msg_123", "type": "message"}},
        }
    )

    def fake_get_message_batch_results(provider, api_key, batch_id):
        assert batch_id == "msgbatch_123"
        return result_line.encode("utf-8") + b"\n", "application/x-jsonlines"

    monkeypatch.setattr(
        "app.api.anthropic.get_message_batch_results",
        fake_get_message_batch_results,
    )

    response = client.get(
        "/v1/messages/batches/msgbatch_123/results",
        headers={
            "Authorization": "Bearer test-local-token",
            "X-ModelPort-Provider": "anthropic",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-jsonlines")
    assert json.loads(response.text.strip())["custom_id"] == "job-1"


def test_message_batches_create_route_rejects_openai_provider(
    client: TestClient,
) -> None:
    response = client.post(
        "/v1/messages/batches",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "openai",
            "requests": [
                {
                    "custom_id": "job-1",
                    "params": {
                        "model": "gpt-4.1",
                        "max_tokens": 64,
                        "messages": [{"role": "user", "content": "hello"}],
                    },
                }
            ],
        },
    )

    assert response.status_code == 501
