from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import Provider, ProviderCredential, is_credential_configured


@dataclass
class ResolvedProviderRoute:
    requested_model: str
    upstream_model: str
    provider: Provider
    credential: ProviderCredential | None


def select_provider_credential(
    provider: Provider,
) -> ProviderCredential | None:
    enabled_credentials = [credential for credential in provider.credentials if credential.enabled]

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


def resolve_provider_route(
    session: Session,
    provider_id: str,
    requested_model: str,
) -> ResolvedProviderRoute:
    provider = session.get(Provider, provider_id)
    if provider is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requested provider is not configured.")
    if not provider.enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Requested provider is disabled.")

    credential = select_provider_credential(provider)
    return ResolvedProviderRoute(
        requested_model=requested_model,
        upstream_model=requested_model,
        provider=provider,
        credential=credential,
    )
