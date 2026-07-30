from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.database import ApiRequest, ModelMetadata, ProviderHealthCheck

from tests.test_helpers import cards_by_slug, provider_uuid


def seed_analytics_data(client: TestClient) -> None:
    now = datetime.now(UTC)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    session_factory = client.app.state.session_factory

    with session_factory() as session:
        session.add_all(
            [
                ModelMetadata(
                    id="openai/gpt-4.1",
                    canonical_slug="openai/gpt-4.1",
                    name="GPT-4.1",
                    architecture_json="{}",
                    input_modalities_json="[]",
                    output_modalities_json="[]",
                    supported_parameters_json="[]",
                    source="openrouter",
                ),
                ApiRequest(
                    created_at=max(now - timedelta(minutes=20), start_of_day),
                    input_format="anthropic",
                    output_format="anthropic",
                    endpoint="/v1/messages",
                    client_name="Claude Code",
                    requested_model="gpt-4.1",
                    resolved_model="gpt-4.1",
                    provider="openai",
                    input_tokens=1200,
                    output_tokens=300,
                    total_tokens=1500,
                    token_source="provider_reported",
                    estimated_cost_usd=0.012,
                    pricing_source="admin_override",
                    duration_ms=420,
                    status_code=200,
                    error_message=None,
                    streamed=True,
                    request_id="req_analytics_01",
                    request_body='{"messages":[{"role":"user","content":"hello"}]}',
                    response_body='{"choices":[{"message":{"content":"hi"}}]}',
                ),
                ApiRequest(
                    created_at=max(now - timedelta(hours=3), start_of_day),
                    input_format="anthropic",
                    output_format="anthropic",
                    endpoint="/v1/messages",
                    client_name="OpenAI SDK",
                    requested_model="gpt-4.1",
                    resolved_model="gpt-4.1",
                    provider="openai",
                    input_tokens=800,
                    output_tokens=200,
                    total_tokens=1000,
                    token_source="provider_reported",
                    estimated_cost_usd=0.008,
                    pricing_source="admin_override",
                    duration_ms=610,
                    status_code=200,
                    error_message=None,
                    streamed=False,
                    request_id="req_analytics_02",
                ),
                ApiRequest(
                    created_at=max(now - timedelta(hours=5), start_of_day),
                    input_format="anthropic",
                    output_format="anthropic",
                    endpoint="/v1/messages",
                    client_name="Cursor",
                    requested_model="gpt-4o-mini",
                    resolved_model="gpt-4o-mini",
                    provider="openrouter",
                    input_tokens=600,
                    output_tokens=120,
                    total_tokens=720,
                    token_source="provider_reported",
                    estimated_cost_usd=0.0036,
                    pricing_source="admin_override",
                    duration_ms=550,
                    status_code=200,
                    error_message=None,
                    streamed=True,
                    request_id="req_analytics_03",
                ),
                ApiRequest(
                    created_at=max(now - timedelta(hours=1, minutes=30), start_of_day),
                    input_format="anthropic",
                    output_format="anthropic",
                    endpoint="/v1/messages",
                    client_name="Custom App",
                    requested_model="gpt-4o-mini",
                    resolved_model="gpt-4o-mini",
                    provider="openrouter",
                    input_tokens=200,
                    output_tokens=0,
                    total_tokens=200,
                    token_source="provider_reported",
                    estimated_cost_usd=0.001,
                    pricing_source="admin_override",
                    duration_ms=900,
                    status_code=502,
                    error_message="Upstream timeout",
                    streamed=False,
                    request_id="req_analytics_04",
                ),
                ApiRequest(
                    created_at=now - timedelta(days=2),
                    input_format="anthropic",
                    output_format="anthropic",
                    endpoint="/v1/messages",
                    client_name="Codex",
                    requested_model="qwen2.5-coder:latest",
                    resolved_model="qwen2.5-coder:latest",
                    provider="ollama",
                    input_tokens=900,
                    output_tokens=400,
                    total_tokens=1300,
                    token_source="provider_reported",
                    estimated_cost_usd=None,
                    pricing_source=None,
                    duration_ms=180,
                    status_code=200,
                    error_message=None,
                    streamed=True,
                    request_id="req_analytics_05",
                ),
                ApiRequest(
                    created_at=now - timedelta(days=10),
                    input_format="anthropic",
                    output_format="anthropic",
                    endpoint="/v1/messages",
                    client_name="Gemini CLI",
                    requested_model="gpt-4.1",
                    resolved_model="gpt-4.1",
                    provider="openai",
                    input_tokens=1500,
                    output_tokens=500,
                    total_tokens=2000,
                    token_source="provider_reported",
                    estimated_cost_usd=0.02,
                    pricing_source="admin_override",
                    duration_ms=480,
                    status_code=200,
                    error_message=None,
                    streamed=True,
                    request_id="req_analytics_06",
                ),
            ]
        )
        session.add_all(
            [
                ProviderHealthCheck(
                    provider_id=provider_uuid(client, "openai"),
                    status="operational",
                    latency_ms=120,
                    available_model_count=42,
                    error_message=None,
                    checked_at=now - timedelta(seconds=10),
                ),
                ProviderHealthCheck(
                    provider_id=provider_uuid(client, "openrouter"),
                    status="degraded",
                    latency_ms=260,
                    available_model_count=18,
                    error_message="Intermittent upstream errors",
                    checked_at=now - timedelta(seconds=12),
                ),
                ProviderHealthCheck(
                    provider_id=provider_uuid(client, "ollama"),
                    status="operational",
                    latency_ms=90,
                    available_model_count=6,
                    error_message=None,
                    checked_at=now - timedelta(seconds=8),
                ),
            ]
        )
        session.commit()


