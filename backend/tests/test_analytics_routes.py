from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.database import ApiRequest, ProviderHealthCheck


def seed_analytics_data(client: TestClient) -> None:
    now = datetime.now(UTC)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    session_factory = client.app.state.session_factory

    with session_factory() as session:
        session.add_all(
            [
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
                    provider_id="openai",
                    status="operational",
                    latency_ms=120,
                    available_model_count=42,
                    error_message=None,
                    checked_at=now - timedelta(seconds=10),
                ),
                ProviderHealthCheck(
                    provider_id="openrouter",
                    status="degraded",
                    latency_ms=260,
                    available_model_count=18,
                    error_message="Intermittent upstream errors",
                    checked_at=now - timedelta(seconds=12),
                ),
                ProviderHealthCheck(
                    provider_id="ollama",
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
    assert top_model_metric["value"] == "gpt-4.1"
    assert payload["topModels"][0]["model"] == "gpt-4.1"
    assert payload["topModels"][0]["provider"] == "OpenAI"
    assert payload["recentRequests"][0]["id"] == "req_analytics_01"
    assert payload["recentRequests"][1]["status"] == "error"
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
    assert payload["rows"][0]["provider"] == "OpenAI"
    assert payload["rows"][1]["status"] == "error"
    assert payload["rows"][1]["costUsd"] == 0.001


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
    cards_by_id = {card["id"]: card for card in payload["cards"]}
    assert cards_by_id["openai"]["requestsToday"] == 2
    assert cards_by_id["openrouter"]["requestsToday"] == 2
    assert cards_by_id["ollama"]["requestsToday"] == 0
    assert cards_by_id["openrouter"]["status"] == "degraded"
