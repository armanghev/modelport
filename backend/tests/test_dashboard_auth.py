from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import DASHBOARD_AUTH_HEADERS, DASHBOARD_TOKEN, managed_test_env


def test_admin_route_rejects_missing_dashboard_token(bare_client: TestClient) -> None:
    response = bare_client.get("/admin/providers")

    assert response.status_code == 401
    assert "Authorization" in response.json()["detail"]


def test_admin_route_rejects_proxy_token(bare_client: TestClient) -> None:
    response = bare_client.get(
        "/admin/providers",
        headers={"Authorization": "Bearer test-local-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid dashboard token."


def test_admin_route_accepts_dashboard_token(bare_client: TestClient) -> None:
    response = bare_client.get("/admin/providers", headers=DASHBOARD_AUTH_HEADERS)

    assert response.status_code == 200


def test_analytics_route_rejects_missing_dashboard_token(bare_client: TestClient) -> None:
    response = bare_client.get("/analytics/overview")

    assert response.status_code == 401
    assert "Authorization" in response.json()["detail"]


def test_analytics_route_rejects_proxy_token(bare_client: TestClient) -> None:
    response = bare_client.get(
        "/analytics/overview",
        headers={"Authorization": "Bearer test-local-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid dashboard token."


def test_analytics_route_accepts_dashboard_token(bare_client: TestClient) -> None:
    response = bare_client.get("/analytics/overview", headers=DASHBOARD_AUTH_HEADERS)

    assert response.status_code == 200


def test_dashboard_auth_status_reports_locked_session(bare_client: TestClient) -> None:
    response = bare_client.get("/dashboard/auth/status")

    assert response.status_code == 200
    assert response.json() == {"authEnabled": True, "authenticated": False}


def test_dashboard_login_rejects_invalid_token(bare_client: TestClient) -> None:
    response = bare_client.post("/dashboard/auth/login", json={"token": "wrong-token"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid dashboard token."
    assert "modelport_dashboard_session" not in response.cookies


def test_dashboard_login_cookie_authenticates_and_logout_clears_session(
    bare_client: TestClient,
) -> None:
    login = bare_client.post("/dashboard/auth/login", json={"token": DASHBOARD_TOKEN})

    assert login.status_code == 204
    cookie_header = login.headers["set-cookie"]
    assert "modelport_dashboard_session=" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "SameSite=strict" in cookie_header
    assert "Max-Age" not in cookie_header

    status_response = bare_client.get("/dashboard/auth/status")
    assert status_response.json() == {"authEnabled": True, "authenticated": True}
    assert bare_client.get("/admin/providers").status_code == 200
    assert bare_client.get("/analytics/overview").status_code == 200

    logout = bare_client.post("/dashboard/auth/logout")
    assert logout.status_code == 204
    assert bare_client.get("/admin/providers").status_code == 401


def test_dashboard_login_marks_cookie_secure_over_https(configured_app) -> None:
    with TestClient(configured_app, base_url="https://testserver") as secure_client:
        response = secure_client.post(
            "/dashboard/auth/login",
            json={"token": DASHBOARD_TOKEN},
        )

    assert response.status_code == 204
    assert "Secure" in response.headers["set-cookie"]


def test_rotating_dashboard_token_invalidates_existing_session(
    bare_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login = bare_client.post("/dashboard/auth/login", json={"token": DASHBOARD_TOKEN})
    assert login.status_code == 204

    monkeypatch.setenv("MODELPORT_DASHBOARD_TOKEN", "rotated-dashboard-token")

    assert bare_client.get("/admin/providers").status_code == 401


def test_dashboard_auth_can_be_disabled(
    app_config,
    encryption_key: str,
) -> None:
    with managed_test_env(encryption_key):
        os.environ["MODELPORT_DASHBOARD_AUTH_ENABLED"] = "false"
        os.environ.pop("MODELPORT_DASHBOARD_TOKEN")
        app = create_app(config_path=app_config)

        with TestClient(app) as unauthenticated_client:
            status_response = unauthenticated_client.get("/dashboard/auth/status")
            admin_response = unauthenticated_client.get("/admin/providers")
            analytics_response = unauthenticated_client.get("/analytics/overview")

    assert status_response.json() == {"authEnabled": False, "authenticated": True}
    assert admin_response.status_code == 200
    assert analytics_response.status_code == 200


def test_dashboard_auth_enabled_requires_token(
    app_config,
    encryption_key: str,
) -> None:
    with managed_test_env(encryption_key):
        os.environ.pop("MODELPORT_DASHBOARD_TOKEN")
        app = create_app(config_path=app_config)

        with pytest.raises(RuntimeError, match="MODELPORT_DASHBOARD_TOKEN"):
            with TestClient(app):
                pass
