from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.database import (
    ApiRequest,
    ProxyResponseResource,
    build_session_factory,
    initialize_database,
    purge_expired_tracking_data,
    set_setting,
    utc_now,
)


def test_purge_expired_tracking_data_removes_old_rows(app_config) -> None:
    session_factory = build_session_factory(f"sqlite:///{app_config.parent / 'test.db'}")
    initialize_database(session_factory)
    now = utc_now()

    with session_factory() as session:
        set_setting(session, "tracking", {"retention_days": 7, "io_logging": False})
        session.add_all(
            [
                ApiRequest(
                    id="old-request",
                    created_at=now - timedelta(days=10),
                    input_format="openai",
                    output_format="openai",
                    endpoint="/v1/chat/completions",
                    request_body='{"prompt":"old"}',
                    response_body='{"text":"old"}',
                ),
                ApiRequest(
                    id="recent-request",
                    created_at=now - timedelta(days=1),
                    input_format="openai",
                    output_format="openai",
                    endpoint="/v1/chat/completions",
                ),
                ProxyResponseResource(
                    id="old-response",
                    provider_id="openai",
                    storage_kind="emulated",
                    status="completed",
                    requested_model="gpt-4.1",
                    upstream_model="gpt-4.1",
                    created_at=now - timedelta(days=10),
                    response_json='{"id":"old"}',
                ),
                ProxyResponseResource(
                    id="recent-response",
                    provider_id="openai",
                    storage_kind="emulated",
                    status="completed",
                    requested_model="gpt-4.1",
                    upstream_model="gpt-4.1",
                    created_at=now - timedelta(days=1),
                ),
            ]
        )
        session.commit()

    purge_expired_tracking_data(session_factory)

    with session_factory() as session:
        request_ids = set(session.scalars(select(ApiRequest.id)).all())
        resource_ids = set(session.scalars(select(ProxyResponseResource.id)).all())

    assert request_ids == {"recent-request"}
    assert resource_ids == {"recent-response"}


def test_purge_expired_tracking_data_skips_non_positive_retention(app_config) -> None:
    session_factory = build_session_factory(f"sqlite:///{app_config.parent / 'test.db'}")
    initialize_database(session_factory)
    now = utc_now()
    with session_factory() as session:
        set_setting(session, "tracking", {"retention_days": 0, "io_logging": False})
        session.add(
            ApiRequest(
                id="kept-request",
                created_at=now - timedelta(days=30),
                input_format="openai",
                output_format="openai",
                endpoint="/v1/chat/completions",
            )
        )
        session.commit()

    purge_expired_tracking_data(session_factory)

    with session_factory() as session:
        request_ids = set(session.scalars(select(ApiRequest.id)).all())

    assert request_ids == {"kept-request"}
