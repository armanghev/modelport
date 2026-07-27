from __future__ import annotations

from fastapi import HTTPException, status


def unsupported_provider_capability(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=detail)
