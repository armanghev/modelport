from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import DASHBOARD_AUTH_HEADERS


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
