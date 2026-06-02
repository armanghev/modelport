from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.admin import router as admin_router
from app.config import AppConfig, load_config
from app.database import build_session_factory, initialize_database, seed_admin_data


def create_app(config_path: str | Path | None = None) -> FastAPI:
    config = load_config(config_path)
    session_factory = build_session_factory(config.database.url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.config = config
        app.state.session_factory = session_factory
        initialize_database(session_factory)
        seed_admin_data(session_factory, config)
        yield

    app = FastAPI(title="ModelPort Backend", lifespan=lifespan)
    app.include_router(admin_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
