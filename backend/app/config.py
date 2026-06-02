from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


ProviderType = Literal[
    "openai_compatible",
    "anthropic_compatible",
    "local_openai_compatible",
]


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 13243


class SecurityConfig(BaseModel):
    modelport_token: str = "MODELPORT_TOKEN"


class DatabaseConfig(BaseModel):
    url: str = "sqlite:///./data/modelport.db"


class DefaultsConfig(BaseModel):
    input_format: str = "anthropic"
    provider: str = "openrouter"
    model: str = "claude-sonnet"


class ProviderSeedConfig(BaseModel):
    type: ProviderType
    display_name: str
    base_url: str
    api_key_env: str | None = None


class ModelAliasSeedConfig(BaseModel):
    provider: str
    model: str
    description: str | None = None


class AppConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    providers: dict[str, ProviderSeedConfig] = Field(default_factory=dict)
    model_aliases: dict[str, ModelAliasSeedConfig] = Field(default_factory=dict)


def load_config(config_path: str | Path | None = None) -> AppConfig:
    resolved_path = Path(config_path or "config.yaml").expanduser().resolve()
    raw_config = yaml.safe_load(resolved_path.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(raw_config)
