import json

import httpx
import pytest
from fastapi import HTTPException

from app.errors.upstream import (
    build_logged_error_response,
    build_upstream_error_detail,
    extract_upstream_error_record,
    format_exception_detail_for_log,
    http_exception_from_upstream_http_error,
    parse_upstream_error_body,
)


def test_parse_gemini_array_error_body() -> None:
    body = json.dumps(
        [
            {
                "error": {
                    "code": 404,
                    "message": "This model models/gemini-2.0-flash is no longer available.",
                    "status": "NOT_FOUND",
                }
            }
        ]
    )
    parsed = parse_upstream_error_body(body)
    record = extract_upstream_error_record(parsed)
    assert record is not None
    assert record["code"] == 404
    assert record["status"] == "NOT_FOUND"


def test_build_upstream_error_detail_uses_provider_message() -> None:
    body = json.dumps(
        {
            "error": {
                "message": "Model not found",
                "type": "invalid_request_error",
                "code": "model_not_found",
            }
        }
    )
    detail = build_upstream_error_detail(
        upstream_status_code=404,
        upstream_body=body,
        fallback_message=body,
    )
    assert detail["message"] == "Model not found"
    assert detail["upstream_status_code"] == 404
    assert detail["provider_error_type"] == "invalid_request_error"
    assert detail["code"] == "model_not_found"
    assert "upstream" not in detail


def test_http_exception_from_upstream_http_error() -> None:
    request = httpx.Request("POST", "https://example.com/v1/chat/completions")
    response = httpx.Response(
        404,
        request=request,
        json=[
            {
                "error": {
                    "code": 404,
                    "message": "Model retired.",
                    "status": "NOT_FOUND",
                }
            }
        ],
    )
    exc = httpx.HTTPStatusError("error", request=request, response=response)
    http_exc = http_exception_from_upstream_http_error(exc)

    assert http_exc.status_code == 404
    assert isinstance(http_exc.detail, dict)
    assert http_exc.detail["message"] == "Model retired."
    assert http_exc.detail["code"] == "404"
    assert http_exc.detail["status"] == "NOT_FOUND"
    assert "upstream" not in http_exc.detail


def test_http_exception_from_unread_streaming_upstream_http_error() -> None:
    request = httpx.Request("POST", "https://example.com/v1/chat/completions")
    response = httpx.Response(
        429,
        request=request,
        stream=httpx.ByteStream(
            json.dumps(
                {
                    "error": {
                        "message": "Rate limit exceeded",
                        "status": "RESOURCE_EXHAUSTED",
                    }
                }
            ).encode("utf-8")
        ),
    )
    exc = httpx.HTTPStatusError("error", request=request, response=response)

    with pytest.raises(httpx.ResponseNotRead):
        _ = response.text

    http_exc = http_exception_from_upstream_http_error(exc)

    assert http_exc.status_code == 429
    assert isinstance(http_exc.detail, dict)
    assert http_exc.detail["message"] == "Rate limit exceeded"
    assert http_exc.detail["status"] == "RESOURCE_EXHAUSTED"
    assert http_exc.detail["upstream_status_code"] == 429


def test_http_exception_from_closed_streaming_upstream_http_error() -> None:
    request = httpx.Request("POST", "https://example.com/v1/chat/completions")
    response = httpx.Response(
        429,
        request=request,
        stream=httpx.ByteStream(
            json.dumps(
                {
                    "error": {
                        "message": "Rate limit exceeded",
                        "status": "RESOURCE_EXHAUSTED",
                    }
                }
            ).encode("utf-8")
        ),
    )
    response.close()
    exc = httpx.HTTPStatusError("stream closed", request=request, response=response)

    with pytest.raises(httpx.ResponseNotRead):
        _ = response.text
    with pytest.raises(httpx.StreamClosed):
        response.read()

    http_exc = http_exception_from_upstream_http_error(exc)

    assert http_exc.status_code == 429
    assert isinstance(http_exc.detail, dict)
    assert http_exc.detail["message"] == "stream closed"
    assert "status" not in http_exc.detail
    assert http_exc.detail["upstream_status_code"] == 429


def test_build_upstream_error_detail_omits_raw_upstream_body() -> None:
    body = json.dumps(
        [
            {
                "error": {
                    "code": 404,
                    "message": "This model models/gemini-2.0-flash is no longer available.",
                    "status": "NOT_FOUND",
                }
            }
        ]
    )
    detail = build_upstream_error_detail(
        upstream_status_code=404,
        upstream_body=body,
        fallback_message=body,
    )
    assert detail["message"] == "This model models/gemini-2.0-flash is no longer available."
    assert detail["code"] == "404"
    assert detail["status"] == "NOT_FOUND"
    assert "upstream" not in detail


def test_build_logged_error_response() -> None:
    exc = HTTPException(
        status_code=429,
        detail={
            "type": "upstream_provider_error",
            "provider_error_type": "rate_limit_error",
            "message": "Mock scenario mock-429 triggered",
            "code": "mock_429",
            "upstream_status_code": 429,
        },
    )
    logged = build_logged_error_response(exc)
    assert logged["error"]["message"] == "Mock scenario mock-429 triggered"
    assert logged["error"]["type"] == "rate_limit_error"
    assert logged["error"]["code"] == "mock_429"
    assert logged["error"]["status_code"] == 429
    assert "upstream" not in logged["error"]


def test_format_exception_detail_for_log() -> None:
    formatted = format_exception_detail_for_log(
        {
            "message": "Model retired.",
            "status": "NOT_FOUND",
            "upstream_status_code": 404,
        }
    )
    assert "Model retired." in formatted
    assert "code=" not in formatted
    assert "status=NOT_FOUND" in formatted
