export type TrendDirection = "up" | "down" | "neutral";
export type ProviderStatus = "operational" | "degraded" | "offline";
export type RequestStatus = "success" | "error" | "cancelled";
export type UsageRange = "1h" | "6h" | "24h" | "7d" | "30d";
export type ProviderType =
  | "openai_compatible"
  | "anthropic_compatible"
  | "local_openai_compatible";

export interface MetricTrend {
  direction: TrendDirection;
  percent: number;
  comparisonLabel: string;
}

export interface OverviewMetric {
  id: "total_tokens" | "estimated_cost" | "top_model" | "average_latency";
  label: string;
  value: string;
  subtext: string;
  trend?: MetricTrend;
}

export interface UsagePoint {
  label: string;
  tokens: number;
}

export interface TimeRangeUsage {
  range: UsageRange;
  points: UsagePoint[];
}

export interface TopModelShare {
  id: string;
  model: string;
  displayName?: string;
  provider: string;
  percent: number;
  tokenTotal: number;
}

export interface RequestIoPayload {
  input?: string | null;
  output?: string | null;
}

export interface RequestRow {
  id: string;
  upstreamRequestId?: string | null;
  timestamp: string;
  client: "Claude Code" | "OpenAI SDK" | "Gemini CLI" | "Custom App" | "Codex" | "Cursor";
  endpoint: "/v1/messages" | "/v1/chat/completions";
  provider: string;
  model: string;
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  costUsd: number;
  latencyMs: number;
  streaming: boolean;
  status: RequestStatus;
  io?: RequestIoPayload | null;
}

export interface RequestTotals {
  requestsToday: number;
  avgLatencyMs: number;
  errorRate: number;
  streamingRate: number;
}

export interface RequestFilters {
  providers: string[];
  models: string[];
  clients: RequestRow["client"][];
  statuses: RequestStatus[];
  endpoints: RequestRow["endpoint"][];
}

export interface OverviewAnalyticsData {
  metrics: OverviewMetric[];
  tokenUsage: Record<UsageRange, TimeRangeUsage>;
  topModels: TopModelShare[];
  recentRequests: RequestRow[];
}

export interface RequestsAnalyticsData {
  totals: RequestTotals;
  filters: RequestFilters;
  rows: RequestRow[];
}

export interface CostTotals {
  todayUsd: number;
  weekUsd: number;
  monthUsd: number;
}

export interface CostsAnalyticsData {
  totals: CostTotals;
  byProvider: CostBucket[];
  byModel: CostBucket[];
  recentHighCostRequests: RequestRow[];
}

export interface ProviderHealth {
  id: string;
  slug: string;
  displayName: string;
  type: ProviderType;
  status: ProviderStatus;
  baseUrl: string;
  requestsToday: number;
  successRate: number;
  errorRate: number;
  avgLatencyMs: number;
  availableModelCount: number;
  lastCheckedAt: string;
  lastError: string | null;
}

export interface ProviderTrendPoint {
  date: string;
  requests: number;
  successfulRequests: number;
  costUsd: number;
}

export interface ProviderDetail {
  providerId: string;
  costBreakdown: CostBucket[];
  requestTrend: ProviderTrendPoint[];
}

export interface CostBucket {
  label: string;
  amountUsd: number;
}

export interface PricingEntry {
  provider: string;
  model: string;
  inputPer1kUsd: number;
  outputPer1kUsd: number;
}

export interface SettingsTrackingOption {
  id: string;
  label: string;
  description: string;
  enabled: boolean;
}

export interface SettingsAppearance {
  autoRefreshInterval: string;
  autoRefreshIntervals: string[];
}
