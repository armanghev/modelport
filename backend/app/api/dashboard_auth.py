from __future__ import annotations

import hashlib
import hmac
import os

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel


DASHBOARD_SESSION_COOKIE = "modelport_dashboard_session"
_SESSION_MESSAGE = b"modelport-dashboard-session-v1"

router = APIRouter(prefix="/dashboard/auth", tags=["dashboard"])


class DashboardLoginRequest(BaseModel):
    token: str


class DashboardAuthStatus(BaseModel):
    authEnabled: bool
    authenticated: bool


def dashboard_token(request: Request) -> str | None:
    token_env_name = request.app.state.config.security.dashboard_token
    return os.environ.get(token_env_name)


def dashboard_session_value(token: str) -> str:
    return hmac.new(
        token.encode("utf-8"),
        _SESSION_MESSAGE,
        hashlib.sha256,
    ).hexdigest()


def has_valid_dashboard_session(request: Request) -> bool:
    token = dashboard_token(request)
    presented = request.cookies.get(DASHBOARD_SESSION_COOKIE)
    if not token or not presented:
        return False
    return hmac.compare_digest(presented, dashboard_session_value(token))


@router.get("/status", response_model=DashboardAuthStatus)
def get_dashboard_auth_status(request: Request) -> DashboardAuthStatus:
    enabled = request.app.state.dashboard_auth_enabled
    return DashboardAuthStatus(
        authEnabled=enabled,
        authenticated=not enabled or has_valid_dashboard_session(request),
    )


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
def login_dashboard(payload: DashboardLoginRequest, request: Request) -> Response:
    if not request.app.state.dashboard_auth_enabled:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    expected = dashboard_token(request)
    if not expected or not hmac.compare_digest(payload.token.strip(), expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid dashboard token.",
        )

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.set_cookie(
        DASHBOARD_SESSION_COOKIE,
        dashboard_session_value(expected),
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        path="/",
    )
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_dashboard() -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(
        DASHBOARD_SESSION_COOKIE,
        httponly=True,
        samesite="strict",
        path="/",
    )
    return response
