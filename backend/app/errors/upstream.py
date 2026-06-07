from __future__ import annotations

import json
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.compatibility.openai_errors import client_status_for_upstream_error, format_openai_proxy_error_response


def parse_upstream_error_body(raw: str) -> Any | None:
    text = raw.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def extract_upstream_error_record(parsed: Any) -> dict[str, Any] | None:
    if parsed is None:
        return None

    if isinstance(parsed, dict):
        nested = parsed.get("error")
        if isinstance(nested, dict):
            return nested
        if any(key in parsed for key in ("message", "code", "status", "type")):
            return parsed
        return None

    if isinstance(parsed, list):
        for item in parsed:
            record = extract_upstream_error_record(item)
            if record is not None:
                return record
        return None

    return None


def build_upstream_error_detail(
    *,
    upstream_status_code: int | None,
    upstream_body: str,
    fallback_message: str,
) -> dict[str, Any]:
    parsed = parse_upstream_error_body(upstream_body)
    upstream_error = extract_upstream_error_record(parsed)

    message = fallback_message.strip() or "Upstream provider request failed."
    status_label: str | None = None

    upstream_error_type: str | None = None
    upstream_error_code: str | None = None

    if upstream_error is not None:
        upstream_message = upstream_error.get("message")
        if isinstance(upstream_message, str) and upstream_message.strip():
            message = upstream_message.strip()
        status_value = upstream_error.get("status")
        if isinstance(status_value, str) and status_value.strip():
            status_label = status_value.strip()
        type_value = upstream_error.get("type")
        if isinstance(type_value, str) and type_value.strip():
            upstream_error_type = type_value.strip()
        code_value = upstream_error.get("code")
        if isinstance(code_value, str) and code_value.strip():
            upstream_error_code = code_value.strip()
        elif isinstance(code_value, int):
            upstream_error_code = str(code_value)

    detail: dict[str, Any] = {
        "type": "upstream_provider_error",
        "message": message,
    }
    if upstream_error_type is not None:
        detail["provider_error_type"] = upstream_error_type
    if upstream_error_code is not None:
        detail["code"] = upstream_error_code
    if upstream_status_code is not None:
        detail["upstream_status_code"] = upstream_status_code
    if status_label is not None:
        detail["status"] = status_label
    return detail


def http_exception_from_upstream_http_error(exc: httpx.HTTPStatusError) -> HTTPException:
    body = ""
    if exc.response is not None:
        try:
            body = exc.response.text.strip()
        except httpx.ResponseNotRead:
            try:
                exc.response.read()
            except httpx.StreamError:
                body = ""
            else:
                body = exc.response.text.strip()
    upstream_status_code = exc.response.status_code if exc.response is not None else None
    detail = build_upstream_error_detail(
        upstream_status_code=upstream_status_code,
        upstream_body=body,
        fallback_message=body or str(exc),
    )
    return HTTPException(
        status_code=client_status_for_upstream_error(upstream_status_code),
        detail=detail,
    )


def http_exception_from_upstream_transport_error(exc: httpx.HTTPError | ValueError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={
            "type": "upstream_provider_error",
            "message": str(exc),
        },
    )


def format_exception_detail_for_log(detail: Any) -> str:
    if isinstance(detail, dict):
        message = detail.get("message")
        if isinstance(message, str) and message.strip():
            parts = [message.strip()]
            status_label = detail.get("status")
            upstream_status_code = detail.get("upstream_status_code")
            if upstream_status_code is not None:
                parts.append(f"upstream HTTP {upstream_status_code}")
            if isinstance(status_label, str) and status_label:
                parts.append(f"status={status_label}")
            return " · ".join(parts)
    return str(detail)


def build_logged_error_response(exc: HTTPException) -> dict[str, Any]:
    status_code, body = format_openai_proxy_error_response(exc)
    error = dict(body["error"])
    error["status_code"] = status_code

    detail = exc.detail
    if isinstance(detail, dict):
        for key in ("status", "upstream_status_code"):
            if key in detail:
                error[key] = detail[key]

    return {"error": error}
