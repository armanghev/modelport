from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class ModelAliasCreate(BaseModel):
    alias: str
    provider_id: str
    model: str
    credential_id: str | None = None
    description: str | None = None
    is_default: bool = False
    enabled: bool = True

    @field_validator("alias")
    @classmethod
    def validate_alias(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Aliases must be lowercase slugs.")
        return normalized


class ModelAliasUpdate(BaseModel):
    provider_id: str | None = None
    model: str | None = None
    credential_id: str | None = None
    description: str | None = None
    is_default: bool | None = None
    enabled: bool | None = None


class ModelAliasResponse(ORMModel):
    alias: str
    provider_id: str
    model: str
    credential_id: str | None
    description: str | None
    is_default: bool
    enabled: bool
    created_at: datetime
    updated_at: datetime


class RoutingRuleCreate(BaseModel):
    match: str
    priority: int = 0
    primary_provider_id: str
    primary_alias: str | None = None
    fallback_provider_ids: list[str] = Field(default_factory=list)
    enabled: bool = True


class RoutingRuleUpdate(BaseModel):
    match: str | None = None
    priority: int | None = None
    primary_provider_id: str | None = None
    primary_alias: str | None = None
    fallback_provider_ids: list[str] | None = None
    enabled: bool | None = None


class RoutingRuleResponse(ORMModel):
    id: str
    match: str
    priority: int
    primary_provider_id: str
    primary_alias: str | None
    fallback_provider_ids: list[str]
    enabled: bool
    created_at: datetime
    updated_at: datetime


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


class DefaultRoutingSettings(BaseModel):
    input_format: str | None = None
    provider: str | None = None
    model: str | None = None


class TrackingSettings(BaseModel):
    request_logging: bool | None = None
    cost_tracking: bool | None = None
    retention_days: int | None = None


class AppearanceSettings(BaseModel):
    theme: str | None = None
    refresh_interval_seconds: int | None = None


class SettingsEnvelope(BaseModel):
    default_routing: dict
    tracking: dict
    appearance: dict


class SettingsResponse(BaseModel):
    providers: list[ProviderResponse]
    provider_credentials: list[ProviderCredentialResponse]
    model_aliases: list[ModelAliasResponse]
    routing_rules: list[RoutingRuleResponse]
    pricing_overrides: list[PricingOverrideResponse]
    settings: SettingsEnvelope
