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
