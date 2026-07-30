from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.analytics_service import (
    build_costs_payload,
    build_models_payload,
    build_overview_payload,
    build_request_detail_payload,
    build_requests_payload,
    RequestQuery,
)
from app.api.proxy_common import get_session, require_dashboard_token
from app.schemas.analytics import (
    CostsAnalyticsResponse,
    ModelsAnalyticsResponse,
    OverviewAnalyticsResponse,
    RequestsAnalyticsResponse,
    RequestRow,
)

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    dependencies=[Depends(require_dashboard_token)],
)


@router.get("/overview", response_model=OverviewAnalyticsResponse)
def get_overview_analytics(session: Session = Depends(get_session)) -> OverviewAnalyticsResponse:
    return OverviewAnalyticsResponse.model_validate(build_overview_payload(session))


@router.get(
    "/requests",
    response_model=RequestsAnalyticsResponse,
    response_model_exclude_none=True,
)
def get_requests_analytics(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str | None = Query(None, max_length=200),
    client: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    status_filter: Literal["success", "error", "cancelled"] | None = Query(
        None,
        alias="status",
    ),
    endpoint: Literal["/v1/messages", "/v1/chat/completions"] | None = None,
    time_range: Literal["1h", "6h", "24h", "7d", "all"] = "all",
    sort: Literal[
        "timestamp",
        "client",
        "provider",
        "model",
        "totalTokens",
        "latencyMs",
        "costUsd",
        "status",
    ] = "timestamp",
    direction: Literal["asc", "desc"] = "desc",
    session: Session = Depends(get_session),
) -> RequestsAnalyticsResponse:
    return RequestsAnalyticsResponse.model_validate(
        build_requests_payload(
            session,
            RequestQuery(
                page=page,
                page_size=page_size,
                search=search,
                client=client,
                provider=provider,
                model=model,
                status=status_filter,
                endpoint=endpoint,
                time_range=time_range,
                sort=sort,
                direction=direction,
            ),
        )
    )


@router.get("/requests/{request_id}", response_model=RequestRow)
def get_request_analytics_detail(
    request_id: str,
    session: Session = Depends(get_session),
) -> RequestRow:
    payload = build_request_detail_payload(session, request_id)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found.",
        )
    return RequestRow.model_validate(payload)


@router.get("/models", response_model=ModelsAnalyticsResponse)
def get_models_analytics(session: Session = Depends(get_session)) -> ModelsAnalyticsResponse:
    return ModelsAnalyticsResponse.model_validate(build_models_payload(session))


@router.get("/costs", response_model=CostsAnalyticsResponse)
def get_costs_analytics(session: Session = Depends(get_session)) -> CostsAnalyticsResponse:
    return CostsAnalyticsResponse.model_validate(build_costs_payload(session))
