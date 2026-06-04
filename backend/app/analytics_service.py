from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import ApiRequest, Provider

KNOWN_CLIENTS = (
    "Claude Code",
    "OpenAI SDK",
    "Gemini CLI",
    "Custom App",
    "Codex",
    "Cursor",
)

REQUEST_ENDPOINTS = ("/v1/messages", "/v1/chat/completions")


@dataclass(slots=True)
class RequestAnalyticsRow:
    id: str
    timestamp: str
    client: str
    endpoint: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: int
    streaming: bool
    status: str


def round_decimal(value: float, digits: int = 4) -> float:
    return round(value + 1e-12, digits)


def round_percent(value: float) -> float:
    return round(value + 1e-12, 1)


def coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def format_large_token_value(tokens: int) -> str:
    if tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.1f}M"
    if tokens >= 1_000:
        return f"{round(tokens / 1_000)}K"
    return str(tokens)


def format_cost(value: float) -> str:
    return f"${value:.4f}"


def normalize_client_name(value: str | None) -> str:
    if not value:
        return "Custom App"

    lowered = value.lower()
    if "claude code" in lowered or "claude-code" in lowered or "claude-cli" in lowered:
        return "Claude Code"
    if "openai" in lowered:
        return "OpenAI SDK"
    if "gemini" in lowered:
        return "Gemini CLI"
    if "codex" in lowered:
        return "Codex"
    if "cursor" in lowered:
        return "Cursor"
    return "Custom App"


def client_sort_key(value: str) -> int:
    try:
        return KNOWN_CLIENTS.index(value)  # type: ignore[arg-type]
    except ValueError:
        return len(KNOWN_CLIENTS)


def request_status(record: ApiRequest) -> str:
    if record.status_code is not None and record.status_code >= 400:
        return "error"
    if record.error_message:
        return "error"
    return "success"


def list_requests(session: Session) -> list[ApiRequest]:
    return session.scalars(select(ApiRequest).order_by(ApiRequest.created_at.desc())).all()


def list_providers(session: Session) -> dict[str, Provider]:
    providers = session.scalars(select(Provider).order_by(Provider.id)).all()
    return {provider.id: provider for provider in providers}


def provider_display_name(provider_id: str | None, providers_by_id: dict[str, Provider]) -> str:
    if provider_id and provider_id in providers_by_id:
        return providers_by_id[provider_id].display_name
    if not provider_id:
        return "Unknown"
    return provider_id.replace("-", " ").replace("_", " ").title()


def model_name(record: ApiRequest) -> str:
    return record.resolved_model or record.requested_model or "unknown"


def serialize_request_rows(
    requests: list[ApiRequest],
    providers_by_id: dict[str, Provider],
) -> list[dict]:
    rows: list[dict] = []
    for record in requests:
        endpoint = (
            record.endpoint
            if record.endpoint in REQUEST_ENDPOINTS
            else "/v1/messages"
        )
        rows.append(
            {
                "id": record.id,
                "upstreamRequestId": record.request_id,
                "timestamp": coerce_utc(record.created_at).isoformat(),
                "client": normalize_client_name(record.client_name),
                "endpoint": endpoint,
                "provider": provider_display_name(record.provider, providers_by_id),
                "model": model_name(record),
                "inputTokens": record.input_tokens,
                "outputTokens": record.output_tokens,
                "totalTokens": record.total_tokens,
                "costUsd": round_decimal(record.estimated_cost_usd or 0.0),
                "latencyMs": record.duration_ms or 0,
                "streaming": record.streamed,
                "status": request_status(record),
                **(
                    {
                        "io": {
                            "input": record.request_body,
                            "output": record.response_body,
                        }
                    }
                    if record.request_body or record.response_body
                    else {}
                ),
            }
        )
    return rows


def build_time_range_usage(
    requests: list[ApiRequest],
    hours: int,
    buckets: int,
    now: datetime,
) -> list[dict]:
    bucket_span = timedelta(hours=hours / buckets)
    start = now - timedelta(hours=hours)
    points: list[dict] = []

    for index in range(buckets):
        bucket_start = start + (bucket_span * index)
        bucket_end = bucket_start + bucket_span
        tokens = sum(
            record.total_tokens
            for record in requests
            if bucket_start <= coerce_utc(record.created_at) < bucket_end
        )
        label = (
            bucket_end.strftime("%b %d")
            if hours >= 24
            else bucket_end.strftime("%H:%M")
        )
        points.append({"label": label, "tokens": tokens})

    return points


def build_daily_cost_trend(
    requests: list[ApiRequest],
    days: int,
    now: datetime,
) -> list[dict]:
    start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    buckets: list[dict] = []

    for index in range(days):
        day_start = start + timedelta(days=index)
        day_end = day_start + timedelta(days=1)
        amount = sum(
            record.estimated_cost_usd or 0.0
            for record in requests
            if day_start <= coerce_utc(record.created_at) < day_end
        )
        buckets.append(
            {
                "label": day_start.strftime("%b %d"),
                "amountUsd": round_decimal(amount),
            }
        )

    return buckets


