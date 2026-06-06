from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from app.database import Provider, ProviderCredential, build_session_factory
from app.main import create_app


def test_startup_seeds_providers_and_credentials(client: TestClient) -> None:
    settings_response = client.get("/admin/settings")

    assert settings_response.status_code == 200
    payload = settings_response.json()

    assert {provider["id"] for provider in payload["providers"]} == {
        "anthropic",
        "gemini",
        "openai",
        "openrouter",
        "ollama",
    }
    assert any(
        credential["provider_id"] == "openai"
        and credential["source"] == "env"
        and credential["api_key_env"] == "OPENAI_API_KEY"
        for credential in payload["provider_credentials"]
    )
    assert "model_aliases" not in payload
    assert "routing_rules" not in payload


def test_seed_is_idempotent(app_config: Path, encryption_key: str) -> None:
    previous_encryption = os.environ.get("PROXY_ENCRYPTION_KEY")
    previous_openai = os.environ.get("OPENAI_API_KEY")
    previous_openrouter = os.environ.get("OPENROUTER_API_KEY")
    previous_anthropic = os.environ.get("ANTHROPIC_API_KEY")
    previous_gemini = os.environ.get("GEMINI_API_KEY")
    os.environ["PROXY_ENCRYPTION_KEY"] = encryption_key
    os.environ["OPENAI_API_KEY"] = "sk-openai-seeded"
    os.environ["OPENROUTER_API_KEY"] = "sk-openrouter-seeded"
    os.environ["ANTHROPIC_API_KEY"] = "sk-anthropic-seeded"
    os.environ["GEMINI_API_KEY"] = "sk-gemini-seeded"

    app = create_app(config_path=app_config)
    with TestClient(app):
        pass
    with TestClient(app):
        pass

    session_factory = build_session_factory(f"sqlite:///{app_config.parent / 'test.db'}")
    with session_factory() as session:
        assert session.query(Provider).count() == 5
        assert session.query(ProviderCredential).count() == 4

    if previous_encryption is None:
        os.environ.pop("PROXY_ENCRYPTION_KEY", None)
    else:
        os.environ["PROXY_ENCRYPTION_KEY"] = previous_encryption
    if previous_openai is None:
        os.environ.pop("OPENAI_API_KEY", None)
    else:
        os.environ["OPENAI_API_KEY"] = previous_openai
    if previous_openrouter is None:
        os.environ.pop("OPENROUTER_API_KEY", None)
    else:
        os.environ["OPENROUTER_API_KEY"] = previous_openrouter
    if previous_anthropic is None:
        os.environ.pop("ANTHROPIC_API_KEY", None)
    else:
        os.environ["ANTHROPIC_API_KEY"] = previous_anthropic
    if previous_gemini is None:
        os.environ.pop("GEMINI_API_KEY", None)
    else:
        os.environ["GEMINI_API_KEY"] = previous_gemini


def test_database_credentials_are_encrypted_and_revealed_explicitly(client: TestClient, app_config: Path) -> None:
    create_response = client.post(
        "/admin/provider-credentials",
        json={
            "provider_id": "openai",
            "display_name": "OpenAI Personal",
            "source": "database",
            "api_key": "sk-secret-value",
            "is_default": False,
            "enabled": True,
        },
    )

    assert create_response.status_code == 201
    credential_id = create_response.json()["id"]

    session_factory = build_session_factory(f"sqlite:///{app_config.parent / 'test.db'}")
    with session_factory() as session:
        record = session.get(ProviderCredential, credential_id)
        assert record is not None
        assert record.encrypted_api_key != "sk-secret-value"
        assert "sk-secret-value" not in record.encrypted_api_key

    reveal_response = client.get(f"/admin/provider-credentials/{credential_id}/secret")
    assert reveal_response.status_code == 200
    assert reveal_response.json()["api_key"] == "sk-secret-value"


def test_database_credentials_require_encryption_key(app_config: Path) -> None:
    os.environ.pop("PROXY_ENCRYPTION_KEY", None)
    os.environ["OPENAI_API_KEY"] = "sk-openai-seeded"
    os.environ["OPENROUTER_API_KEY"] = "sk-openrouter-seeded"
    app = create_app(config_path=app_config)

    with TestClient(app) as client:
        create_response = client.post(
            "/admin/provider-credentials",
            json={
                "provider_id": "openai",
                "display_name": "Broken Credential",
                "source": "database",
                "api_key": "sk-secret-value",
            },
        )

    assert create_response.status_code == 400
    assert "PROXY_ENCRYPTION_KEY" in create_response.json()["detail"]
