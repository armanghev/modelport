from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import create_app


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
                'database:',
                f'  url: "sqlite:///{db_path}"',
                'providers:',
                '  openai:',
                '    type: "openai_compatible"',
                '    display_name: "OpenAI"',
                '    base_url: "https://api.openai.com/v1"',
                '    api_key_env: "OPENAI_API_KEY"',
                '  openrouter:',
                '    type: "openai_compatible"',
                '    display_name: "OpenRouter"',
                '    base_url: "https://openrouter.ai/api/v1"',
                '    api_key_env: "OPENROUTER_API_KEY"',
                '  anthropic:',
                '    type: "anthropic_compatible"',
                '    display_name: "Anthropic"',
                '    base_url: "https://api.anthropic.com"',
                '    api_key_env: "ANTHROPIC_API_KEY"',
                '  gemini:',
                '    type: "openai_compatible"',
                '    display_name: "Gemini"',
                '    base_url: "https://generativelanguage.googleapis.com/v1beta/openai"',
                '    api_key_env: "GEMINI_API_KEY"',
                '  ollama:',
                '    type: "local_openai_compatible"',
                '    display_name: "Ollama"',
                '    base_url: "http://localhost:11434/v1"',
                '    api_key_env: null',
            ]
        ),
        encoding="utf-8",
    )
    return config_path


@pytest.fixture()
def client(app_config: Path, encryption_key: str) -> TestClient:
    previous_proxy_token = os.environ.get("MODELPORT_TOKEN")
    previous_openai = os.environ.get("OPENAI_API_KEY")
    previous_openrouter = os.environ.get("OPENROUTER_API_KEY")
    previous_anthropic = os.environ.get("ANTHROPIC_API_KEY")
    previous_gemini = os.environ.get("GEMINI_API_KEY")
    previous_encryption = os.environ.get("PROXY_ENCRYPTION_KEY")
    os.environ["MODELPORT_TOKEN"] = "test-local-token"
    os.environ["OPENAI_API_KEY"] = "sk-openai-seeded"
    os.environ["OPENROUTER_API_KEY"] = "sk-openrouter-seeded"
    os.environ["ANTHROPIC_API_KEY"] = "sk-anthropic-seeded"
    os.environ["GEMINI_API_KEY"] = "sk-gemini-seeded"
    os.environ["PROXY_ENCRYPTION_KEY"] = encryption_key

    app = create_app(config_path=app_config)

    with TestClient(app) as test_client:
        yield test_client

    if previous_proxy_token is None:
        os.environ.pop("MODELPORT_TOKEN", None)
    else:
        os.environ["MODELPORT_TOKEN"] = previous_proxy_token

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
