from __future__ import annotations

from sqlalchemy.orm import Session

from app.database import ModelAlias


def resolve_model_alias(session: Session, requested_model: str) -> ModelAlias | None:
    normalized_model = requested_model.strip().lower()
    alias = session.get(ModelAlias, normalized_model)
    if alias is None or not alias.enabled:
        return None
    return alias
