from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import String, case, cast, func, or_, select
from sqlalchemy.orm import Session, defer

from app.database import ApiRequest, ModelMetadata, Provider

KNOWN_CLIENTS = (
    "Claude Code",
    "OpenAI SDK",
    "Gemini CLI",
    "Custom App",
    "Codex",
    "Cursor",
)

REQUEST_ENDPOINTS = ("/v1/messages", "/v1/chat/completions")
RequestTimeRange = Literal["1h", "6h", "24h", "7d", "all"]
RequestSortKey = Literal[
    "timestamp",
    "client",
    "provider",
    "model",
    "totalTokens",
    "latencyMs",
    "costUsd",
    "status",
]
SortDirection = Literal["asc", "desc"]


@dataclass(frozen=True)
class RequestQuery:
    page: int = 1
    page_size: int = 25
    search: str | None = None
    client: str | None = None
    provider: str | None = None
    model: str | None = None
    status: str | None = None
    endpoint: str | None = None
    time_range: RequestTimeRange = "all"
    sort: RequestSortKey = "timestamp"
    direction: SortDirection = "desc"

PROVIDER_METADATA_PREFIXES: dict[str, tuple[str, ...]] = {
    "anthropic": ("anthropic",),
    "gemini": ("google", "gemini"),
    "google": ("google",),
    "openai": ("openai",),
}

PROVIDER_DISPLAY_PREFIXES: dict[str, tuple[str, ...]] = {
    "anthropic": ("Anthropic",),
    "gemini": ("Google", "Gemini"),
    "google": ("Google",),
    "openai": ("OpenAI",),
}


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
    providers = session.scalars(select(Provider).order_by(Provider.slug)).all()
    return {provider.slug: provider for provider in providers}


def provider_display_name(provider_id: str | None, providers_by_id: dict[str, Provider]) -> str:
    if provider_id and provider_id in providers_by_id:
        return providers_by_id[provider_id].display_name
    if not provider_id:
        return "Unknown"
    return provider_id.replace("-", " ").replace("_", " ").title()


def model_name(record: ApiRequest) -> str:
    return record.resolved_model or record.requested_model or "unknown"


def load_model_display_names(session: Session) -> dict[str, str]:
    rows = session.scalars(select(ModelMetadata)).all()
    display_names: dict[str, str] = {}
    for row in rows:
        display_name = row.name
        if not display_name:
            continue
        for value in (row.id, row.canonical_slug):
            if not value:
                continue
            display_names[value.lower()] = display_name
            if "/" in value:
                display_names[value.split("/", 1)[-1].lower()] = display_name
    return display_names


def model_display_name(
    provider_id: str | None,
    model_id: str,
    display_names_by_key: dict[str, str],
) -> str:
    if not model_id:
        return "unknown"

    candidates = [model_id]
    if provider_id:
        provider_key = provider_id.lower()
        candidates.append(f"{provider_key}/{model_id}")
        for prefix in PROVIDER_METADATA_PREFIXES.get(provider_key, ()):
            candidates.append(f"{prefix}/{model_id}")

    if "/" in model_id:
        candidates.append(model_id.split("/", 1)[-1])

    for candidate in candidates:
        display_name = display_names_by_key.get(candidate.lower())
        if display_name:
            return strip_provider_display_prefix(provider_id, display_name)
    return model_id


def strip_provider_display_prefix(provider_id: str | None, display_name: str) -> str:
    if not provider_id:
        return display_name

    for prefix in PROVIDER_DISPLAY_PREFIXES.get(provider_id.lower(), ()):
        redundant_prefix = f"{prefix}: "
        if display_name.startswith(redundant_prefix):
            return display_name.removeprefix(redundant_prefix)
    return display_name


def serialize_request_rows(
    requests: list[ApiRequest],
    providers_by_id: dict[str, Provider],
    *,
    include_io: bool = False,
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
                    if include_io and (record.request_body or record.response_body)
                    else {}
                ),
            }
        )
    return rows


def request_model_expression():
    return func.coalesce(
        ApiRequest.resolved_model,
        ApiRequest.requested_model,
        "unknown",
    )


