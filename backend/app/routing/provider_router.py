from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import ModelAlias, Provider, ProviderCredential, get_setting, is_credential_configured
from app.routing.alias_resolver import resolve_model_alias


@dataclass
class ResolvedProviderRoute:
    requested_model: str
    upstream_model: str
    provider: Provider
    credential: ProviderCredential | None
    alias: ModelAlias | None = None


def select_provider_credential(
    provider: Provider,
    preferred_credential_id: str | None = None,
) -> ProviderCredential | None:
    enabled_credentials = [credential for credential in provider.credentials if credential.enabled]

    if preferred_credential_id:
        preferred_credential = next(
            (credential for credential in enabled_credentials if credential.id == preferred_credential_id),
            None,
        )
        if preferred_credential is not None and is_credential_configured(preferred_credential):
            return preferred_credential
        if preferred_credential is not None:
            return preferred_credential

    configured_credentials = [
        credential for credential in enabled_credentials if is_credential_configured(credential)
    ]
    default_configured = next(
        (credential for credential in configured_credentials if credential.is_default),
        None,
    )
    if default_configured is not None:
        return default_configured

    if configured_credentials:
        return configured_credentials[0]

    default_enabled = next((credential for credential in enabled_credentials if credential.is_default), None)
    if default_enabled is not None:
        return default_enabled

    if enabled_credentials:
        return enabled_credentials[0]

    return provider.credentials[0] if provider.credentials else None


def resolve_provider_route(session: Session, requested_model: str) -> ResolvedProviderRoute:
    alias = resolve_model_alias(session, requested_model)
    if alias is not None:
        provider = session.get(Provider, alias.provider_id)
        if provider is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found for model alias.")
        if not provider.enabled:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Selected provider is disabled.")
        credential = select_provider_credential(provider, preferred_credential_id=alias.credential_id)
        return ResolvedProviderRoute(
            requested_model=requested_model,
            upstream_model=alias.model,
            provider=provider,
            credential=credential,
            alias=alias,
        )

    default_routing = get_setting(session, "default_routing", {})
    provider_id = default_routing.get("provider")
    if not provider_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No provider route found for requested model.",
        )

    provider = session.get(Provider, provider_id)
    if provider is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Default provider is not configured.")
    if not provider.enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Default provider is disabled.")

    credential = select_provider_credential(provider)
    upstream_model = requested_model
    return ResolvedProviderRoute(
        requested_model=requested_model,
        upstream_model=upstream_model,
        provider=provider,
        credential=credential,
        alias=None,
    )
