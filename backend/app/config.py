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


class SecurityConfig(BaseModel):
    modelport_token: str = "MODELPORT_TOKEN"
    dashboard_token: str = "MODELPORT_DASHBOARD_TOKEN"


class DatabaseConfig(BaseModel):
    url: str = "sqlite:///./data/modelport.db"


class ProviderPresetConfig(BaseModel):
    type: ProviderType
    display_name: str
    base_url: str


class AppConfig(BaseModel):
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    providers: dict[str, ProviderPresetConfig] = Field(default_factory=dict)


def resolve_database_url(database_url: str, *, config_dir: Path) -> str:
    """Resolve relative SQLite paths against the config file directory, not cwd."""
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return database_url

    path_part = database_url[len(prefix) :]
    if not path_part or path_part == ":memory:" or path_part.startswith("/"):
        return database_url

    resolved = (config_dir / path_part).resolve()
    return f"{prefix}{resolved.as_posix()}"


def load_config(config_path: str | Path | None = None) -> AppConfig:
    resolved_path = Path(config_path or "config.yaml").expanduser().resolve()
    raw_config = yaml.safe_load(resolved_path.read_text(encoding="utf-8")) or {}
    config = AppConfig.model_validate(raw_config)
    config.database.url = resolve_database_url(
        config.database.url,
        config_dir=resolved_path.parent,
    )
    return config
