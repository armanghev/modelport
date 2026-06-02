from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

ProviderType = Literal[
    "openai_compatible",
    "anthropic_compatible",
    "local_openai_compatible",
]
CredentialSource = Literal["env", "database"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProviderBase(BaseModel):
    display_name: str
    provider_type: ProviderType
    base_url: str
    enabled: bool = True


class ProviderCreate(ProviderBase):
    id: str

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Provider ids must be lowercase slugs.")
        return normalized


class ProviderUpdate(BaseModel):
    display_name: str | None = None
    provider_type: ProviderType | None = None
    base_url: str | None = None
    enabled: bool | None = None


class ProviderResponse(ORMModel):
    id: str
    display_name: str
    provider_type: ProviderType
    base_url: str
    enabled: bool
    created_at: datetime
    updated_at: datetime
    default_credential_id: str | None = None


class ProviderCredentialCreate(BaseModel):
    provider_id: str
    display_name: str
    source: CredentialSource
    api_key_env: str | None = None
    api_key: str | None = None
    is_default: bool = False
    enabled: bool = True


class ProviderCredentialUpdate(BaseModel):
    display_name: str | None = None
    source: CredentialSource | None = None
    api_key_env: str | None = None
    api_key: str | None = None
    is_default: bool | None = None
    enabled: bool | None = None


class ProviderCredentialResponse(ORMModel):
    id: str
    provider_id: str
    display_name: str
    source: CredentialSource
    api_key_env: str | None
    key_hint: str
    configured: bool
    is_default: bool
    enabled: bool
    created_at: datetime
    updated_at: datetime


class CredentialSecretResponse(BaseModel):
    id: str
    source: CredentialSource
    configured: bool
    api_key: str | None


class PricingOverrideCreate(BaseModel):
    provider_id: str
    model: str
    input_per_1m_usd: float
    output_per_1m_usd: float
    currency: str = "USD"
    enabled: bool = True


class PricingOverrideUpdate(BaseModel):
    provider_id: str | None = None
    model: str | None = None
    input_per_1m_usd: float | None = None
    output_per_1m_usd: float | None = None
    currency: str | None = None
    enabled: bool | None = None


class PricingOverrideResponse(ORMModel):
    id: str
    provider_id: str
    model: str
    input_per_1m_usd: float
    output_per_1m_usd: float
    currency: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


class TrackingSettings(BaseModel):
    request_logging: bool | None = None
    cost_tracking: bool | None = None
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
    pricing_overrides: list[PricingOverrideResponse]
    settings: SettingsEnvelope


class ProviderHealthCard(BaseModel):
    id: str
    displayName: str
    type: ProviderType
    status: Literal["operational", "degraded", "offline"]
    baseUrl: str
    requestsToday: int
    successRate: float
    errorRate: float
    avgLatencyMs: int
    availableModelCount: int
    lastCheckedAt: str
    lastError: str | None


class ProviderHealthPayload(BaseModel):
    cards: list[ProviderHealthCard]
    details: list[dict]
