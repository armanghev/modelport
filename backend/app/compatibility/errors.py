from __future__ import annotations

from fastapi import HTTPException, status


def unsupported_provider_capability(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=detail)


def proxy_resource_not_found(resource_kind: str, resource_id: str, *, expired: bool = False) -> HTTPException:
    if expired:
        detail = f"{resource_kind} '{resource_id}' was not found or has expired."
    else:
        detail = f"{resource_kind} '{resource_id}' was not found."
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