def request_client_expression():
    lowered = func.lower(func.coalesce(ApiRequest.client_name, ""))
    return case(
        (or_(lowered.like("%claude code%"), lowered.like("%claude-code%"), lowered.like("%claude-cli%")), "Claude Code"),
        (lowered.like("%openai%"), "OpenAI SDK"),
        (lowered.like("%gemini%"), "Gemini CLI"),
        (lowered.like("%codex%"), "Codex"),
        (lowered.like("%cursor%"), "Cursor"),
        else_="Custom App",
    )


def request_status_expression():
    return case(
        (
            or_(
                ApiRequest.status_code >= 400,
                ApiRequest.error_message.is_not(None),
            ),
            "error",
        ),
        else_="success",
    )


def request_endpoint_expression():
    return case(
        (ApiRequest.endpoint.in_(REQUEST_ENDPOINTS), ApiRequest.endpoint),
        else_="/v1/messages",
    )


def request_provider_expression():
    return func.coalesce(Provider.display_name, ApiRequest.provider, "Unknown")


def request_time_cutoff(time_range: RequestTimeRange, now: datetime) -> datetime | None:
    hours_by_range = {
        "1h": 1,
        "6h": 6,
        "24h": 24,
        "7d": 24 * 7,
    }
    hours = hours_by_range.get(time_range)
    return now - timedelta(hours=hours) if hours is not None else None


def request_conditions(query: RequestQuery, now: datetime) -> list:
    conditions: list = []
    cutoff = request_time_cutoff(query.time_range, now)
    if cutoff is not None:
        conditions.append(ApiRequest.created_at >= cutoff)
    if query.client:
        conditions.append(request_client_expression() == query.client)
    if query.provider:
        conditions.append(request_provider_expression() == query.provider)
    if query.model:
        conditions.append(request_model_expression() == query.model)
    if query.status:
        conditions.append(request_status_expression() == query.status)
    if query.endpoint:
        conditions.append(request_endpoint_expression() == query.endpoint)
    if query.search and (normalized_search := query.search.strip().lower()):
        pattern = f"%{normalized_search}%"
        conditions.append(
            or_(
                func.lower(cast(ApiRequest.id, String)).like(pattern),
                func.lower(func.coalesce(ApiRequest.request_id, "")).like(pattern),
                func.lower(request_client_expression()).like(pattern),
                func.lower(request_provider_expression()).like(pattern),
                func.lower(request_model_expression()).like(pattern),
                func.lower(request_endpoint_expression()).like(pattern),
                func.lower(request_status_expression()).like(pattern),
            )
        )
    return conditions


def request_order_expression(sort_key: RequestSortKey):
    return {
        "timestamp": ApiRequest.created_at,
        "client": request_client_expression(),
        "provider": request_provider_expression(),
        "model": request_model_expression(),
        "totalTokens": ApiRequest.total_tokens,
        "latencyMs": func.coalesce(ApiRequest.duration_ms, 0),
        "costUsd": func.coalesce(ApiRequest.estimated_cost_usd, 0.0),
        "status": request_status_expression(),
    }[sort_key]


def build_request_totals(session: Session, now: datetime) -> dict:
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    error_condition = or_(
        ApiRequest.status_code >= 400,
        ApiRequest.error_message.is_not(None),
    )
    row = session.execute(
        select(
            func.count(ApiRequest.id),
            func.sum(case((ApiRequest.created_at >= start_of_day, 1), else_=0)),
            func.avg(func.coalesce(ApiRequest.duration_ms, 0)),
            func.sum(case((error_condition, 1), else_=0)),
            func.sum(case((ApiRequest.streamed.is_(True), 1), else_=0)),
        )
    ).one()
    total_requests = int(row[0] or 0)
    return {
        "requestsToday": int(row[1] or 0),
        "avgLatencyMs": round(float(row[2] or 0)),
        "errorRate": round_percent((int(row[3] or 0) / max(1, total_requests)) * 100),
        "streamingRate": round_percent((int(row[4] or 0) / max(1, total_requests)) * 100),
    }


