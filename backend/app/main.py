from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.api.admin import router as admin_router
from app.api.analytics import router as analytics_router
from app.api.anthropic import router as anthropic_router
from app.api.openai import router as openai_router
from app.config import AppConfig, load_config
from app.database import build_session_factory, initialize_database, seed_admin_data
from app.pricing_seed import DEFAULT_CATALOG_PATH, seed_pricing_overrides


def create_app(config_path: str | Path | None = None) -> FastAPI:
    resolved_config_path = Path(config_path or "config.yaml").expanduser().resolve()
    dotenv_path = resolved_config_path.parent / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path, override=False)
    config = load_config(config_path)
    session_factory = build_session_factory(config.database.url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.config = config
        app.state.session_factory = session_factory
        initialize_database(session_factory)
        seed_admin_data(session_factory, config)
        catalog_path = resolved_config_path.parent / DEFAULT_CATALOG_PATH.name
        if catalog_path.exists():
            seed_pricing_overrides(session_factory, config, catalog_path=catalog_path)
        yield

    app = FastAPI(title="ModelPort Backend", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(admin_router)
    app.include_router(analytics_router)
    app.include_router(anthropic_router)
    app.include_router(openai_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
