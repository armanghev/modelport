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

export interface ModelUsageSummary {
  id: string;
  provider: string;
  model: string;
  displayName?: string;
  requestCount: number;
  tokenTotal: number;
  costUsd: number;
  avgLatencyMs: number;
  errorRate: number;
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

export interface ProviderBillingCycle {
  planName: string;
  periodStart: string;
  periodEnd: string;
  nextInvoiceDate: string;
  budgetUsd: number;
  spentUsd: number;
  forecastUsd: number;
}

export interface ProviderTrendPoint {
  date: string;
  requests: number;
  successfulRequests: number;
  costUsd: number;
}

export interface ProviderDetail {
  providerId: string;
  region: string;
  supportTier: string;
  billingCycle: ProviderBillingCycle;
  costBreakdown: CostBucket[];
  requestTrend: ProviderTrendPoint[];
  notes: string;
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

export interface ApiKeyStatus {
  provider: string;
  envVar: string;
  configured: boolean;
  maskedKey: string;
  fullKey: string;
  baseUrl?: string;
  headers?: Array<{
    key: string;
    value: string;
  }>;
}

export interface SettingsTrackingOption {
  id: string;
  label: string;
  description: string;
  enabled: boolean;
}

export interface SettingsAppearance {
  theme: string;
  themes: string[];
  autoRefreshInterval: string;
  autoRefreshIntervals: string[];
}

export interface DashboardMockData {
  generatedAt: string;
  proxy: {
    name: string;
    version: string;
    status: "running" | "stopped" | "error";
    systemHealthLabel: string;
    baseUrl: string;
  };
  overview: {
    metrics: OverviewMetric[];
    tokenUsage: Record<UsageRange, TimeRangeUsage>;
    topModels: TopModelShare[];
    recentRequests: RequestRow[];
  };
  requests: {
    totals: {
      requestsToday: number;
      avgLatencyMs: number;
      errorRate: number;
      streamingRate: number;
    };
    filters: {
      providers: string[];
      models: string[];
      clients: RequestRow["client"][];
      statuses: RequestStatus[];
      endpoints: RequestRow["endpoint"][];
    };
    rows: RequestRow[];
  };
  models: {
    totals: {
      tokenTotal: number;
      costUsd: number;
      requestCount: number;
      avgLatencyMs: number;
      errorRate: number;
    };
    models: ModelUsageSummary[];
  };
  providers: {
    cards: ProviderHealth[];
    details: ProviderDetail[];
  };
  costs: {
    note: string;
    totals: {
      todayUsd: number;
      weekUsd: number;
      monthUsd: number;
    };
    byProvider: CostBucket[];
    byModel: CostBucket[];
    dailyTrend: CostBucket[];
  };
  settings: {
    apiKeys: ApiKeyStatus[];
    pricingTable: PricingEntry[];
    tracking: SettingsTrackingOption[];
    appearance: SettingsAppearance;
  };
}
