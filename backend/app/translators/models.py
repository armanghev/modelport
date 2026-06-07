from __future__ import annotations

from datetime import UTC, datetime


def _parse_created_at(created_at: object) -> int | None:
    if not isinstance(created_at, str) or not created_at:
        return None
    normalized = created_at.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return int(parsed.astimezone(UTC).timestamp())


def translate_anthropic_models_to_openai(payload: dict) -> dict:
    data = payload.get("data")
    translated_models: list[dict] = []
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            model_id = item.get("id")
            if not isinstance(model_id, str) or not model_id:
                continue
            translated_model = {
                "id": model_id,
                "object": "model",
                "owned_by": "anthropic",
            }
            created = _parse_created_at(item.get("created_at"))
            if created is not None:
                translated_model["created"] = created
            translated_models.append(translated_model)

    return {
        "object": "list",
        "data": translated_models,
    }
