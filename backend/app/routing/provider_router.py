from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import (
    Provider,
    ProviderCredential,
    ProviderHealthCheck,
    get_provider_by_slug,
    is_credential_configured,
)


@dataclass
class ResolvedProviderRoute:
    requested_model: str
    upstream_model: str
    provider: Provider
    credential: ProviderCredential | None
    health_status: str | None = None


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
    return resolve_provider_routes(
        session,
        provider_id=provider_id,
        requested_model=requested_model,
        fallback_provider_ids=[],
    )[0]


def get_latest_provider_health_status(session: Session, provider_id: str) -> str | None:
    latest_check = session.scalars(
        select(ProviderHealthCheck.status)
        .where(ProviderHealthCheck.provider_id == provider_id)
        .order_by(ProviderHealthCheck.checked_at.desc())
        .limit(1)
    ).first()
    return latest_check


def resolve_provider_routes(
    session: Session,
    provider_id: str,
    requested_model: str,
    fallback_provider_ids: list[str] | None = None,
    upstream_model: str | None = None,
) -> list[ResolvedProviderRoute]:
    fallback_provider_ids = fallback_provider_ids or []
    resolved_upstream_model = upstream_model if upstream_model is not None else requested_model
    candidate_ids: list[str] = []
    for candidate_id in [provider_id, *fallback_provider_ids]:
        normalized = candidate_id.strip().lower()
        if normalized and normalized not in candidate_ids:
            candidate_ids.append(normalized)

    operational_routes: list[ResolvedProviderRoute] = []
    degraded_routes: list[ResolvedProviderRoute] = []
    offline_routes: list[ResolvedProviderRoute] = []

    for index, candidate_id in enumerate(candidate_ids):
        provider = get_provider_by_slug(session, candidate_id)
        if provider is None:
            if index == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Requested provider is not configured.",
                )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fallback provider '{candidate_id}' is not configured.",
            )
        if not provider.enabled:
            continue

        route = ResolvedProviderRoute(
            requested_model=requested_model,
            upstream_model=resolved_upstream_model,
            provider=provider,
            credential=select_provider_credential(provider),
            health_status=get_latest_provider_health_status(session, provider.id),
        )
        if route.health_status == "offline":
            offline_routes.append(route)
        elif route.health_status == "degraded":
            degraded_routes.append(route)
        else:
            operational_routes.append(route)

    ordered_routes = operational_routes + degraded_routes
    if ordered_routes:
        return ordered_routes

    if offline_routes:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No healthy provider available. Requested provider and fallbacks are offline.",
        )

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="No enabled provider available for the request.",
    )
