from __future__ import annotations

from typing import Any

from fastapi import HTTPException

OPENAI_ERROR_TYPES = {
    "invalid_request_error",
    "authentication_error",
    "permission_denied_error",
    "not_found_error",
    "rate_limit_error",
    "api_error",
    "server_error",
    "conflict_error",
    "internal_error",
}

ANTHROPIC_PROXY_PATH_PREFIXES = (
    "/v1/messages",
    "/v1/files",
)


def is_openai_proxy_path(path: str) -> bool:
    if not path.startswith("/v1/"):
        return False
    return not any(path.startswith(prefix) for prefix in ANTHROPIC_PROXY_PATH_PREFIXES)


def infer_openai_error_type(*, status_code: int, detail_type: str | None = None) -> str:
    if detail_type in OPENAI_ERROR_TYPES:
        return detail_type
    if status_code == 400:
        return "invalid_request_error"
    if status_code == 401:
        return "authentication_error"
    if status_code == 403:
        return "permission_denied_error"
    if status_code == 404:
        return "invalid_request_error"
    if status_code == 409:
        return "conflict_error"
    if status_code == 429:
        return "rate_limit_error"
    if status_code >= 500:
        return "api_error"
    return "api_error"


def client_status_for_upstream_error(upstream_status_code: int | None) -> int:
    if upstream_status_code is not None and 400 <= upstream_status_code < 500:
        return upstream_status_code
    return 502


def format_openai_proxy_error_response(exc: HTTPException) -> tuple[int, dict[str, Any]]:
    status_code = exc.status_code
    detail = exc.detail

    if isinstance(detail, dict):
        upstream_status = detail.get("upstream_status_code")
        if isinstance(upstream_status, int) and 400 <= upstream_status < 500:
            status_code = upstream_status

        message = detail.get("message", "Request failed")
        if not isinstance(message, str) or not message.strip():
            message = "Request failed"

        upstream_type = detail.get("provider_error_type")
        if not isinstance(upstream_type, str):
            upstream_type = detail.get("type")
        if upstream_type == "upstream_provider_error":
            upstream_type = None
        error_type = infer_openai_error_type(
            status_code=status_code,
            detail_type=upstream_type if isinstance(upstream_type, str) else None,
        )

        error: dict[str, Any] = {"message": message.strip(), "type": error_type}
        code = detail.get("code")
        if isinstance(code, str) and code.strip():
            error["code"] = code.strip()
        elif isinstance(code, int):
            error["code"] = str(code)

        return status_code, {"error": error}

    message = str(detail) if detail else "Request failed"
    error_type = infer_openai_error_type(status_code=status_code)
    return status_code, {"error": {"message": message, "type": error_type}}
