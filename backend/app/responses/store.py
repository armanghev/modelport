from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.database import ProxyResponseResource, utc_now
from app.schemas.openai import OpenAIResponseCreate, OpenAIResponseInputMessage

UPSTREAM_PASSTHROUGH = "upstream_passthrough"
PROXY_EMULATED = "proxy_emulated"
DEFAULT_PROXY_RESPONSE_TTL = timedelta(hours=24)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def default_expires_at(*, now: datetime | None = None) -> datetime:
    current = now or utc_now()
    return current + DEFAULT_PROXY_RESPONSE_TTL


def response_resource_is_expired(
    resource: ProxyResponseResource,
    *,
    now: datetime | None = None,
) -> bool:
    if resource.expires_at is None:
        return False
    current = _ensure_utc(now or utc_now())
    expires_at = _ensure_utc(resource.expires_at)
    return expires_at <= current


def build_input_items_from_create_payload(payload: OpenAIResponseCreate) -> list[dict]:
    items: list[dict] = []
    if payload.instructions:
        items.append(
            {
                "type": "message",
                "role": "system",
                "content": [{"type": "input_text", "text": payload.instructions}],
            }
        )

    input_value = payload.input
    if isinstance(input_value, str):
        items.append(
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": input_value}],
            }
        )
        return items

    for message in input_value:
        items.append(_build_input_item_from_message(message))
    return items


def _build_input_item_from_message(message: OpenAIResponseInputMessage) -> dict:
    content = message.content
    if isinstance(content, str):
        content_parts = [{"type": "input_text", "text": content}]
    else:
        content_parts = [{"type": part.type, "text": part.text} for part in content]
    return {
        "type": "message",
        "role": message.role,
        "content": content_parts,
    }


def save_emulated_response(
    session: Session,
    *,
    response_id: str,
    provider_id: str,
    requested_model: str,
    upstream_model: str,
    response_body: dict,
    input_items: list[dict],
    status: str = "completed",
    expires_at: datetime | None = None,
) -> ProxyResponseResource:
    resource = ProxyResponseResource(
        id=response_id,
        provider_id=provider_id,
        storage_kind=PROXY_EMULATED,
        status=status,
        requested_model=requested_model,
        upstream_model=upstream_model,
        response_json=json.dumps(response_body),
        input_items_json=json.dumps(input_items),
        expires_at=expires_at or default_expires_at(),
    )
    session.add(resource)
    session.flush()
    return resource


def save_passthrough_response(
    session: Session,
    *,
    response_id: str,
    provider_id: str,
    requested_model: str,
    upstream_model: str,
    status: str,
    expires_at: datetime | None = None,
) -> ProxyResponseResource:
    resolved_expires_at = expires_at or default_expires_at()
    existing = get_response_resource(session, response_id)
    if existing is not None:
        existing.provider_id = provider_id
        existing.storage_kind = UPSTREAM_PASSTHROUGH
        existing.status = status
        existing.requested_model = requested_model
        existing.upstream_model = upstream_model
        existing.upstream_response_id = response_id
        existing.expires_at = resolved_expires_at
        session.flush()
        return existing

    resource = ProxyResponseResource(
        id=response_id,
        provider_id=provider_id,
        storage_kind=UPSTREAM_PASSTHROUGH,
        status=status,
        requested_model=requested_model,
        upstream_model=upstream_model,
        upstream_response_id=response_id,
        expires_at=resolved_expires_at,
    )
    session.add(resource)
    session.flush()
    return resource


def get_response_resource(session: Session, response_id: str) -> ProxyResponseResource | None:
    return session.get(ProxyResponseResource, response_id)


def get_active_response_resource(
    session: Session,
    response_id: str,
    *,
    now: datetime | None = None,
) -> ProxyResponseResource | None:
    resource = get_response_resource(session, response_id)
    if resource is None or response_resource_is_expired(resource, now=now):
        return None
    return resource


def retrieve_emulated_response(session: Session, response_id: str) -> dict | None:
    resource = get_active_response_resource(session, response_id)
    if resource is None or resource.storage_kind != PROXY_EMULATED or not resource.response_json:
        return None
    return json.loads(resource.response_json)


def list_input_items(session: Session, response_id: str) -> dict | None:
    resource = get_active_response_resource(session, response_id)
    if resource is None:
        return None
    if resource.storage_kind == PROXY_EMULATED:
        if not resource.input_items_json:
            return {"object": "list", "data": []}
        return {"object": "list", "data": json.loads(resource.input_items_json)}
    return None


def cancel_emulated_response(session: Session, response_id: str) -> dict:
    resource = get_active_response_resource(session, response_id)
    if resource is None or resource.storage_kind != PROXY_EMULATED or not resource.response_json:
        raise KeyError(response_id)

    response_body = json.loads(resource.response_json)
    response_body["status"] = "cancelled"
    resource.status = "cancelled"
    resource.response_json = json.dumps(response_body)
    session.flush()
    return response_body


def ingest_passthrough_response_stream_line(line: str, state: dict[str, object]) -> None:
    stripped = line.strip()
    if not stripped.startswith("data:"):
        return

    raw_payload = stripped.removeprefix("data:").strip()
    if not raw_payload:
        return

    try:
        payload = json.loads(raw_payload)
    except ValueError:
        return

    if not isinstance(payload, dict):
        return

    event_type = payload.get("type")
    response = payload.get("response")
    if not isinstance(response, dict):
        return

    if event_type in {"response.created", "response.completed", "response.in_progress"}:
        response_id = response.get("id")
        if isinstance(response_id, str) and response_id:
            state["response_id"] = response_id
        status = response.get("status")
        if isinstance(status, str) and status:
            state["status"] = status
        if event_type == "response.completed":
            state["final_response"] = response
