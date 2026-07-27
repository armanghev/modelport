from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from app.database import AppSetting, Provider, ProviderCredential, build_session_factory
from app.main import create_app


def test_startup_does_not_seed_providers(bare_client: TestClient) -> None:
    settings_response = bare_client.get("/admin/settings")

    assert settings_response.status_code == 200
    payload = settings_response.json()

    assert payload["providers"] == []
    assert payload["provider_credentials"] == []
    assert "model_aliases" not in payload
    assert "routing_rules" not in payload


def test_startup_seeds_default_settings_only(bare_client: TestClient, app_config: Path) -> None:
    settings_response = bare_client.get("/admin/settings")
    assert settings_response.status_code == 200
    payload = settings_response.json()
    assert payload["settings"]["tracking"]["io_logging"] is False
    assert payload["settings"]["appearance"]["theme"] == "system"

    session_factory = build_session_factory(f"sqlite:///{app_config.parent / 'test.db'}")
    with session_factory() as session:
        assert session.query(Provider).count() == 0
        assert session.query(ProviderCredential).count() == 0
        assert session.get(AppSetting, "tracking") is not None
        assert session.get(AppSetting, "appearance") is not None


def test_provider_presets_endpoint_reads_config_yaml(bare_client: TestClient) -> None:
    response = bare_client.get("/admin/provider-presets")

    assert response.status_code == 200
    presets = {preset["slug"]: preset for preset in response.json()}
    assert set(presets) == {"anthropic", "gemini", "openai", "openrouter", "ollama"}
    assert presets["anthropic"]["protocol"] == "anthropic"
    assert presets["openai"]["protocol"] == "openai"
    assert presets["openai"]["base_url"] == "https://api.openai.com/v1"


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
        assert session.query(Provider).count() == 0
        assert session.query(ProviderCredential).count() == 0

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


def test_database_credentials_are_encrypted_and_revealed_explicitly(bare_client: TestClient, app_config: Path) -> None:
    create_provider_response = bare_client.post(
        "/admin/providers",
        json={
            "slug": "openai",
            "display_name": "OpenAI",
            "provider_type": "openai_compatible",
            "base_url": "https://api.openai.com/v1",
        },
    )
    assert create_provider_response.status_code == 201
    openai_uuid = create_provider_response.json()["id"]

    create_response = bare_client.post(
        "/admin/provider-credentials",
        json={
            "provider_id": openai_uuid,
            "display_name": "OpenAI Personal",
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

    reveal_response = bare_client.get(f"/admin/provider-credentials/{credential_id}/secret")
    assert reveal_response.status_code == 200
    assert reveal_response.json()["api_key"] == "sk-secret-value"


def test_database_credentials_require_encryption_key(app_config: Path) -> None:
    os.environ.pop("PROXY_ENCRYPTION_KEY", None)
    os.environ["OPENAI_API_KEY"] = "sk-openai-seeded"
    os.environ["OPENROUTER_API_KEY"] = "sk-openrouter-seeded"
    app = create_app(config_path=app_config)

    with TestClient(app) as client:
        create_provider_response = client.post(
            "/admin/providers",
            json={
                "slug": "openai",
                "display_name": "OpenAI",
                "provider_type": "openai_compatible",
                "base_url": "https://api.openai.com/v1",
            },
        )
        assert create_provider_response.status_code == 201
        openai_uuid = create_provider_response.json()["id"]
        create_response = client.post(
            "/admin/provider-credentials",
            json={
                "provider_id": openai_uuid,
                "display_name": "Broken Credential",
                "api_key": "sk-secret-value",
            },
        )

    assert create_response.status_code == 400
    assert "PROXY_ENCRYPTION_KEY" in create_response.json()["detail"]
