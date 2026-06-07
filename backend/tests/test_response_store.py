from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.database import ProxyResponseResource, build_session_factory
from app.responses.store import (
    PROXY_EMULATED,
    UPSTREAM_PASSTHROUGH,
    build_input_items_from_create_payload,
    cancel_emulated_response,
    default_expires_at,
    get_active_response_resource,
    get_response_resource,
    list_input_items,
    response_resource_is_expired,
    retrieve_emulated_response,
    save_emulated_response,
    save_passthrough_response,
)
from app.schemas.openai import OpenAIResponseCreate


@pytest.fixture()
def session_factory(tmp_path) -> sessionmaker[Session]:
    db_path = tmp_path / "response-store.db"
    factory = build_session_factory(f"sqlite:///{db_path}")
    from app.database import Base

    Base.metadata.create_all(factory.kw["bind"])
    return factory


def test_build_input_items_from_string_input() -> None:
    payload = OpenAIResponseCreate.model_validate(
        {
            "model": "gpt-4.1",
            "input": "hello",
            "instructions": "Be terse.",
        }
    )

    assert build_input_items_from_create_payload(payload) == [
        {
            "type": "message",
            "role": "system",
            "content": [{"type": "input_text", "text": "Be terse."}],
        },
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "hello"}],
        },
    ]


def test_save_and_retrieve_emulated_response(session_factory: sessionmaker[Session]) -> None:
    response_body = {
        "id": "resp_emulated_1",
        "object": "response",
        "status": "completed",
        "model": "claude-sonnet-4-5",
        "output": [],
    }
    input_items = [{"type": "message", "role": "user", "content": []}]

    with session_factory() as session:
        save_emulated_response(
            session,
            response_id="resp_emulated_1",
            provider_id="anthropic",
            requested_model="claude-sonnet-4-5",
            upstream_model="claude-sonnet-4-5-20250929",
            response_body=response_body,
            input_items=input_items,
        )
        session.commit()

        resource = get_response_resource(session, "resp_emulated_1")
        assert resource is not None
        assert resource.storage_kind == PROXY_EMULATED
        assert retrieve_emulated_response(session, "resp_emulated_1") == response_body
        assert list_input_items(session, "resp_emulated_1") == {
            "object": "list",
            "data": input_items,
        }


def test_save_passthrough_response_metadata(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        save_passthrough_response(
            session,
            response_id="resp_upstream_1",
            provider_id="openai",
            requested_model="gpt-4.1",
            upstream_model="gpt-4.1",
            status="completed",
        )
        session.commit()

        resource = get_response_resource(session, "resp_upstream_1")
        assert resource is not None
        assert resource.storage_kind == UPSTREAM_PASSTHROUGH
        assert resource.response_json is None
        assert json.loads(resource.input_items_json or "null") is None


def test_cancel_emulated_response_updates_status(session_factory: sessionmaker[Session]) -> None:
    response_body = {
        "id": "resp_emulated_2",
        "object": "response",
        "status": "completed",
        "model": "claude-sonnet-4-5",
        "output": [],
    }

    with session_factory() as session:
        save_emulated_response(
            session,
            response_id="resp_emulated_2",
            provider_id="anthropic",
            requested_model="claude-sonnet-4-5",
            upstream_model="claude-sonnet-4-5-20250929",
            response_body=response_body,
            input_items=[],
        )
        session.commit()

        cancelled = cancel_emulated_response(session, "resp_emulated_2")
        session.commit()

        assert cancelled["status"] == "cancelled"
        stored = retrieve_emulated_response(session, "resp_emulated_2")
        assert stored is not None
        assert stored["status"] == "cancelled"


def test_save_emulated_response_sets_expires_at(session_factory: sessionmaker[Session]) -> None:
    now = datetime(2026, 6, 6, 12, 0, tzinfo=UTC)
    response_body = {
        "id": "resp_emulated_3",
        "object": "response",
        "status": "completed",
        "model": "claude-sonnet-4-5",
        "output": [],
    }

    with session_factory() as session:
        save_emulated_response(
            session,
            response_id="resp_emulated_3",
            provider_id="anthropic",
            requested_model="claude-sonnet-4-5",
            upstream_model="claude-sonnet-4-5-20250929",
            response_body=response_body,
            input_items=[],
            expires_at=default_expires_at(now=now),
        )
        session.commit()

        resource = get_response_resource(session, "resp_emulated_3")
        assert resource is not None
        assert resource.expires_at is not None
        assert not response_resource_is_expired(resource, now=now)
        assert response_resource_is_expired(resource, now=now + timedelta(hours=25))


def test_expired_emulated_response_is_not_retrievable(session_factory: sessionmaker[Session]) -> None:
    response_body = {
        "id": "resp_emulated_4",
        "object": "response",
        "status": "completed",
        "model": "claude-sonnet-4-5",
        "output": [],
    }

    with session_factory() as session:
        save_emulated_response(
            session,
            response_id="resp_emulated_4",
            provider_id="anthropic",
            requested_model="claude-sonnet-4-5",
            upstream_model="claude-sonnet-4-5-20250929",
            response_body=response_body,
            input_items=[{"type": "message", "role": "user", "content": []}],
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        session.commit()

        assert get_active_response_resource(session, "resp_emulated_4") is None
        assert retrieve_emulated_response(session, "resp_emulated_4") is None
        assert list_input_items(session, "resp_emulated_4") is None
        with pytest.raises(KeyError):
            cancel_emulated_response(session, "resp_emulated_4")
