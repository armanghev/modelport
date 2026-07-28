from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analytics_service import (
    build_costs_payload,
    build_models_payload,
    build_overview_payload,
    build_requests_payload,
)
from app.api.proxy_common import get_session, require_dashboard_token
from app.schemas.analytics import (
    CostsAnalyticsResponse,
    ModelsAnalyticsResponse,
    OverviewAnalyticsResponse,
    RequestsAnalyticsResponse,
)

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    dependencies=[Depends(require_dashboard_token)],
)


@router.get("/overview", response_model=OverviewAnalyticsResponse)
def get_overview_analytics(session: Session = Depends(get_session)) -> OverviewAnalyticsResponse:
    return OverviewAnalyticsResponse.model_validate(build_overview_payload(session))


@router.get("/requests", response_model=RequestsAnalyticsResponse)
def get_requests_analytics(session: Session = Depends(get_session)) -> RequestsAnalyticsResponse:
    return RequestsAnalyticsResponse.model_validate(build_requests_payload(session))


@router.get("/models", response_model=ModelsAnalyticsResponse)
def get_models_analytics(session: Session = Depends(get_session)) -> ModelsAnalyticsResponse:
    return ModelsAnalyticsResponse.model_validate(build_models_payload(session))


@router.get("/costs", response_model=CostsAnalyticsResponse)
def get_costs_analytics(session: Session = Depends(get_session)) -> CostsAnalyticsResponse:
    return CostsAnalyticsResponse.model_validate(build_costs_payload(session))
