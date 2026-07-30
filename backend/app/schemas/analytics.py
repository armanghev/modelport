from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.admin import ProviderType

RequestStatus = Literal["success", "error", "cancelled"]
RequestEndpoint = Literal["/v1/messages", "/v1/chat/completions"]
UsageRange = Literal["1h", "6h", "24h", "7d", "30d"]
KnownClientName = Literal[
    "Claude Code",
    "OpenAI SDK",
    "Gemini CLI",
    "Custom App",
    "Codex",
    "Cursor",
]


class OverviewMetric(BaseModel):
    id: Literal["total_tokens", "estimated_cost", "top_model", "average_latency"]
    label: str
    value: str
    subtext: str


class UsagePoint(BaseModel):
    label: str
    tokens: int


class TimeRangeUsage(BaseModel):
    range: UsageRange
    points: list[UsagePoint]


class TopModelShare(BaseModel):
    id: str
    model: str
    displayName: str | None = None
    provider: str
    percent: int
    tokenTotal: int


class RequestIoPayload(BaseModel):
    input: str | None = None
    output: str | None = None


class RequestRow(BaseModel):
    id: str
    upstreamRequestId: str | None = None
    timestamp: str
    client: KnownClientName
    endpoint: RequestEndpoint
    provider: str
    model: str
    inputTokens: int
    outputTokens: int
    totalTokens: int
    costUsd: float
    latencyMs: int
    streaming: bool
    status: RequestStatus
    io: RequestIoPayload | None = None


class RequestTotals(BaseModel):
    requestsToday: int
    avgLatencyMs: int
    errorRate: float
    streamingRate: float


class RequestFilters(BaseModel):
    providers: list[str]
    models: list[str]
    clients: list[KnownClientName]
    statuses: list[RequestStatus]
    endpoints: list[RequestEndpoint]


class OverviewAnalyticsResponse(BaseModel):
    metrics: list[OverviewMetric]
    tokenUsage: dict[UsageRange, TimeRangeUsage]
    topModels: list[TopModelShare]
    recentRequests: list[RequestRow]


class RequestsAnalyticsResponse(BaseModel):
    totals: RequestTotals
    filters: RequestFilters
    rows: list[RequestRow]
    pagination: "RequestPagination"


class RequestPagination(BaseModel):
    page: int
    pageSize: int
    totalItems: int
    totalPages: int


class ModelUsageSummary(BaseModel):
    id: str
    provider: str
    model: str
    displayName: str | None = None
    requestCount: int
    tokenTotal: int
    costUsd: float
    avgLatencyMs: int
    errorRate: float


class ModelsTotals(BaseModel):
    tokenTotal: int
    costUsd: float
    requestCount: int
    avgLatencyMs: int
    errorRate: float


class ModelsAnalyticsResponse(BaseModel):
    totals: ModelsTotals
    models: list[ModelUsageSummary]


class CostBucket(BaseModel):
    label: str
    amountUsd: float


class CostTotals(BaseModel):
    todayUsd: float
    weekUsd: float
    monthUsd: float


class CostsAnalyticsResponse(BaseModel):
    note: str
    totals: CostTotals
    byProvider: list[CostBucket]
    byModel: list[CostBucket]
    dailyTrend: list[CostBucket]
    recentHighCostRequests: list[RequestRow]


class ProviderTrendPoint(BaseModel):
    date: str
    requests: int
    successfulRequests: int
    costUsd: float


class ProviderDetail(BaseModel):
    providerId: str
    costBreakdown: list[CostBucket]
    requestTrend: list[ProviderTrendPoint]
    notes: str


class ProviderHealthCard(BaseModel):
    id: str
    slug: str
    displayName: str
    type: ProviderType
    status: Literal["operational", "degraded", "offline"]
    baseUrl: str
    requestsToday: int
    successRate: float
    errorRate: float
    avgLatencyMs: int
    availableModelCount: int
    lastCheckedAt: str
    lastError: str | None


class ProviderHealthPayload(BaseModel):
    cards: list[ProviderHealthCard]
    details: list[ProviderDetail]
