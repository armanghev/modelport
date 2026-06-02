from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_provider_routes_list_create_and_patch(client: TestClient) -> None:
    list_response = client.get("/admin/providers")
    assert list_response.status_code == 200
    assert any(provider["id"] == "openai" for provider in list_response.json())

    create_response = client.post(
        "/admin/providers",
        json={
            "id": "groq",
            "display_name": "Groq",
            "provider_type": "openai_compatible",
            "base_url": "https://api.groq.com/openai/v1",
        },
    )
    assert create_response.status_code == 201
    assert create_response.json()["id"] == "groq"

    patch_response = client.patch(
        "/admin/providers/groq",
        json={
            "display_name": "Groq Cloud",
            "enabled": False,
        },
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["display_name"] == "Groq Cloud"
    assert patch_response.json()["enabled"] is False


def test_credential_routes_mask_and_reveal(client: TestClient) -> None:
    env_credentials = client.get("/admin/provider-credentials")
    assert env_credentials.status_code == 200
    openai_credential = next(
        credential for credential in env_credentials.json() if credential["provider_id"] == "openai"
    )
    assert openai_credential["key_hint"] == "sk************ed"
    assert "api_key" not in openai_credential

    update_response = client.patch(
        f"/admin/provider-credentials/{openai_credential['id']}",
        json={"api_key": "sk-replaced-from-dashboard"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["source"] == "database"
    assert update_response.json()["api_key_env"] is None

    reveal_response = client.get(f"/admin/provider-credentials/{openai_credential['id']}/secret")
    assert reveal_response.status_code == 200
    assert reveal_response.json()["api_key"] == "sk-replaced-from-dashboard"


def test_model_alias_routes_create_and_patch(client: TestClient) -> None:
    create_response = client.post(
        "/admin/model-aliases",
        json={
            "alias": "fast",
            "provider_id": "openai",
            "model": "gpt-5.4-mini",
            "description": "Fast alias",
            "enabled": True,
        },
    )
    assert create_response.status_code == 201
    assert create_response.json()["alias"] == "fast"

    patch_response = client.patch(
        "/admin/model-aliases/fast",
        json={"description": "Updated fast alias", "is_default": True},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["description"] == "Updated fast alias"
    assert patch_response.json()["is_default"] is True


def test_routing_pricing_and_settings_routes(client: TestClient) -> None:
    routing_create = client.post(
        "/admin/routing-rules",
        json={
            "match": "gpt*",
            "priority": 10,
            "primary_provider_id": "openai",
            "primary_alias": "gpt",
            "fallback_provider_ids": ["openrouter"],
        },
    )
    assert routing_create.status_code == 201
    routing_id = routing_create.json()["id"]

    routing_patch = client.patch(f"/admin/routing-rules/{routing_id}", json={"enabled": False})
    assert routing_patch.status_code == 200
    assert routing_patch.json()["enabled"] is False

    pricing_create = client.post(
        "/admin/pricing",
        json={
            "provider_id": "openai",
            "model": "gpt-5.5",
            "input_per_1m_usd": 2.0,
            "output_per_1m_usd": 8.0,
            "currency": "USD",
        },
    )
    assert pricing_create.status_code == 201
    pricing_id = pricing_create.json()["id"]

    pricing_patch = client.patch(
        f"/admin/pricing/{pricing_id}",
        json={"output_per_1m_usd": 9.0},
    )
    assert pricing_patch.status_code == 200
    assert pricing_patch.json()["output_per_1m_usd"] == 9.0

    default_routing_patch = client.patch(
        "/admin/settings/default-routing",
        json={"provider": "openai", "model": "gpt"},
    )
    assert default_routing_patch.status_code == 200
    assert default_routing_patch.json()["provider"] == "openai"

    tracking_patch = client.patch(
        "/admin/settings/tracking",
        json={"request_logging": True, "cost_tracking": True, "retention_days": 14},
    )
    assert tracking_patch.status_code == 200
    assert tracking_patch.json()["retention_days"] == 14

    appearance_patch = client.patch(
        "/admin/settings/appearance",
        json={"theme": "system", "refresh_interval_seconds": 30},
    )
    assert appearance_patch.status_code == 200
    assert appearance_patch.json()["refresh_interval_seconds"] == 30

    settings_response = client.get("/admin/settings")
    assert settings_response.status_code == 200
    payload = settings_response.json()
    assert payload["settings"]["default_routing"]["provider"] == "openai"
    assert payload["settings"]["tracking"]["retention_days"] == 14
    assert payload["settings"]["appearance"]["theme"] == "system"


def test_invalid_provider_references_return_client_errors(client: TestClient) -> None:
    alias_response = client.post(
        "/admin/model-aliases",
        json={"alias": "broken", "provider_id": "missing", "model": "gpt-5.5"},
    )
    assert alias_response.status_code == 404

    routing_response = client.post(
        "/admin/routing-rules",
        json={
            "match": "broken*",
            "priority": 1,
            "primary_provider_id": "missing",
        },
    )
    assert routing_response.status_code == 404


def test_provider_health_endpoint_returns_dashboard_ready_cards(
    client: TestClient,
    monkeypatch,
) -> None:
    client.post(
        "/admin/routing-rules",
        json={
            "match": "gpt*",
            "priority": 10,
            "primary_provider_id": "openai",
            "primary_alias": "gpt",
            "fallback_provider_ids": ["openrouter"],
        },
    )

    def fake_collect_provider_health_payload(session):
        return {
            "cards": [
                {
                    "id": "openai",
                    "displayName": "OpenAI",
                    "type": "openai_compatible",
                    "status": "operational",
                    "baseUrl": "https://api.openai.com/v1",
                    "requestsToday": 0,
                    "successRate": 100.0,
                    "errorRate": 0.0,
                    "avgLatencyMs": 120,
                    "availableModelCount": 2,
                    "lastCheckedAt": "2026-06-02T12:00:00Z",
                    "lastError": None,
                },
                {
                    "id": "openrouter",
                    "displayName": "OpenRouter",
                    "type": "openai_compatible",
                    "status": "operational",
                    "baseUrl": "https://openrouter.ai/api/v1",
                    "requestsToday": 0,
                    "successRate": 100.0,
                    "errorRate": 0.0,
                    "avgLatencyMs": 150,
                    "availableModelCount": 1,
                    "lastCheckedAt": "2026-06-02T12:00:00Z",
                    "lastError": None,
                },
                {
                    "id": "ollama",
                    "displayName": "Ollama",
                    "type": "local_openai_compatible",
                    "status": "operational",
                    "baseUrl": "http://localhost:11434/v1",
                    "requestsToday": 0,
                    "successRate": 100.0,
                    "errorRate": 0.0,
                    "avgLatencyMs": 80,
                    "availableModelCount": 1,
                    "lastCheckedAt": "2026-06-02T12:00:00Z",
                    "lastError": None,
                },
            ],
            "routingRules": [
                {
                    "match": "gpt*",
                    "primaryProvider": "openai",
                    "fallbackProviders": ["openrouter"],
                }
            ],
            "details": [],
        }

    monkeypatch.setattr(
        "app.api.admin.collect_provider_health_payload",
        fake_collect_provider_health_payload,
    )

    health_response = client.get("/admin/providers/health")

    assert health_response.status_code == 200
    payload = health_response.json()
    assert payload["details"] == []
    assert payload["routingRules"] == [
        {
            "match": "gpt*",
            "primaryProvider": "openai",
            "fallbackProviders": ["openrouter"],
        }
    ]

    cards_by_id = {card["id"]: card for card in payload["cards"]}
    assert cards_by_id["openai"]["status"] == "operational"
    assert cards_by_id["openai"]["availableModelCount"] == 2
    assert cards_by_id["openai"]["successRate"] == 100.0
    assert cards_by_id["openrouter"]["availableModelCount"] == 1
    assert cards_by_id["ollama"]["availableModelCount"] == 1


def test_provider_health_endpoint_marks_unreachable_provider_offline(
    client: TestClient,
    monkeypatch,
) -> None:
    client.post(
        "/admin/providers",
        json={
            "id": "broken-local",
            "display_name": "Broken Local",
            "provider_type": "local_openai_compatible",
            "base_url": "http://localhost:9999/v1",
        },
    )

    def fake_collect_provider_health_payload(session):
        return {
            "cards": [
                {
                    "id": "broken-local",
                    "displayName": "Broken Local",
                    "type": "local_openai_compatible",
                    "status": "offline",
                    "baseUrl": "http://localhost:9999/v1",
                    "requestsToday": 0,
                    "successRate": 0.0,
                    "errorRate": 100.0,
                    "avgLatencyMs": 0,
                    "availableModelCount": 0,
                    "lastCheckedAt": "2026-06-02T12:00:00Z",
                    "lastError": "Connection refused",
                }
            ],
            "routingRules": [],
            "details": [],
        }

    monkeypatch.setattr(
        "app.api.admin.collect_provider_health_payload",
        fake_collect_provider_health_payload,
    )

    health_response = client.get("/admin/providers/health")

    assert health_response.status_code == 200
    cards_by_id = {card["id"]: card for card in health_response.json()["cards"]}
    assert cards_by_id["broken-local"]["status"] == "offline"
    assert "Connection refused" in cards_by_id["broken-local"]["lastError"]


def test_provider_health_allows_local_provider_without_api_key(
    client: TestClient,
    monkeypatch,
) -> None:
    import httpx

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"data": [{"id": "qwen2.5-coder"}]}

    class FakeHttpClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str, headers: dict | None = None):
            if "localhost:11434" in url:
                return FakeResponse()
            raise httpx.ConnectError("remote unavailable")

    monkeypatch.setattr("app.api.admin.httpx.Client", FakeHttpClient)

    health_response = client.get("/admin/providers/health")

    assert health_response.status_code == 200
    cards_by_id = {card["id"]: card for card in health_response.json()["cards"]}
    assert cards_by_id["ollama"]["status"] == "operational"
    assert cards_by_id["ollama"]["availableModelCount"] == 1


def test_provider_health_prefers_configured_enabled_credential(
    client: TestClient,
    monkeypatch,
) -> None:
    created_credential = client.post(
        "/admin/provider-credentials",
        json={
            "provider_id": "openai",
            "display_name": "OpenAI Primary",
            "source": "database",
            "api_key": "sk-configured-secret",
            "is_default": False,
            "enabled": True,
        },
    )
    assert created_credential.status_code == 201
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

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"data": [{"id": "gpt-4.1"}]}

    class FakeHttpClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str, headers: dict | None = None):
            headers = headers or {}
            if "api.openai.com" in url:
                assert headers.get("Authorization") == "Bearer sk-configured-secret"
            return FakeResponse()

    monkeypatch.setattr("app.api.admin.httpx.Client", FakeHttpClient)

    health_response = client.get("/admin/providers/health")

    assert health_response.status_code == 200
    cards_by_id = {card["id"]: card for card in health_response.json()["cards"]}
    assert cards_by_id["openai"]["status"] == "operational"
    assert cards_by_id["openai"]["availableModelCount"] == 1
