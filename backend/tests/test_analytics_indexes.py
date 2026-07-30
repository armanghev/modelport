from sqlalchemy import inspect

from app.database import SchemaVersion, build_session_factory, initialize_database


EXPECTED_ANALYTICS_INDEXES = {
    "ix_api_requests_created_at",
    "ix_api_requests_provider_created_at",
    "ix_api_requests_resolved_model_created_at",
    "ix_api_requests_requested_model_created_at",
    "ix_api_requests_client_name_created_at",
    "ix_api_requests_status_code_created_at",
    "ix_api_requests_estimated_cost_usd",
}


def test_schema_version_six_adds_analytics_indexes_idempotently(tmp_path) -> None:
    session_factory = build_session_factory(f"sqlite:///{tmp_path / 'analytics.db'}")

    initialize_database(session_factory)
    initialize_database(session_factory)

    engine = session_factory.kw["bind"]
    index_names = {
        index["name"] for index in inspect(engine).get_indexes("api_requests")
    }
    assert EXPECTED_ANALYTICS_INDEXES <= index_names
    with session_factory() as session:
        assert session.get(SchemaVersion, 6) is not None
