from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse


DASHBOARD_BUILD_COMMAND = "pnpm --dir dashboard build"


def default_dashboard_dist_path() -> Path:
    return Path(__file__).resolve().parent / "static" / "dashboard"


def _safe_file(root: Path, relative_path: str) -> Path | None:
    candidate = (root / relative_path).resolve()
    resolved_root = root.resolve()
    if not candidate.is_relative_to(resolved_root) or not candidate.is_file():
        return None
    return candidate


def configure_dashboard_routes(app: FastAPI, *, dist_path: Path) -> None:
    @app.get("/", include_in_schema=False)
    def dashboard_root() -> RedirectResponse:
        return RedirectResponse("/dashboard/overview")

    @app.get("/dashboard", include_in_schema=False)
    @app.get("/dashboard/", include_in_schema=False)
    def dashboard_index_redirect() -> RedirectResponse:
        return RedirectResponse("/dashboard/overview")

    @app.get("/dashboard/assets/{asset_path:path}", include_in_schema=False)
    def dashboard_asset(asset_path: str):
        asset = _safe_file(dist_path / "assets", asset_path)
        if asset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return FileResponse(
            asset,
            headers={
                "Cache-Control": "public, max-age=31536000, immutable",
            },
        )

    @app.get("/dashboard/{dashboard_path:path}", include_in_schema=False)
    def dashboard_spa(dashboard_path: str):
        index_path = dist_path / "index.html"
        if not index_path.is_file():
            return PlainTextResponse(
                (
                    "ModelPort dashboard assets are missing. "
                    f"Run `{DASHBOARD_BUILD_COMMAND}` from the repository root."
                ),
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        requested_file = _safe_file(dist_path, dashboard_path)
        if requested_file is not None:
            return FileResponse(requested_file)

        return FileResponse(
            index_path,
            headers={"Cache-Control": "no-cache"},
        )
