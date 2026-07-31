from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient
from app.database import ApiRequest, ProviderHealthCheck

from tests.test_helpers import cards_by_slug, provider_uuid


def test_provider_routes_list_create_and_patch(client: TestClient) -> None:
    list_response = client.get("/admin/providers")
    assert list_response.status_code == 200
    assert any(provider["slug"] == "openai" for provider in list_response.json())

    create_response = client.post(
        "/admin/providers",
        json={
            "slug": "groq",
            "display_name": "Groq",
            "provider_type": "openai_compatible",
            "base_url": "https://api.groq.com/openai/v1",
            "api_key": "sk-groq-secret",
            "credential_name": "Groq Default",
        },
    )
    assert create_response.status_code == 201
    assert create_response.json()["slug"] == "groq"
    groq_uuid = create_response.json()["id"]

    patch_response = client.patch(
        f"/admin/providers/{groq_uuid}",
        json={
            "display_name": "Groq Cloud",
            "enabled": False,
        },
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["display_name"] == "Groq Cloud"
    assert patch_response.json()["enabled"] is False


def test_provider_list_includes_latest_health_state(client: TestClient) -> None:
    session_factory = client.app.state.session_factory
    with session_factory() as session:
        session.add(
            ProviderHealthCheck(
                provider_id=provider_uuid(client, "openai"),
                status="degraded",
                latency_ms=321,
                available_model_count=7,
                error_message="rate limited",
                checked_at=datetime.now(UTC),
            )
        )
        session.commit()

    list_response = client.get("/admin/providers")

    assert list_response.status_code == 200
    openai_provider = next(provider for provider in list_response.json() if provider["slug"] == "openai")
    assert openai_provider["health_status"] == "degraded"
    assert openai_provider["last_error"] == "rate limited"
    assert openai_provider["last_checked_at"] is not None


def test_provider_delete_removes_provider_without_credentials(client: TestClient) -> None:
    create_provider_response = client.post(
        "/admin/providers",
        json={
            "slug": "mock-local",
            "display_name": "Mock Local",
            "provider_type": "openai_compatible",
            "base_url": "http://127.0.0.1:8011/v1",
        },
    )
    assert create_provider_response.status_code == 201
    provider_id = create_provider_response.json()["id"]

    delete_response = client.delete(f"/admin/providers/{provider_id}")
    assert delete_response.status_code == 204

    providers_response = client.get("/admin/providers")
    assert all(provider["slug"] != "mock-local" for provider in providers_response.json())


def test_credential_delete_removes_credential_and_orphaned_provider(client: TestClient) -> None:
    create_provider_response = client.post(
        "/admin/providers",
        json={
            "slug": "tempprovider",
            "display_name": "Temp Provider",
            "provider_type": "openai_compatible",
            "base_url": "https://api.example.com/v1",
            "api_key": "sk-temp-secret",
            "credential_name": "Temp Credential",
        },
    )
    assert create_provider_response.status_code == 201
    temp_uuid = create_provider_response.json()["id"]
    credential_id = next(
        credential["id"]
        for credential in client.get("/admin/provider-credentials").json()
        if credential["provider_id"] == temp_uuid
    )

    delete_response = client.delete(f"/admin/provider-credentials/{credential_id}")
    assert delete_response.status_code == 204

    providers_response = client.get("/admin/providers")
    assert all(provider["slug"] != "tempprovider" for provider in providers_response.json())

    credentials_response = client.get("/admin/provider-credentials")
    assert all(credential["id"] != credential_id for credential in credentials_response.json())


def test_credential_delete_keeps_provider_when_other_credentials_remain(client: TestClient) -> None:
    openai_uuid = provider_uuid(client, "openai")
    primary_credential = client.post(
        "/admin/provider-credentials",
        json={
            "provider_id": openai_uuid,
            "display_name": "OpenAI Backup",
            "api_key": "sk-backup-secret",
            "is_default": False,
            "enabled": True,
        },
    )
    assert primary_credential.status_code == 201
    backup_credential_id = primary_credential.json()["id"]

    credentials_response = client.get("/admin/provider-credentials")
    default_openai_credential = next(
        credential
        for credential in credentials_response.json()
        if credential["provider_id"] == openai_uuid and credential["is_default"]
    )

    delete_response = client.delete(
        f"/admin/provider-credentials/{default_openai_credential['id']}",
    )
    assert delete_response.status_code == 204

    providers_response = client.get("/admin/providers")
    assert any(provider["slug"] == "openai" for provider in providers_response.json())

    remaining_credentials = client.get("/admin/provider-credentials").json()
    openai_credentials = [
        credential for credential in remaining_credentials if credential["provider_id"] == openai_uuid
    ]
    assert len(openai_credentials) == 1
    assert openai_credentials[0]["id"] == backup_credential_id
    assert openai_credentials[0]["is_default"] is True


def test_credential_routes_mask_and_reveal(client: TestClient) -> None:
    env_credentials = client.get("/admin/provider-credentials")
    assert env_credentials.status_code == 200
    openai_uuid = provider_uuid(client, "openai")
    openai_credential = next(
        credential for credential in env_credentials.json() if credential["provider_id"] == openai_uuid
    )
    assert openai_credential["key_hint"] == "sk************ed"
    assert "api_key" not in openai_credential

    update_response = client.patch(
        f"/admin/provider-credentials/{openai_credential['id']}",
        json={"api_key": "sk-replaced-from-dashboard"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["configured"] is True

    reveal_response = client.get(f"/admin/provider-credentials/{openai_credential['id']}/secret")
    assert reveal_response.status_code == 200
    assert reveal_response.json()["api_key"] == "sk-replaced-from-dashboard"


def test_settings_excludes_manual_pricing_configuration(client: TestClient) -> None:
    tracking_patch = client.patch(
        "/admin/settings/tracking",
        json={"io_logging": True, "retention_days": 14},
    )
    assert tracking_patch.status_code == 200
    assert tracking_patch.json()["retention_days"] == 14
    assert tracking_patch.json()["io_logging"] is True

    appearance_patch = client.patch(
        "/admin/settings/appearance",
        json={"theme": "system", "refresh_interval_seconds": 30},
    )
    assert appearance_patch.status_code == 200
    assert appearance_patch.json()["refresh_interval_seconds"] == 30

    settings_response = client.get("/admin/settings")
    assert settings_response.status_code == 200
    payload = settings_response.json()
    assert "model_aliases" not in payload
    assert "routing_rules" not in payload
    assert "pricing_overrides" not in payload
    assert "default_routing" not in payload["settings"]
    assert payload["settings"]["tracking"]["retention_days"] == 14
    assert payload["settings"]["appearance"]["theme"] == "system"
    assert client.get("/admin/pricing").status_code == 404


def test_provider_health_endpoint_returns_dashboard_ready_cards(
    client: TestClient,
    monkeypatch,
) -> None:
    def fake_collect_provider_health_payload(session):
        return {
            "cards": [
                {
                    "id": "uuid-openai",
                    "slug": "openai",
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
                    "id": "uuid-openrouter",
                    "slug": "openrouter",
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
                    "id": "uuid-ollama",
                    "slug": "ollama",
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
    assert "routingRules" not in payload

    cards = cards_by_slug(payload["cards"])
    assert cards["openai"]["status"] == "operational"
    assert cards["openai"]["availableModelCount"] == 2
    assert cards["openai"]["successRate"] == 100.0
    assert cards["openrouter"]["availableModelCount"] == 1
    assert cards["ollama"]["availableModelCount"] == 1


def test_provider_health_endpoint_marks_unreachable_provider_offline(
    client: TestClient,
    monkeypatch,
) -> None:
    client.post(
        "/admin/providers",
        json={
            "slug": "brokenlocal",
            "display_name": "Broken Local",
            "provider_type": "local_openai_compatible",
            "base_url": "http://localhost:9999/v1",
            "api_key": "unused",
        },
    )

    def fake_collect_provider_health_payload(session):
        return {
            "cards": [
                {
                    "id": "uuid-brokenlocal",
                    "slug": "brokenlocal",
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
            "details": [],
        }

    monkeypatch.setattr(
        "app.api.admin.collect_provider_health_payload",
        fake_collect_provider_health_payload,
    )

    health_response = client.get("/admin/providers/health")

    assert health_response.status_code == 200
    cards = cards_by_slug(health_response.json()["cards"])
    assert cards["brokenlocal"]["status"] == "offline"
    assert "Connection refused" in cards["brokenlocal"]["lastError"]


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

        def get(self, url: str, headers: dict | None = None, **kwargs):
            if "localhost:11434" in url:
                return FakeResponse()
            raise httpx.ConnectError("remote unavailable")

    monkeypatch.setattr("app.api.admin.httpx.Client", FakeHttpClient)

    health_response = client.get("/admin/providers/health")

    assert health_response.status_code == 200
    cards = cards_by_slug(health_response.json()["cards"])
    assert cards["ollama"]["status"] == "operational"
    assert cards["ollama"]["availableModelCount"] == 1


def test_provider_health_prefers_configured_enabled_credential(
    client: TestClient,
    monkeypatch,
) -> None:
    openai_uuid = provider_uuid(client, "openai")
    created_credential = client.post(
        "/admin/provider-credentials",
        json={
            "provider_id": openai_uuid,
            "display_name": "OpenAI Primary",
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
        if credential["provider_id"] == openai_uuid and credential["is_default"]
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

        def get(self, url: str, headers: dict | None = None, **kwargs):
            headers = headers or {}
            if "api.openai.com" in url:
                assert headers.get("Authorization") == "Bearer sk-configured-secret"
            return FakeResponse()

    monkeypatch.setattr("app.api.admin.httpx.Client", FakeHttpClient)

    health_response = client.get("/admin/providers/health")

    assert health_response.status_code == 200
    cards = cards_by_slug(health_response.json()["cards"])
    assert cards["openai"]["status"] == "operational"
    assert cards["openai"]["availableModelCount"] == 1


def test_provider_health_uses_anthropic_models_endpoint_and_headers(
    client: TestClient,
    monkeypatch,
) -> None:
    import httpx

    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    class FakeHttpClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str, headers: dict | None = None, **kwargs):
            headers = headers or {}
            if "api.anthropic.com" in url:
                assert url == "https://api.anthropic.com/v1/models"
                assert headers.get("x-api-key") == "sk-anthropic-seeded"
                assert headers.get("anthropic-version") == "2023-06-01"
                return FakeResponse(
                    {
                        "data": [
                            {
                                "id": "claude-sonnet-4-5-20250929",
                                "display_name": "Claude Sonnet 4.5",
                            }
                        ]
                    }
                )
            raise httpx.ConnectError("provider unavailable")

    monkeypatch.setattr("app.api.admin.httpx.Client", FakeHttpClient)

    health_response = client.get("/admin/providers/health")

    assert health_response.status_code == 200
    cards = cards_by_slug(health_response.json()["cards"])
    assert cards["anthropic"]["status"] == "operational"
    assert cards["anthropic"]["availableModelCount"] == 1


def test_provider_models_endpoint_returns_live_models_for_healthy_providers_only(
    client: TestClient,
    monkeypatch,
) -> None:
    import httpx

    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    class FakeHttpClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str, headers: dict | None = None, **kwargs):
            headers = headers or {}
            if "api.openai.com" in url:
                assert headers.get("Authorization") == "Bearer sk-openai-seeded"
                return FakeResponse(
                    {
                        "data": [
                            {"id": "gpt-4.1", "owned_by": "openai"},
                            {"id": "gpt-4.1-mini", "owned_by": "openai"},
                        ]
                    }
                )
            if "localhost:11434" in url:
                return FakeResponse(
                    {
                        "data": [
                            {"id": "qwen2.5-coder:latest", "owned_by": "ollama"},
                        ]
                    }
                )
            raise httpx.ConnectError("provider unavailable")

    monkeypatch.setattr("app.api.admin.httpx.Client", FakeHttpClient)

    response = client.get("/admin/providers/models")

    assert response.status_code == 200
    payload = response.json()
    providers = {entry["provider_id"]: entry for entry in payload["providers"]}
    assert set(providers) == {"openai", "ollama"}
    assert providers["openai"]["available_model_count"] == 2
    assert providers["openai"]["models"][0]["id"] == "gpt-4.1"
    assert providers["openai"]["models"][0]["metadata_source"] in {
        "openrouter",
        "pricing",
        "unknown",
    }
    assert providers["openai"]["status"] == "operational"
    assert "totals" in payload
    assert payload["totals"]["live_model_count"] == 3
    assert providers["ollama"]["available_model_count"] == 1
    assert providers["ollama"]["models"][0]["id"] == "qwen2.5-coder:latest"


def test_model_catalog_returns_paginated_provider_models(
    client: TestClient,
    monkeypatch,
) -> None:
    import httpx

    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    class FakeHttpClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str, headers: dict | None = None, **kwargs):
            headers = headers or {}
            if "api.openai.com" in url:
                assert headers.get("Authorization") == "Bearer sk-openai-seeded"
                return FakeResponse(
                    {
                        "data": [
                            {"id": "gpt-4.1", "owned_by": "openai"},
                            {"id": "gpt-4.1-mini", "owned_by": "openai"},
                        ]
                    }
                )
            if "localhost:11434" in url:
                return FakeResponse(
                    {
                        "data": [
                            {"id": "qwen2.5-coder:latest", "owned_by": "ollama"},
                        ]
                    }
                )
            raise httpx.ConnectError("provider unavailable")

    monkeypatch.setattr("app.api.admin.httpx.Client", FakeHttpClient)

    response = client.get("/admin/model-catalog?page=1&page_size=1&provider=openai")

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"] == {
        "page": 1,
        "page_size": 1,
        "total_items": 2,
        "total_pages": 2,
    }
    assert payload["totals"]["live_model_count"] == 2
    assert payload["totals"]["provider_count"] == 1
    assert {"value": "openai", "label": "OpenAI", "count": 2} in payload["facets"]["providers"]
    assert {"value": "openai", "label": "openai", "count": 2} in payload["facets"]["owners"]
    assert payload["items"][0]["provider_id"] == "openai"
    assert payload["items"][0]["model"]["id"] == "gpt-4.1"


def test_model_catalog_filters_sorts_and_paginates_enriched_models(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.model_metadata_service import parse_openrouter_model

    catalog = {
        "openai": [
            {"id": "gpt-4.1", "display_name": "GPT 4.1", "owned_by": "openai"},
            {"id": "gpt-4.1-mini", "display_name": "GPT Mini", "owned_by": "openai"},
        ],
        "openrouter": [
            {
                "id": "meta/mini-free",
                "display_name": "Mini Free",
                "owned_by": "meta",
                "openrouter_metadata": parse_openrouter_model(
                    {
                        "id": "meta/mini-free",
                        "name": "Mini Free",
                        "description": "A miniature free model",
                        "context_length": 128000,
                        "architecture": {
                            "input_modalities": ["text"],
                            "output_modalities": ["text"],
                        },
                        "supported_parameters": ["tools"],
                        "pricing": {"prompt": "0", "completion": "0"},
                    }
                ),
            },
            {
                "id": "meta/large-paid",
                "display_name": "Large Paid",
                "owned_by": "meta",
                "openrouter_metadata": parse_openrouter_model(
                    {
                        "id": "meta/large-paid",
                        "name": "Large Paid",
                        "description": "A premium image model",
                        "context_length": 1_000_000,
                        "architecture": {
                            "input_modalities": ["text", "image"],
                            "output_modalities": ["text"],
                        },
                        "supported_parameters": ["tools", "reasoning"],
                        "pricing": {"prompt": "0.000002", "completion": "0.000004"},
                    }
                ),
            },
            {
                "id": "meta/mid-context",
                "display_name": "Mid Context",
                "owned_by": "meta",
                "openrouter_metadata": parse_openrouter_model(
                    {
                        "id": "meta/mid-context",
                        "name": "Mid Context",
                        "context_length": 200000,
                        "architecture": {
                            "input_modalities": ["audio"],
                            "output_modalities": ["text"],
                        },
                        "supported_parameters": ["json"],
                        "pricing": {"prompt": "0", "completion": "0"},
                    }
                ),
            },
        ],
        "ollama": [{"id": "qwen2.5-coder:latest", "owned_by": "ollama"}],
    }

    def fake_fetch(provider, secret):
        return catalog.get(provider.slug, []), 1

    monkeypatch.setattr("app.api.admin.ensure_openrouter_metadata_fresh", lambda session: None)
    monkeypatch.setattr("app.api.admin.fetch_provider_models_from_upstream", fake_fetch)
    monkeypatch.setattr(
        "app.api.admin.record_provider_health_check",
        lambda *args, **kwargs: SimpleNamespace(checked_at=datetime(2026, 7, 31, tzinfo=UTC)),
    )
    session_factory = client.app.state.session_factory
    with session_factory() as session:
        session.add(
            ApiRequest(
                input_format="chat_completions",
                output_format="chat_completions",
                endpoint="/v1/chat/completions",
                provider="openrouter",
                resolved_model="meta/large-paid",
                total_tokens=10,
            )
        )
        session.commit()

    mini = client.get("/admin/model-catalog?q=mini")
    assert mini.status_code == 200
    assert [item["model"]["id"] for item in mini.json()["items"]] == ["gpt-4.1-mini", "meta/mini-free"]

    repeated_provider = client.get("/admin/model-catalog?provider=ollama&provider=openai")
    assert repeated_provider.status_code == 200
    assert {item["provider_id"] for item in repeated_provider.json()["items"]} == {"ollama", "openai"}

    owner = client.get("/admin/model-catalog?owner=openai")
    assert owner.status_code == 200
    assert {item["model"]["id"] for item in owner.json()["items"]} == {"gpt-4.1", "gpt-4.1-mini"}
    repeated_owner = client.get("/admin/model-catalog?owner=openai&owner=meta")
    assert {item["model"]["owned_by"] for item in repeated_owner.json()["items"]} == {"openai", "meta"}

    assert [item["model"]["id"] for item in client.get("/admin/model-catalog?modality=image").json()["items"]] == ["meta/large-paid"]
    assert [item["model"]["id"] for item in client.get("/admin/model-catalog?capability=reasoning").json()["items"]] == ["meta/large-paid"]
    assert {item["model"]["id"] for item in client.get("/admin/model-catalog?price_tier=free").json()["items"]} == {"meta/mini-free", "meta/mid-context"}
    assert {item["model"]["id"] for item in client.get("/admin/model-catalog?price_tier=paid").json()["items"]} == {"meta/mini-free", "meta/mid-context", "meta/large-paid"}
    assert [item["model"]["id"] for item in client.get("/admin/model-catalog?usage=used").json()["items"]] == ["meta/large-paid"]
    assert {item["model"]["id"] for item in client.get("/admin/model-catalog?usage=unused").json()["items"]} == {"gpt-4.1", "gpt-4.1-mini", "meta/mini-free", "meta/mid-context", "qwen2.5-coder:latest"}
    assert [item["model"]["id"] for item in client.get("/admin/model-catalog?context=128k").json()["items"]] == ["meta/mini-free"]
    assert [item["model"]["id"] for item in client.get("/admin/model-catalog?context=200k").json()["items"]] == ["meta/mid-context"]
    assert [item["model"]["id"] for item in client.get("/admin/model-catalog?context=1m").json()["items"]] == ["meta/large-paid"]

    by_name = client.get("/admin/model-catalog?sort=name")
    by_provider = client.get("/admin/model-catalog?sort=provider")
    by_usage = client.get("/admin/model-catalog?sort=usage")
    by_context = client.get("/admin/model-catalog?sort=context")
    by_price = client.get("/admin/model-catalog?sort=price")
    by_fetched = client.get("/admin/model-catalog?sort=fetched")
    assert [item["model"]["id"] for item in by_name.json()["items"]] == ["gpt-4.1", "gpt-4.1-mini", "meta/large-paid", "meta/mid-context", "meta/mini-free", "qwen2.5-coder:latest"]
    assert [item["provider_id"] for item in by_provider.json()["items"]] == ["ollama", "openai", "openai", "openrouter", "openrouter", "openrouter"]
    assert [item["model"]["id"] for item in by_usage.json()["items"]] == ["meta/large-paid", "qwen2.5-coder:latest", "gpt-4.1", "gpt-4.1-mini", "meta/mid-context", "meta/mini-free"]
    assert [item["model"]["id"] for item in by_context.json()["items"]] == ["meta/mini-free", "meta/mid-context", "meta/large-paid", "qwen2.5-coder:latest", "gpt-4.1", "gpt-4.1-mini"]
    assert [item["model"]["id"] for item in by_price.json()["items"]] == ["meta/mid-context", "meta/mini-free", "meta/large-paid", "qwen2.5-coder:latest", "gpt-4.1", "gpt-4.1-mini"]
    assert [item["model"]["id"] for item in by_fetched.json()["items"]] == ["qwen2.5-coder:latest", "gpt-4.1", "gpt-4.1-mini", "meta/large-paid", "meta/mid-context", "meta/mini-free"]

    detail = client.get("/admin/model-catalog/openai/gpt-4.1")
    assert detail.status_code == 200
    assert detail.json()["provider_id"] == "openai"
    assert detail.json()["model"]["id"] == "gpt-4.1"
    missing = client.get("/admin/model-catalog/openai/not-a-model")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Model not found in the current healthy provider catalogs."

    beyond_end = client.get("/admin/model-catalog?page=99&page_size=2")
    assert beyond_end.status_code == 200
    assert beyond_end.json()["items"] == []
    assert beyond_end.json()["pagination"] == {"page": 99, "page_size": 2, "total_items": 6, "total_pages": 3}


def test_model_catalog_rejects_invalid_pagination(client: TestClient) -> None:
    assert client.get("/admin/model-catalog?page=0").status_code == 422
    assert client.get("/admin/model-catalog?page_size=0").status_code == 422
    assert client.get("/admin/model-catalog?page_size=101").status_code == 422
    assert client.get("/admin/model-catalog?price_tier=unknown").status_code == 422
    assert client.get("/admin/model-catalog?usage=maybe").status_code == 422
    assert client.get("/admin/model-catalog?context=64k").status_code == 422
    assert client.get("/admin/model-catalog?sort=random").status_code == 422


def test_model_catalog_context_buckets_require_positive_context_length() -> None:
    from app.api.admin import _catalog_context_bucket

    assert _catalog_context_bucket(0) is None
    assert _catalog_context_bucket(-1) is None


def test_provider_models_endpoint_includes_anthropic_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    import httpx

    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    class FakeHttpClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str, headers: dict | None = None, **kwargs):
            headers = headers or {}
            if "api.anthropic.com" in url:
                assert url == "https://api.anthropic.com/v1/models"
                assert headers.get("x-api-key") == "sk-anthropic-seeded"
                assert headers.get("anthropic-version") == "2023-06-01"
                return FakeResponse(
                    {
                        "data": [
                            {
                                "id": "claude-sonnet-4-5-20250929",
                                "display_name": "Claude Sonnet 4.5",
                            }
                        ]
                    }
                )
            raise httpx.ConnectError("provider unavailable")

    monkeypatch.setattr("app.api.admin.httpx.Client", FakeHttpClient)

    response = client.get("/admin/providers/models")

    assert response.status_code == 200
    payload = response.json()
    providers = {entry["provider_id"]: entry for entry in payload["providers"]}
    assert set(providers) == {"anthropic"}
    assert providers["anthropic"]["status"] == "operational"
    assert providers["anthropic"]["available_model_count"] == 1
    assert providers["anthropic"]["models"][0]["id"] == "claude-sonnet-4-5-20250929"