def build_request_filters(
    session: Session,
    providers_by_id: dict[str, Provider],
) -> dict:
    provider_ids = session.scalars(
        select(ApiRequest.provider).distinct()
    ).all()
    models = session.scalars(
        select(request_model_expression()).distinct()
    ).all()
    clients = session.scalars(
        select(request_client_expression()).distinct()
    ).all()
    statuses = session.scalars(
        select(request_status_expression()).distinct()
    ).all()
    endpoints = session.scalars(
        select(request_endpoint_expression()).distinct()
    ).all()
    return {
        "providers": sorted(
            {
                provider_display_name(provider_id, providers_by_id)
                for provider_id in provider_ids
            }
        ),
        "models": sorted(str(model) for model in models),
        "clients": sorted(
            (str(client) for client in clients),
            key=client_sort_key,
        ),
        "statuses": sorted(str(status_value) for status_value in statuses),
        "endpoints": sorted(str(endpoint_value) for endpoint_value in endpoints),
    }


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
    display_names_by_key = load_model_display_names(session)
    serialized_rows = serialize_request_rows(requests, providers_by_id)

    total_tokens = sum(record.total_tokens for record in requests)
    total_cost = sum(record.estimated_cost_usd or 0.0 for record in requests)
    average_latency = round(
        sum((record.duration_ms or 0) for record in requests) / max(1, len(requests))
    )

    model_totals: dict[tuple[str | None, str, str], int] = defaultdict(int)
    for record in requests:
        model_totals[(record.provider, provider_display_name(record.provider, providers_by_id), model_name(record))] += (
            record.total_tokens
        )

    sorted_models = sorted(model_totals.items(), key=lambda item: item[1], reverse=True)
    top_model_name = (
        model_display_name(sorted_models[0][0][0], sorted_models[0][0][2], display_names_by_key)
        if sorted_models
        else "None"
    )

    top_models = []
    for index, ((provider_id, provider_name, model), token_total) in enumerate(sorted_models[:5], start=1):
        display_name = model_display_name(provider_id, model, display_names_by_key)
        percent = round((token_total / max(1, total_tokens)) * 100)
        top_models.append(
            {
                "id": f"top_model_{index}",
                "model": model,
                "displayName": display_name,
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


def build_requests_payload(
    session: Session,
    query: RequestQuery | None = None,
) -> dict:
    query = query or RequestQuery()
    now = datetime.now(UTC)
    providers_by_id = list_providers(session)
    conditions = request_conditions(query, now)
    total_items = int(
        session.scalar(
            select(func.count(ApiRequest.id))
            .outerjoin(Provider, Provider.slug == ApiRequest.provider)
            .where(*conditions)
        )
        or 0
    )
    order_expression = request_order_expression(query.sort)
    order_by = (
        order_expression.asc()
        if query.direction == "asc"
        else order_expression.desc()
    )
    requests = session.scalars(
        select(ApiRequest)
        .options(defer(ApiRequest.request_body), defer(ApiRequest.response_body))
        .outerjoin(Provider, Provider.slug == ApiRequest.provider)
        .where(*conditions)
        .order_by(order_by, ApiRequest.id.asc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    ).all()
    serialized_rows = serialize_request_rows(requests, providers_by_id)
    total_pages = (
        (total_items + query.page_size - 1) // query.page_size
        if total_items
        else 0
    )

    return {
        "totals": build_request_totals(session, now),
        "filters": build_request_filters(session, providers_by_id),
        "rows": serialized_rows,
        "pagination": {
            "page": query.page,
            "pageSize": query.page_size,
            "totalItems": total_items,
            "totalPages": total_pages,
        },
    }


def build_request_detail_payload(session: Session, request_id: str) -> dict | None:
    record = session.get(ApiRequest, request_id)
    if record is None:
        return None
    providers_by_id = list_providers(session)
    return serialize_request_rows(
        [record],
        providers_by_id,
        include_io=True,
    )[0]


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
    provider_requests = [record for record in requests if record.provider == provider.slug]
    cycle_start = now - timedelta(days=29)

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
        "providerId": provider.slug,
        "costBreakdown": cost_breakdown,
        "requestTrend": request_trend,
        "notes": "Derived from proxy request logs and recent provider health checks.",
    }
