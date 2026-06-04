from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.database import get_setting


def is_io_logging_enabled(session: Session) -> bool:
    tracking = get_setting(session, "tracking", {})
    return bool(tracking.get("io_logging", False))


def serialize_io_payload(data: Any) -> str:
    if hasattr(data, "model_dump"):
        data = data.model_dump(mode="json")
    return json.dumps(data, ensure_ascii=False, default=str)


def io_log_kwargs(
    session: Session,
    *,
    request_payload: Any | None = None,
    response_payload: Any | None = None,
) -> dict[str, str]:
    if not is_io_logging_enabled(session):
        return {}

    kwargs: dict[str, str] = {}
    if request_payload is not None:
        kwargs["request_body"] = serialize_io_payload(request_payload)
    if response_payload is not None:
        kwargs["response_body"] = serialize_io_payload(response_payload)
    return kwargs