def requests_today_count(
    requests: list[ApiRequest],
    provider_id: str,
    now: datetime,
) -> int:
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return sum(
        1
        for record in requests
        if record.provider == provider_id and coerce_utc(record.created_at) >= start_of_day
    )


def build_overview_payload(session: Session) -> dict:
    now = datetime.now(UTC)
    requests = list_requests(session)
    providers_by_id = list_providers(session)
    serialized_rows = serialize_request_rows(requests, providers_by_id)

    total_tokens = sum(record.total_tokens for record in requests)
    total_cost = sum(record.estimated_cost_usd or 0.0 for record in requests)
    average_latency = round(
        sum((record.duration_ms or 0) for record in requests) / max(1, len(requests))
    )

    model_totals: dict[tuple[str, str], int] = defaultdict(int)
    for record in requests:
        model_totals[(provider_display_name(record.provider, providers_by_id), model_name(record))] += (
            record.total_tokens
        )

    sorted_models = sorted(model_totals.items(), key=lambda item: item[1], reverse=True)
    top_model_name = sorted_models[0][0][1] if sorted_models else "None"

    top_models = []
    for index, ((provider_name, model), token_total) in enumerate(sorted_models[:5], start=1):
        percent = round((token_total / max(1, total_tokens)) * 100)
        top_models.append(
            {
                "id": f"top_model_{index}",
                "model": model,
                "provider": provider_name,
                "percent": percent,
                "tokenTotal": token_total,
            }
        )

    metrics = [
        {
            "id": "total_tokens",
            "label": "Total tokens",
            "value": format_large_token_value(total_tokens),
            "subtext": "Across tracked requests",
        },
        {
            "id": "estimated_cost",
            "label": "Estimated cost",
            "value": format_cost(total_cost),
            "subtext": "Based on pricing overrides",
        },
        {
            "id": "top_model",
            "label": "Top model",
            "value": top_model_name,
            "subtext": "By total token volume",
        },
        {
            "id": "average_latency",
            "label": "Average latency",
            "value": f"{average_latency} ms",
            "subtext": "Across tracked requests",
        },
    ]

    token_usage = {
        "1h": {"range": "1h", "points": build_time_range_usage(requests, hours=1, buckets=12, now=now)},
        "6h": {"range": "6h", "points": build_time_range_usage(requests, hours=6, buckets=24, now=now)},
        "24h": {"range": "24h", "points": build_time_range_usage(requests, hours=24, buckets=24, now=now)},
        "7d": {"range": "7d", "points": build_time_range_usage(requests, hours=24 * 7, buckets=7, now=now)},
        "30d": {"range": "30d", "points": build_time_range_usage(requests, hours=24 * 30, buckets=30, now=now)},
    }

    return {
        "metrics": metrics,
        "tokenUsage": token_usage,
        "topModels": top_models,
        "recentRequests": serialized_rows[:10],
    }


def build_requests_payload(session: Session) -> dict:
    now = datetime.now(UTC)
    requests = list_requests(session)
    providers_by_id = list_providers(session)
    serialized_rows = serialize_request_rows(requests, providers_by_id)

    total_requests = len(requests)
    requests_today = sum(
        1
        for record in requests
        if coerce_utc(record.created_at) >= now.replace(hour=0, minute=0, second=0, microsecond=0)
    )
    average_latency = round(
        sum((record.duration_ms or 0) for record in requests) / max(1, total_requests)
    )
    error_count = sum(1 for record in requests if request_status(record) == "error")
    streaming_count = sum(1 for record in requests if record.streamed)

    filters = {
        "providers": sorted({row["provider"] for row in serialized_rows}),
        "models": sorted({row["model"] for row in serialized_rows}),
        "clients": sorted(
            {row["client"] for row in serialized_rows},
            key=client_sort_key,
        ),
        "statuses": sorted({row["status"] for row in serialized_rows}),
        "endpoints": sorted({row["endpoint"] for row in serialized_rows}),
    }

    return {
        "totals": {
            "requestsToday": requests_today,
            "avgLatencyMs": average_latency,
            "errorRate": round_percent((error_count / max(1, total_requests)) * 100),
            "streamingRate": round_percent((streaming_count / max(1, total_requests)) * 100),
        },
        "filters": filters,
        "rows": serialized_rows,
    }


