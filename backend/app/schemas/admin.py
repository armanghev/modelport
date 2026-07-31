from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProviderType = Literal[
    "openai_compatible",
    "anthropic_compatible",
    "local_openai_compatible",
]

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def normalize_provider_slug(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9-]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    if not normalized or not SLUG_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Provider slug must be lowercase letters, numbers, and dashes (e.g. openai or mock-local)."
        )
    return normalized


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProviderBase(BaseModel):
    display_name: str
    provider_type: ProviderType
    base_url: str
    enabled: bool = True


class ProviderPresetResponse(BaseModel):
    slug: str
    display_name: str
    provider_type: ProviderType
    base_url: str
    protocol: Literal["openai", "anthropic"]


class ProviderCreate(ProviderBase):
    slug: str
    api_key: str | None = None
    credential_name: str | None = None

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        return normalize_provider_slug(value)


class ProviderUpdate(BaseModel):
    display_name: str | None = None
    provider_type: ProviderType | None = None
    base_url: str | None = None
    enabled: bool | None = None


class ProviderResponse(ORMModel):
    id: str
    slug: str
    display_name: str
    provider_type: ProviderType
    base_url: str
    enabled: bool
    created_at: datetime
    updated_at: datetime
    default_credential_id: str | None = None
    health_status: Literal["operational", "degraded", "offline"] | None = None
    last_checked_at: datetime | None = None
    last_error: str | None = None


class ProviderCredentialCreate(BaseModel):
    provider_id: str
    display_name: str
    api_key: str
    is_default: bool = False
    enabled: bool = True


class ProviderCredentialUpdate(BaseModel):
    display_name: str | None = None
    api_key: str | None = None
    is_default: bool | None = None
    enabled: bool | None = None


class ProviderCredentialResponse(ORMModel):
    id: str
    provider_id: str
    provider_slug: str
    display_name: str
    key_hint: str
    configured: bool
    is_default: bool
    enabled: bool
    created_at: datetime
    updated_at: datetime


class CredentialSecretResponse(BaseModel):
    id: str
    configured: bool
    api_key: str | None


class TrackingSettings(BaseModel):
    io_logging: bool | None = None
    retention_days: int | None = None


class AppearanceSettings(BaseModel):
    theme: str | None = None
    refresh_interval_seconds: int | None = None


class SettingsEnvelope(BaseModel):
    tracking: dict
    appearance: dict


class SettingsResponse(BaseModel):
    providers: list[ProviderResponse]
    provider_credentials: list[ProviderCredentialResponse]
    settings: SettingsEnvelope


class ModelUsageSummary(BaseModel):
    requestCount: int = 0
    tokenTotal: int = 0
    costUsd: float = 0.0
    avgLatencyMs: int = 0
    errorRate: float = 0.0


class ProviderModelSummary(BaseModel):
    id: str
    display_name: str | None = None
    owned_by: str | None = None
    metadata_source: Literal["openrouter", "local", "pricing", "unknown"] = "unknown"
    canonical_slug: str | None = None
    description: str | None = None
    context_length: int | None = None
    architecture: dict = Field(default_factory=dict)
    input_modalities: list[str] = Field(default_factory=list)
    output_modalities: list[str] = Field(default_factory=list)
    supported_parameters: list[str] = Field(default_factory=list)
    input_per_1m_usd: float | None = None
    output_per_1m_usd: float | None = None
    top_provider: dict | None = None
    expiration_date: str | None = None
    openrouter_id: str | None = None
    usage: ModelUsageSummary | None = None


class ProviderModelsEntry(BaseModel):
    provider_id: str
    provider_uuid: str | None = None
    display_name: str
    provider_type: ProviderType
    base_url: str
    status: Literal["operational", "degraded", "offline"]
    available_model_count: int
    fetched_at: str
    models: list[ProviderModelSummary]


class ProviderModelsTotals(BaseModel):
    live_model_count: int = 0
    provider_count: int = 0
    priced_model_count: int = 0
    used_model_count: int = 0
    metadata_synced_at: str | None = None


class ProviderModelsPayload(BaseModel):
    totals: ProviderModelsTotals = ProviderModelsTotals()
    providers: list[ProviderModelsEntry]
