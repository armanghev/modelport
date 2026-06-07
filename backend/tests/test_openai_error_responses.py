from fastapi import HTTPException

from app.compatibility.openai_errors import (
    format_openai_proxy_error_response,
    is_openai_proxy_path,
)


def test_is_openai_proxy_path() -> None:
    assert is_openai_proxy_path("/v1/chat/completions")
    assert is_openai_proxy_path("/v1/models")
    assert not is_openai_proxy_path("/v1/messages")
    assert not is_openai_proxy_path("/v1/files")
    assert not is_openai_proxy_path("/admin/providers")


def test_format_openai_proxy_error_response_for_upstream_rate_limit() -> None:
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

    status_code, body = format_openai_proxy_error_response(exc)

    assert status_code == 429
    assert body == {
        "error": {
            "message": "Mock scenario mock-429 triggered",
            "type": "rate_limit_error",
            "code": "mock_429",
        }
    }


def test_format_openai_proxy_error_response_for_string_detail() -> None:
    exc = HTTPException(status_code=401, detail="Authorization header required.")

    status_code, body = format_openai_proxy_error_response(exc)

    assert status_code == 401
    assert body["error"]["message"] == "Authorization header required."
    assert body["error"]["type"] == "authentication_error"