def test_overview_analytics_endpoint_returns_aggregates(client: TestClient) -> None:
    seed_analytics_data(client)

    response = client.get("/analytics/overview")

    assert response.status_code == 200
    payload = response.json()
    assert {metric["id"] for metric in payload["metrics"]} == {
        "total_tokens",
        "estimated_cost",
        "top_model",
        "average_latency",
    }
    top_model_metric = next(metric for metric in payload["metrics"] if metric["id"] == "top_model")
    assert top_model_metric["value"] == "GPT-4.1"
    assert payload["topModels"][0]["model"] == "gpt-4.1"
    assert payload["topModels"][0]["displayName"] == "GPT-4.1"
    assert payload["topModels"][0]["provider"] == "OpenAI"
    assert payload["recentRequests"][0]["upstreamRequestId"] == "req_analytics_01"
    recent_by_id = {
        row["upstreamRequestId"]: row for row in payload["recentRequests"]
    }
    assert recent_by_id["req_analytics_04"]["status"] == "error"
    assert set(payload["tokenUsage"]) == {"1h", "6h", "24h", "7d", "30d"}
    assert len(payload["tokenUsage"]["30d"]["points"]) == 30


def test_requests_analytics_endpoint_returns_filters_rows_and_totals(client: TestClient) -> None:
    seed_analytics_data(client)

    response = client.get("/analytics/requests")

    assert response.status_code == 200
    payload = response.json()
    assert payload["totals"]["requestsToday"] == 4
    assert payload["totals"]["avgLatencyMs"] == 523
    assert payload["totals"]["errorRate"] == 16.7
    assert payload["totals"]["streamingRate"] == 66.7
    assert payload["filters"]["providers"] == ["Ollama", "OpenAI", "OpenRouter"]
    assert payload["filters"]["statuses"] == ["error", "success"]
    assert payload["pagination"] == {
        "page": 1,
        "pageSize": 25,
        "totalItems": 6,
        "totalPages": 1,
    }
    assert payload["rows"][0]["provider"] == "OpenAI"
    assert "io" not in payload["rows"][0]
    error_row = next(row for row in payload["rows"] if row["status"] == "error")
    assert error_row["costUsd"] == 0.001


