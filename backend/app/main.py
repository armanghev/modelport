from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from dotenv import load_dotenv

from app.api.admin import router as admin_router
from app.api.analytics import router as analytics_router
from app.api.anthropic import router as anthropic_router
from app.api.dashboard_auth import router as dashboard_auth_router
from app.api.openai import router as openai_router
from app.config import load_config, read_env_bool
from app.database import build_session_factory, initialize_database, purge_expired_tracking_data, seed_admin_data
from app.dashboard_assets import configure_dashboard_routes, default_dashboard_dist_path
from app.compatibility.exception_handlers import register_exception_handlers
from app.openapi import configure_openapi
from app.pricing_seed import DEFAULT_CATALOG_PATH, seed_pricing_overrides


def create_app(
    config_path: str | Path | None = None,
    *,
    dashboard_dist_path: str | Path | None = None,
) -> FastAPI:
    resolved_config_path = Path(config_path or "config.yaml").expanduser().resolve()
    dotenv_path = resolved_config_path.parent / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path, override=False)
    config = load_config(config_path)
    dashboard_auth_enabled = read_env_bool(
        config.security.dashboard_auth_enabled_env,
        default=True,
    )
    session_factory = build_session_factory(config.database.url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if dashboard_auth_enabled and not os.environ.get(config.security.dashboard_token):
            raise RuntimeError(
                f"{config.security.dashboard_token} is required when dashboard authentication is enabled."
            )
        app.state.config = config
        app.state.session_factory = session_factory
        initialize_database(session_factory)
        seed_admin_data(session_factory)
        purge_expired_tracking_data(session_factory)
        catalog_path = resolved_config_path.parent / DEFAULT_CATALOG_PATH.name
        if catalog_path.exists():
            seed_pricing_overrides(session_factory, catalog_path=catalog_path)
        yield

    app = FastAPI(
        title="ModelPort Backend",
        version="0.1.0",
        description=(
            "ModelPort backend API including the OpenAI/Anthropic-compatible proxy, admin, and analytics routes. "
            "Proxy-only docs are available at /docs/proxy."
        ),
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def prevent_dashboard_api_caching(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith(
            ("/admin", "/analytics", "/dashboard/auth")
        ):
            response.headers["Cache-Control"] = "private, no-store"
            vary_values = {
                value.strip()
                for value in response.headers.get("Vary", "").split(",")
                if value.strip()
            }
            vary_values.add("Cookie")
            response.headers["Vary"] = ", ".join(sorted(vary_values))
        return response

    app.state.dashboard_auth_enabled = dashboard_auth_enabled
    app.include_router(admin_router)
    app.include_router(analytics_router)
    app.include_router(dashboard_auth_router)
    app.include_router(anthropic_router)
    app.include_router(openai_router)
    register_exception_handlers(app)
    configure_openapi(app)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    configure_dashboard_routes(
        app,
        dist_path=Path(dashboard_dist_path or default_dashboard_dist_path()),
    )

    return app


app = create_app()
