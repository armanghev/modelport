from __future__ import annotations

from sqlalchemy import inspect


def test_api_requests_has_breakdown_columns(client) -> None:
    engine = client.app.state.session_factory.kw["bind"]
    columns = {column["name"] for column in inspect(engine).get_columns("api_requests")}

    assert {
        "uncached_input_tokens",
        "cache_read_tokens",
        "cache_write_5m_tokens",
        "cache_write_1h_tokens",
        "cost_input_usd",
        "cost_output_usd",
        "cost_cache_read_usd",
        "cost_cache_write_usd",
        "cost_tools_usd",
        "context_tier",
        "service_tier",
    } <= columns


def test_pricing_overrides_has_rate_card_columns(client) -> None:
    engine = client.app.state.session_factory.kw["bind"]
    columns = {column["name"] for column in inspect(engine).get_columns("pricing_overrides")}

    assert {"rate_card_json", "source"} <= columns
