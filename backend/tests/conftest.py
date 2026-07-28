from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import create_app

DASHBOARD_TOKEN = "test-dashboard-token"
DASHBOARD_AUTH_HEADERS = {"Authorization": f"Bearer {DASHBOARD_TOKEN}"}


class DashboardAuthTestClient(TestClient):
    def request(self, method: str, url: str, **kwargs):  # type: ignore[override]
        path = url.split("?")[0]
        if path.startswith(("/admin", "/analytics")):
            headers = dict(DASHBOARD_AUTH_HEADERS)
            if kwargs.get("headers"):
                headers.update(kwargs["headers"])
            kwargs["headers"] = headers
        return super().request(method, url, **kwargs)


@pytest.fixture()
def encryption_key() -> str:
    return Fernet.generate_key().decode("ascii")


@pytest.fixture()
def app_config(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                'server:',
                '  host: "127.0.0.1"',
                '  port: 13243',
                'security:',
                '  modelport_token: "MODELPORT_TOKEN"',
                '  dashboard_token: "MODELPORT_DASHBOARD_TOKEN"',
                'database:',
                f'  url: "sqlite:///{db_path}"',
                'providers:',
                '  openai:',
                '    type: "openai_compatible"',
                '    display_name: "OpenAI"',
                '    base_url: "https://api.openai.com/v1"',
                '  openrouter:',
                '    type: "openai_compatible"',
                '    display_name: "OpenRouter"',
                '    base_url: "https://openrouter.ai/api/v1"',
                '  anthropic:',
                '    type: "anthropic_compatible"',
                '    display_name: "Anthropic"',
                '    base_url: "https://api.anthropic.com"',
                '  gemini:',
                '    type: "openai_compatible"',
                '    display_name: "Gemini"',
                '    base_url: "https://generativelanguage.googleapis.com/v1beta/openai"',
                '  ollama:',
                '    type: "local_openai_compatible"',
                '    display_name: "Ollama"',
                '    base_url: "http://localhost:11434/v1"',
            ]
        ),
        encoding="utf-8",
    )
    return config_path


@contextmanager
def managed_test_env(encryption_key: str) -> Iterator[None]:
    previous_proxy_token = os.environ.get("MODELPORT_TOKEN")
    previous_dashboard_token = os.environ.get("MODELPORT_DASHBOARD_TOKEN")
    previous_openai = os.environ.get("OPENAI_API_KEY")
    previous_openrouter = os.environ.get("OPENROUTER_API_KEY")
    previous_anthropic = os.environ.get("ANTHROPIC_API_KEY")
    previous_gemini = os.environ.get("GEMINI_API_KEY")
    previous_encryption = os.environ.get("PROXY_ENCRYPTION_KEY")
    os.environ["MODELPORT_TOKEN"] = "test-local-token"
    os.environ["MODELPORT_DASHBOARD_TOKEN"] = DASHBOARD_TOKEN
    os.environ["OPENAI_API_KEY"] = "sk-openai-seeded"
    os.environ["OPENROUTER_API_KEY"] = "sk-openrouter-seeded"
    os.environ["ANTHROPIC_API_KEY"] = "sk-anthropic-seeded"
    os.environ["GEMINI_API_KEY"] = "sk-gemini-seeded"
    os.environ["PROXY_ENCRYPTION_KEY"] = encryption_key

    try:
        yield
    finally:
        if previous_proxy_token is None:
            os.environ.pop("MODELPORT_TOKEN", None)
        else:
            os.environ["MODELPORT_TOKEN"] = previous_proxy_token

        if previous_dashboard_token is None:
            os.environ.pop("MODELPORT_DASHBOARD_TOKEN", None)
        else:
            os.environ["MODELPORT_DASHBOARD_TOKEN"] = previous_dashboard_token

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

        if previous_encryption is None:
            os.environ.pop("PROXY_ENCRYPTION_KEY", None)
        else:
            os.environ["PROXY_ENCRYPTION_KEY"] = previous_encryption


@pytest.fixture()
def configured_app(app_config: Path, encryption_key: str) -> Iterator[FastAPI]:
    with managed_test_env(encryption_key):
        yield create_app(config_path=app_config)


@pytest.fixture()
def bare_client(configured_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(configured_app) as test_client:
        yield test_client


@pytest.fixture()
def client(configured_app: FastAPI) -> TestClient:
    seeded_api_keys = {
        "openai": "sk-openai-seeded",
        "openrouter": "sk-openrouter-seeded",
        "anthropic": "sk-anthropic-seeded",
        "gemini": "sk-gemini-seeded",
    }
    with DashboardAuthTestClient(configured_app) as dashboard_client:
        config = configured_app.state.config
        existing_slugs = {
            provider["slug"] for provider in dashboard_client.get("/admin/providers").json()
        }

        for slug, preset in config.providers.items():
            if slug in existing_slugs:
                continue
            payload: dict[str, str] = {
                "slug": slug,
                "display_name": preset.display_name,
                "provider_type": preset.type,
                "base_url": preset.base_url,
            }
            api_key = seeded_api_keys.get(slug)
            if api_key:
                payload["api_key"] = api_key
                payload["credential_name"] = f"{preset.display_name} Default"
            create_response = dashboard_client.post("/admin/providers", json=payload)
            assert create_response.status_code == 201

        yield dashboard_client
