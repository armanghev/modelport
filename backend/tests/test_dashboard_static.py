from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import managed_test_env


def test_dashboard_root_redirects_to_overview(bare_client: TestClient) -> None:
    response = bare_client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/dashboard/overview"


def test_missing_dashboard_build_returns_503_without_affecting_health(
    app_config: Path,
    encryption_key: str,
    tmp_path: Path,
) -> None:
    missing_dist = tmp_path / "missing-dashboard"
    with managed_test_env(encryption_key):
        app = create_app(
            config_path=app_config,
            dashboard_dist_path=missing_dist,
        )
        with TestClient(app) as client:
            dashboard_response = client.get("/dashboard/requests")
            health_response = client.get("/health")

    assert dashboard_response.status_code == 503
    assert "pnpm --dir dashboard build" in dashboard_response.text
    assert health_response.status_code == 200


def test_dashboard_serves_assets_and_spa_fallback(
    app_config: Path,
    encryption_key: str,
    tmp_path: Path,
) -> None:
    dashboard_dist = tmp_path / "dashboard"
    assets_dir = dashboard_dist / "assets"
    assets_dir.mkdir(parents=True)
    (dashboard_dist / "index.html").write_text(
        "<!doctype html><div id='root'></div>",
        encoding="utf-8",
    )
    (assets_dir / "app-123.js").write_text("console.log('ok')", encoding="utf-8")

    with managed_test_env(encryption_key):
        app = create_app(
            config_path=app_config,
            dashboard_dist_path=dashboard_dist,
        )
        with TestClient(app) as client:
            deep_link = client.get("/dashboard/models/openai/gpt-4.1")
            asset = client.get("/dashboard/assets/app-123.js")

    assert deep_link.status_code == 200
    assert deep_link.text.startswith("<!doctype html>")
    assert deep_link.headers["cache-control"] == "no-cache"
    assert asset.status_code == 200
    assert asset.text == "console.log('ok')"
    assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"