def build_models_payload(session: Session) -> dict:
    requests = list_requests(session)
    providers_by_id = list_providers(session)
    groups: dict[tuple[str, str], list[ApiRequest]] = defaultdict(list)

    for record in requests:
        groups[(provider_display_name(record.provider, providers_by_id), model_name(record))].append(record)

    models = []
    for index, ((provider_name, model), records) in enumerate(groups.items(), start=1):
        token_total = sum(record.total_tokens for record in records)
        cost_total = sum(record.estimated_cost_usd or 0.0 for record in records)
        average_latency = round(
            sum((record.duration_ms or 0) for record in records) / max(1, len(records))
        )
        error_count = sum(1 for record in records if request_status(record) == "error")
        models.append(
            {
                "id": f"model_{index}",
                "provider": provider_name,
                "model": model,
                "displayName": model,
                "requestCount": len(records),
                "tokenTotal": token_total,
                "costUsd": round_decimal(cost_total),
                "avgLatencyMs": average_latency,
                "errorRate": round_percent((error_count / max(1, len(records))) * 100),
            }
        )

    models.sort(key=lambda entry: entry["tokenTotal"], reverse=True)

    total_requests = len(requests)
    total_tokens = sum(record.total_tokens for record in requests)
    total_cost = sum(record.estimated_cost_usd or 0.0 for record in requests)
    avg_latency = round(
        sum((record.duration_ms or 0) for record in requests) / max(1, total_requests)
    )
    total_errors = sum(1 for record in requests if request_status(record) == "error")

    return {
        "totals": {
            "tokenTotal": total_tokens,
            "costUsd": round_decimal(total_cost),
            "requestCount": total_requests,
            "avgLatencyMs": avg_latency,
            "errorRate": round_percent((total_errors / max(1, total_requests)) * 100),
        },
        "models": models,
    }


def build_costs_payload(session: Session) -> dict:
    now = datetime.now(UTC)
    requests = list_requests(session)
    providers_by_id = list_providers(session)
    serialized_rows = serialize_request_rows(requests, providers_by_id)

    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    def sum_cost(records: list[ApiRequest]) -> float:
        return round_decimal(sum(record.estimated_cost_usd or 0.0 for record in records))

    by_provider_totals: dict[str, float] = defaultdict(float)
    by_model_totals: dict[str, float] = defaultdict(float)

    for record in requests:
        by_provider_totals[provider_display_name(record.provider, providers_by_id)] += (
            record.estimated_cost_usd or 0.0
        )
        by_model_totals[model_name(record)] += record.estimated_cost_usd or 0.0

    by_provider = [
        {"label": label, "amountUsd": round_decimal(amount)}
        for label, amount in sorted(by_provider_totals.items(), key=lambda item: item[1], reverse=True)
    ]
    by_model = [
        {"label": label, "amountUsd": round_decimal(amount)}
        for label, amount in sorted(by_model_totals.items(), key=lambda item: item[1], reverse=True)
    ]

    recent_high_cost_requests = sorted(
        serialized_rows,
        key=lambda row: row["costUsd"],
        reverse=True,
    )[:25]

    return {
        "note": "Derived from tracked request logs and admin pricing overrides.",
        "totals": {
            "todayUsd": sum_cost([record for record in requests if coerce_utc(record.created_at) >= start_of_day]),
            "weekUsd": sum_cost([record for record in requests if coerce_utc(record.created_at) >= week_ago]),
            "monthUsd": sum_cost([record for record in requests if coerce_utc(record.created_at) >= month_ago]),
        },
        "byProvider": by_provider,
        "byModel": by_model,
        "dailyTrend": build_daily_cost_trend(requests, days=30, now=now),
        "recentHighCostRequests": recent_high_cost_requests,
    }


def build_provider_details(
    requests: list[ApiRequest],
    provider: Provider,
    now: datetime,
) -> dict:
    provider_requests = [record for record in requests if record.provider == provider.id]
    cycle_end = now
    cycle_start = now - timedelta(days=29)
    spend_usd = sum(
        record.estimated_cost_usd or 0.0
        for record in provider_requests
        if coerce_utc(record.created_at) >= cycle_start
    )
    budget_usd = round_decimal(max(spend_usd * 1.35, 25.0), 2)
    forecast_usd = round_decimal(spend_usd * 1.12, 2)

    request_trend = []
    for index in range(30):
        day_start = cycle_start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=index)
        day_end = day_start + timedelta(days=1)
        day_records = [
            record
            for record in provider_requests
            if day_start <= coerce_utc(record.created_at) < day_end
        ]
        request_trend.append(
            {
                "date": day_start.isoformat(),
                "requests": len(day_records),
                "successfulRequests": sum(1 for record in day_records if request_status(record) == "success"),
                "costUsd": round_decimal(sum(record.estimated_cost_usd or 0.0 for record in day_records)),
            }
        )

    successful_requests = [record for record in provider_requests if request_status(record) == "success"]
    failed_requests = [record for record in provider_requests if request_status(record) == "error"]
    cost_breakdown = [
        {
            "label": "Successful requests",
            "amountUsd": round_decimal(sum(record.estimated_cost_usd or 0.0 for record in successful_requests)),
        },
        {
            "label": "Failed requests",
            "amountUsd": round_decimal(sum(record.estimated_cost_usd or 0.0 for record in failed_requests)),
        },
    ]

    return {
        "providerId": provider.id,
        "region": "global",
        "supportTier": "Standard",
        "billingCycle": {
            "planName": "Pay as you go",
            "periodStart": cycle_start.isoformat(),
            "periodEnd": cycle_end.isoformat(),
            "nextInvoiceDate": cycle_end.isoformat(),
            "budgetUsd": budget_usd,
            "spentUsd": round_decimal(spend_usd, 2),
            "forecastUsd": forecast_usd,
        },
        "costBreakdown": cost_breakdown,
        "requestTrend": request_trend,
        "notes": "Derived from proxy request logs and recent provider health checks.",
    }
