from __future__ import annotations

import secrets

_REQUEST_ID_PREFIX = "req_"


def generate_api_request_id() -> str:
    """Return a short, URL-safe gateway request ID (e.g. req_x7Kp9mN2qR4s)."""
    return f"{_REQUEST_ID_PREFIX}{secrets.token_urlsafe(9)}"