def test_requests_analytics_endpoint_paginates_filters_and_sorts(client: TestClient) -> None:
    seed_analytics_data(client)

    response = client.get(
        "/analytics/requests",
        params={
            "page": 1,
            "page_size": 2,
            "provider": "OpenAI",
            "time_range": "all",
            "sort": "costUsd",
            "direction": "desc",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"] == {
        "page": 1,
        "pageSize": 2,
        "totalItems": 3,
        "totalPages": 2,
    }
    assert [row["costUsd"] for row in payload["rows"]] == [0.02, 0.012]
    assert {row["provider"] for row in payload["rows"]} == {"OpenAI"}


def test_requests_analytics_search_and_status_filter_are_server_side(
    client: TestClient,
) -> None:
    seed_analytics_data(client)

    response = client.get(
        "/analytics/requests",
        params={
            "search": "custom app",
            "status": "error",
            "time_range": "all",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["totalItems"] == 1
    assert payload["rows"][0]["upstreamRequestId"] == "req_analytics_04"


def test_request_detail_returns_stored_io_only_for_requested_row(
    client: TestClient,
) -> None:
    seed_analytics_data(client)
    list_payload = client.get("/analytics/requests").json()
    request_id = next(
        row["id"]
        for row in list_payload["rows"]
        if row["upstreamRequestId"] == "req_analytics_01"
    )

    response = client.get(f"/analytics/requests/{request_id}")

    assert response.status_code == 200
    assert response.json()["io"] == {
        "input": '{"messages":[{"role":"user","content":"hello"}]}',
        "output": '{"choices":[{"message":{"content":"hi"}}]}',
    }


def test_request_detail_returns_404_for_unknown_request(client: TestClient) -> None:
    response = client.get("/analytics/requests/req_missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Request not found."


def test_requests_analytics_rejects_page_size_over_limit(client: TestClient) -> None:
    response = client.get("/analytics/requests", params={"page_size": 101})

    assert response.status_code == 422


def test_models_analytics_endpoint_groups_usage_by_provider_and_model(client: TestClient) -> None:
    seed_analytics_data(client)

    response = client.get("/analytics/models")

    assert response.status_code == 200
    payload = response.json()
    assert payload["totals"]["tokenTotal"] == 6720
    assert payload["totals"]["costUsd"] == 0.0446
    assert payload["totals"]["requestCount"] == 6
    assert payload["totals"]["avgLatencyMs"] == 523
    assert payload["totals"]["errorRate"] == 16.7
    assert payload["models"][0]["model"] == "gpt-4.1"
    assert payload["models"][0]["provider"] == "OpenAI"
    assert payload["models"][0]["requestCount"] == 3
    assert payload["models"][1]["model"] == "qwen2.5-coder:latest"


def test_costs_analytics_endpoint_returns_breakdowns_and_trend(client: TestClient) -> None:
    seed_analytics_data(client)

    response = client.get("/analytics/costs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["note"] == "Derived from tracked request logs and admin pricing overrides."
    assert payload["totals"]["todayUsd"] == 0.0246
    assert payload["totals"]["weekUsd"] == 0.0246
    assert payload["totals"]["monthUsd"] == 0.0446
    assert payload["byProvider"][0]["label"] == "OpenAI"
    assert payload["byProvider"][0]["amountUsd"] == 0.04
    assert payload["byModel"][0]["label"] == "gpt-4.1"
    assert len(payload["dailyTrend"]) == 30


def test_provider_health_endpoint_includes_request_counts(client: TestClient) -> None:
    seed_analytics_data(client)

    response = client.get("/admin/providers/health")

    assert response.status_code == 200
    payload = response.json()
    cards = cards_by_slug(payload["cards"])
    assert cards["openai"]["requestsToday"] == 2
    assert cards["openrouter"]["requestsToday"] == 2
    assert cards["ollama"]["requestsToday"] == 0
    assert cards["openrouter"]["status"] == "degraded"
