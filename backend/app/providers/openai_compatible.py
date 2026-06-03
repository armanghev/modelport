from __future__ import annotations

from urllib.parse import urljoin

import httpx
from fastapi import HTTPException, status

from app.database import Provider


def build_chat_completions_url(provider: Provider) -> str:
    normalized_base = provider.base_url.rstrip("/") + "/"
    return urljoin(normalized_base, "chat/completions")


def create_chat_completion(
    provider: Provider,
    api_key: str | None,
    payload: dict,
) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                build_chat_completions_url(provider),
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip() or str(exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream provider request failed: {detail}",
        ) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream provider request failed: {exc}",
        ) from exc


def stream_chat_completion_chunks(
    provider: Provider,
    api_key: str | None,
    payload: dict,
):
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with httpx.Client(timeout=60.0) as client:
            with client.stream(
                "POST",
                build_chat_completions_url(provider),
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    if isinstance(line, bytes):
                        line = line.decode("utf-8")
                    if not line.startswith("data:"):
                        continue
                    yield line.removeprefix("data:").strip()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip() or str(exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream provider request failed: {detail}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream provider request failed: {exc}",
        ) from exc
