from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.compatibility.openai_errors import format_openai_proxy_error_response, is_openai_proxy_path


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if is_openai_proxy_path(request.url.path):
        status_code, body = format_openai_proxy_error_response(exc)
        return JSONResponse(status_code=status_code, content=body)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_exception_handler)
