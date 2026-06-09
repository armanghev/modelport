from __future__ import annotations

from fastapi.testclient import TestClient


def provider_uuid(client: TestClient, slug: str) -> str:
    providers = client.get("/admin/providers").json()
    return next(provider["id"] for provider in providers if provider["slug"] == slug)


def cards_by_slug(cards: list[dict]) -> dict[str, dict]:
    return {card["slug"]: card for card in cards}
