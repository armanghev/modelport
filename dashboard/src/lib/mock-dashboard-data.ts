export type TrendDirection = "up" | "down" | "neutral";
export type ProviderStatus = "operational" | "degraded" | "offline";
export type RequestStatus = "success" | "error" | "cancelled";
export type UsageRange = "1h" | "6h" | "24h" | "7d" | "30d";
export type ProviderType =
  | "openai_compatible"
  | "anthropic_compatible"
  | "local_openai_compatible";
export type LoggingLevel = "debug" | "info" | "warn" | "error";

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
  provider: string;
  percent: number;
  tokenTotal: number;
}

export interface RequestRow {
  id: string;
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

export interface RoutingRule {
  match: string;
  primaryProvider: string;
  fallbackProviders: string[];
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
  keyHint: string;
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
    routingRules: RoutingRule[];
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
    defaults: {
      inputFormat: "anthropic" | "openai";
      provider: string;
    };
    apiKeys: ApiKeyStatus[];
    pricingTable: PricingEntry[];
    logging: {
      level: LoggingLevel;
      availableLevels: LoggingLevel[];
    };
    retention: {
      requestLogsDays: number;
      providerHealthDays: number;
      metricGranularity: "5m" | "15m" | "1h";
    };
  };
}

const requests: RequestRow[] = [
  {
    id: "req_01",
    timestamp: "2026-05-27T09:24:31-07:00",
    client: "Claude Code",
    endpoint: "/v1/messages",
    provider: "Anthropic",
    model: "Claude 3.5 Sonnet",
    inputTokens: 96342,
    outputTokens: 57550,
    totalTokens: 153892,
    costUsd: 0.0542,
    latencyMs: 801,
    streaming: true,
    status: "success",
  },
  {
    id: "req_02",
    timestamp: "2026-05-27T09:23:47-07:00",
    client: "OpenAI SDK",
    endpoint: "/v1/chat/completions",
    provider: "OpenAI",
    model: "GPT-4.1",
    inputTokens: 49010,
    outputTokens: 29332,
    totalTokens: 78342,
    costUsd: 0.0321,
    latencyMs: 744,
    streaming: true,
    status: "success",
  },
  {
    id: "req_03",
    timestamp: "2026-05-27T09:22:19-07:00",
    client: "Gemini CLI",
    endpoint: "/v1/chat/completions",
    provider: "Gemini",
    model: "Gemini 2.5 Pro",
    inputTokens: 127882,
    outputTokens: 73831,
    totalTokens: 201713,
    costUsd: 0.0718,
    latencyMs: 936,
    streaming: true,
    status: "success",
  },
  {
    id: "req_04",
    timestamp: "2026-05-27T09:21:02-07:00",
    client: "Claude Code",
    endpoint: "/v1/messages",
    provider: "Anthropic",
    model: "Claude 3.5 Sonnet",
    inputTokens: 62920,
    outputTokens: 35751,
    totalTokens: 98671,
    costUsd: 0.0346,
    latencyMs: 792,
    streaming: true,
    status: "success",
  },
  {
    id: "req_05",
    timestamp: "2026-05-27T09:19:58-07:00",
    client: "OpenAI SDK",
    endpoint: "/v1/chat/completions",
    provider: "OpenRouter",
    model: "GPT-4o mini",
    inputTokens: 28018,
    outputTokens: 17192,
    totalTokens: 45210,
    costUsd: 0.0063,
    latencyMs: 623,
    streaming: false,
    status: "success",
  },
  {
    id: "req_06",
    timestamp: "2026-05-27T09:18:41-07:00",
    client: "Custom App",
    endpoint: "/v1/chat/completions",
    provider: "OpenAI",
    model: "GPT-4o mini",
    inputTokens: 12110,
    outputTokens: 5644,
    totalTokens: 17754,
    costUsd: 0.0031,
    latencyMs: 548,
    streaming: false,
    status: "success",
  },
  {
    id: "req_07",
    timestamp: "2026-05-27T09:17:14-07:00",
    client: "Codex",
    endpoint: "/v1/messages",
    provider: "Anthropic",
    model: "Claude 3 Haiku",
    inputTokens: 19444,
    outputTokens: 12389,
    totalTokens: 31833,
    costUsd: 0.0054,
    latencyMs: 512,
    streaming: true,
    status: "success",
  },
  {
    id: "req_08",
    timestamp: "2026-05-27T09:15:59-07:00",
    client: "Custom App",
    endpoint: "/v1/chat/completions",
    provider: "Ollama",
    model: "qwen2.5-coder",
    inputTokens: 6088,
    outputTokens: 4110,
    totalTokens: 10198,
    costUsd: 0,
    latencyMs: 1404,
    streaming: true,
    status: "cancelled",
  },
  {
    id: "req_09",
    timestamp: "2026-05-27T09:14:20-07:00",
    client: "Claude Code",
    endpoint: "/v1/messages",
    provider: "OpenRouter",
    model: "Claude 3.5 Sonnet",
    inputTokens: 84990,
    outputTokens: 49712,
    totalTokens: 134702,
    costUsd: 0.0418,
    latencyMs: 1188,
    streaming: true,
    status: "error",
  },
  {
    id: "req_10",
    timestamp: "2026-05-27T09:13:04-07:00",
    client: "OpenAI SDK",
    endpoint: "/v1/chat/completions",
    provider: "Gemini",
    model: "Gemini 2.5 Flash",
    inputTokens: 15802,
    outputTokens: 10911,
    totalTokens: 26713,
    costUsd: 0.0048,
    latencyMs: 486,
    streaming: true,
    status: "success",
  },
];

function buildProviderTrend(
  startDate: string,
  requestsByDay: number[],
  successRate: number,
  dailyCostMultiplier: number,
): ProviderTrendPoint[] {
  const start = new Date(startDate);

  return requestsByDay.map((requests, index) => {
    const date = new Date(start);
    date.setDate(start.getDate() + index);
    const successfulRequests = Math.round(requests * successRate);
    const costUsd = Number((requests * dailyCostMultiplier).toFixed(2));

    return {
      date: date.toISOString(),
      requests,
      successfulRequests,
      costUsd,
    };
  });
}

const providerDetails: ProviderDetail[] = [
  {
    providerId: "prov_openai",
    region: "us-east-1",
    supportTier: "Enterprise",
    billingCycle: {
      planName: "Scale Tier",
      periodStart: "2026-05-01",
      periodEnd: "2026-05-31",
      nextInvoiceDate: "2026-06-01",
      budgetUsd: 6500,
      spentUsd: 4821.37,
      forecastUsd: 5312.18,
    },
    costBreakdown: [
      { label: "Completions", amountUsd: 2831.42 },
      { label: "Reasoning", amountUsd: 1167.83 },
      { label: "Embeddings", amountUsd: 432.16 },
      { label: "Audio", amountUsd: 389.96 },
    ],
    requestTrend: buildProviderTrend(
      "2026-05-01T00:00:00-07:00",
      [
        412, 398, 420, 436, 452, 468, 479, 491, 505, 523, 538, 546, 559, 571,
        584, 596, 612, 625, 619, 637, 651, 662, 675, 688, 703, 712, 721, 735,
        744, 759,
      ],
      0.985,
      3.08,
    ),
    notes: "Primary production provider for reasoning and multimodal traffic.",
  },
  {
    providerId: "prov_anthropic",
    region: "us-west-2",
    supportTier: "Enterprise",
    billingCycle: {
      planName: "Team Annual",
      periodStart: "2026-05-01",
      periodEnd: "2026-05-31",
      nextInvoiceDate: "2026-06-01",
      budgetUsd: 5200,
      spentUsd: 3962.08,
      forecastUsd: 4270.44,
    },
    costBreakdown: [
      { label: "Claude Sonnet", amountUsd: 2684.73 },
      { label: "Claude Opus", amountUsd: 821.65 },
      { label: "Claude Haiku", amountUsd: 455.7 },
    ],
    requestTrend: buildProviderTrend(
      "2026-05-01T00:00:00-07:00",
      [
        368, 372, 379, 387, 391, 405, 418, 421, 433, 446, 452, 461, 473, 486,
        498, 511, 524, 538, 543, 552, 563, 576, 585, 597, 612, 626, 641, 652,
        663, 679,
      ],
      0.989,
      2.41,
    ),
    notes: "Preferred provider for Claude-specific routes and long-context prompts.",
  },
  {
    providerId: "prov_gemini",
    region: "us-central1",
    supportTier: "Standard",
    billingCycle: {
      planName: "Pay as you go",
      periodStart: "2026-05-01",
      periodEnd: "2026-05-31",
      nextInvoiceDate: "2026-06-01",
      budgetUsd: 2400,
      spentUsd: 1594.92,
      forecastUsd: 1830.16,
    },
    costBreakdown: [
      { label: "Gemini Pro", amountUsd: 1014.43 },
      { label: "Gemini Flash", amountUsd: 489.17 },
      { label: "Context caching", amountUsd: 91.32 },
    ],
    requestTrend: buildProviderTrend(
      "2026-05-01T00:00:00-07:00",
      [
        221, 228, 233, 241, 248, 252, 259, 268, 276, 281, 288, 295, 301, 306,
        312, 321, 326, 338, 347, 355, 362, 369, 377, 384, 390, 396, 401, 409,
        417, 426,
      ],
      0.969,
      1.27,
    ),
    notes: "Degraded due to rate limiting bursts on peak hours.",
  },
  {
    providerId: "prov_openrouter",
    region: "global",
    supportTier: "Pro",
    billingCycle: {
      planName: "Volume",
      periodStart: "2026-05-01",
      periodEnd: "2026-05-31",
      nextInvoiceDate: "2026-06-01",
      budgetUsd: 1800,
      spentUsd: 944.53,
      forecastUsd: 1106.2,
    },
    costBreakdown: [
      { label: "Claude routes", amountUsd: 392.77 },
      { label: "GPT routes", amountUsd: 288.49 },
      { label: "Fallback traffic", amountUsd: 263.27 },
    ],
    requestTrend: buildProviderTrend(
      "2026-05-01T00:00:00-07:00",
      [
        132, 126, 129, 134, 139, 141, 144, 147, 151, 156, 159, 162, 164, 168,
        171, 173, 176, 179, 181, 184, 188, 192, 196, 199, 201, 204, 206, 209,
        211, 215,
      ],
      0.979,
      0.84,
    ),
    notes: "Used heavily for fallback and specialty model routing.",
  },
  {
    providerId: "prov_ollama",
    region: "local-gpu",
    supportTier: "Self-hosted",
    billingCycle: {
      planName: "Infra-backed",
      periodStart: "2026-05-01",
      periodEnd: "2026-05-31",
      nextInvoiceDate: "2026-06-01",
      budgetUsd: 420,
      spentUsd: 278.61,
      forecastUsd: 334.08,
    },
    costBreakdown: [
      { label: "GPU runtime", amountUsd: 182.14 },
      { label: "Storage", amountUsd: 54.33 },
      { label: "Power", amountUsd: 42.14 },
    ],
    requestTrend: buildProviderTrend(
      "2026-05-01T00:00:00-07:00",
      [
        44, 47, 45, 49, 53, 57, 58, 61, 63, 66, 68, 70, 73, 75, 78, 82, 84, 87,
        89, 92, 95, 97, 101, 103, 106, 109, 111, 115, 117, 121,
      ],
      0.948,
      0.18,
    ),
    notes: "Local provider with intermittent VRAM pressure under concurrent load.",
  },
  {
    providerId: "prov_azure_openai",
    region: "eastus2",
    supportTier: "Enterprise",
    billingCycle: {
      planName: "Enterprise commitment",
      periodStart: "2026-05-01",
      periodEnd: "2026-05-31",
      nextInvoiceDate: "2026-06-01",
      budgetUsd: 3100,
      spentUsd: 1872.44,
      forecastUsd: 2140.03,
    },
    costBreakdown: [
      { label: "Completions", amountUsd: 1108.72 },
      { label: "Embeddings", amountUsd: 429.11 },
      { label: "Image generation", amountUsd: 334.61 },
    ],
    requestTrend: buildProviderTrend(
      "2026-05-01T00:00:00-07:00",
      [
        121, 124, 129, 132, 137, 141, 146, 149, 152, 156, 158, 163, 168, 173,
        177, 181, 186, 190, 194, 197, 202, 205, 209, 212, 216, 219, 224, 227,
        232, 236,
      ],
      0.987,
      1.02,
    ),
    notes: "Secondary OpenAI-compatible provider for enterprise failover.",
  },
];

export const dashboardMockData: DashboardMockData = {
  generatedAt: "2026-05-27T09:30:00-07:00",
  proxy: {
    name: "Local AI Proxy",
    version: "v1.2.0",
    status: "running",
    systemHealthLabel: "All systems operational",
    baseUrl: "http://localhost:8000",
  },
  overview: {
    metrics: [
      {
        id: "total_tokens",
        label: "Total tokens today",
        value: "24.7M",
        subtext: "vs yesterday",
        trend: {
          direction: "up",
          percent: 18.6,
          comparisonLabel: "vs yesterday",
        },
      },
      {
        id: "estimated_cost",
        label: "Estimated cost",
        value: "$8.62",
        subtext: "vs yesterday",
        trend: {
          direction: "down",
          percent: 7.3,
          comparisonLabel: "vs yesterday",
        },
      },
      {
        id: "top_model",
        label: "Top model",
        value: "Claude 3.5 Sonnet",
        subtext: "43% of total tokens",
      },
      {
        id: "average_latency",
        label: "Average latency",
        value: "842 ms",
        subtext: "vs yesterday",
        trend: {
          direction: "down",
          percent: 6.1,
          comparisonLabel: "vs yesterday",
        },
      },
    ],
    tokenUsage: {
      "1h": {
        range: "1h",
        points: [
          { label: "-55m", tokens: 72000 },
          { label: "-50m", tokens: 76000 },
          { label: "-45m", tokens: 70200 },
          { label: "-40m", tokens: 83400 },
          { label: "-35m", tokens: 79000 },
          { label: "-30m", tokens: 88600 },
          { label: "-25m", tokens: 84200 },
          { label: "-20m", tokens: 91800 },
          { label: "-15m", tokens: 86000 },
          { label: "-10m", tokens: 81100 },
          { label: "-5m", tokens: 78400 },
          { label: "Now", tokens: 83200 },
        ],
      },
      "6h": {
        range: "6h",
        points: [
          { label: "4:00", tokens: 332000 },
          { label: "4:15", tokens: 351000 },
          { label: "4:30", tokens: 347000 },
          { label: "4:45", tokens: 365000 },
          { label: "5:00", tokens: 378000 },
          { label: "5:15", tokens: 391000 },
          { label: "5:30", tokens: 402000 },
          { label: "5:45", tokens: 418000 },
          { label: "6:00", tokens: 429000 },
          { label: "6:15", tokens: 452000 },
          { label: "6:30", tokens: 479000 },
          { label: "6:45", tokens: 498000 },
          { label: "7:00", tokens: 515000 },
          { label: "7:15", tokens: 537000 },
          { label: "7:30", tokens: 521000 },
          { label: "7:45", tokens: 546000 },
          { label: "8:00", tokens: 568000 },
          { label: "8:15", tokens: 583000 },
          { label: "8:30", tokens: 561000 },
          { label: "8:45", tokens: 549000 },
          { label: "9:00", tokens: 525000 },
          { label: "9:15", tokens: 501000 },
          { label: "9:30", tokens: 487000 },
          { label: "9:45", tokens: 466000 },
        ],
      },
      "24h": {
        range: "24h",
        points: [
          { label: "12 AM", tokens: 1200000 },
          { label: "1 AM", tokens: 1010000 },
          { label: "2 AM", tokens: 860000 },
          { label: "3 AM", tokens: 900000 },
          { label: "4 AM", tokens: 1020000 },
          { label: "5 AM", tokens: 1290000 },
          { label: "6 AM", tokens: 1480000 },
          { label: "7 AM", tokens: 1780000 },
          { label: "8 AM", tokens: 2010000 },
          { label: "9 AM", tokens: 2310000 },
          { label: "10 AM", tokens: 2220000 },
          { label: "11 AM", tokens: 2310000 },
          { label: "12 PM", tokens: 2590000 },
          { label: "1 PM", tokens: 2900000 },
          { label: "2 PM", tokens: 3020000 },
          { label: "3 PM", tokens: 3200000 },
          { label: "4 PM", tokens: 3510000 },
          { label: "5 PM", tokens: 3210000 },
          { label: "6 PM", tokens: 3030000 },
          { label: "7 PM", tokens: 2810000 },
          { label: "8 PM", tokens: 2500000 },
          { label: "9 PM", tokens: 2240000 },
          { label: "10 PM", tokens: 1940000 },
          { label: "11 PM", tokens: 1730000 },
        ],
      },
      "7d": {
        range: "7d",
        points: [
          { label: "Thu", tokens: 18200000 },
          { label: "Fri", tokens: 19500000 },
          { label: "Sat", tokens: 14300000 },
          { label: "Sun", tokens: 12800000 },
          { label: "Mon", tokens: 21100000 },
          { label: "Tue", tokens: 22600000 },
          { label: "Wed", tokens: 24700000 },
        ],
      },
      "30d": {
        range: "30d",
        points: [
          { label: "D1", tokens: 11000000 },
          { label: "D2", tokens: 12500000 },
          { label: "D3", tokens: 11900000 },
          { label: "D4", tokens: 12100000 },
          { label: "D5", tokens: 13200000 },
          { label: "D6", tokens: 13800000 },
          { label: "D7", tokens: 14200000 },
          { label: "D8", tokens: 14800000 },
          { label: "D9", tokens: 15200000 },
          { label: "D10", tokens: 16000000 },
          { label: "D11", tokens: 16500000 },
          { label: "D12", tokens: 17200000 },
          { label: "D13", tokens: 17500000 },
          { label: "D14", tokens: 16900000 },
          { label: "D15", tokens: 17700000 },
          { label: "D16", tokens: 18100000 },
          { label: "D17", tokens: 18700000 },
          { label: "D18", tokens: 19000000 },
          { label: "D19", tokens: 20100000 },
          { label: "D20", tokens: 20800000 },
          { label: "D21", tokens: 21400000 },
          { label: "D22", tokens: 20500000 },
          { label: "D23", tokens: 21800000 },
          { label: "D24", tokens: 22600000 },
          { label: "D25", tokens: 21900000 },
          { label: "D26", tokens: 23200000 },
          { label: "D27", tokens: 23800000 },
          { label: "D28", tokens: 24100000 },
          { label: "D29", tokens: 24500000 },
          { label: "D30", tokens: 24700000 },
        ],
      },
    },
    topModels: [
      {
        id: "top_01",
        model: "Claude 3.5 Sonnet",
        provider: "Anthropic",
        percent: 43,
        tokenTotal: 10600000,
      },
      {
        id: "top_02",
        model: "GPT-4.1",
        provider: "OpenAI",
        percent: 28,
        tokenTotal: 6900000,
      },
      {
        id: "top_03",
        model: "Gemini 2.5 Pro",
        provider: "Gemini",
        percent: 17,
        tokenTotal: 4200000,
      },
      {
        id: "top_04",
        model: "Claude 3 Haiku",
        provider: "Anthropic",
        percent: 7,
        tokenTotal: 1700000,
      },
      {
        id: "top_05",
        model: "GPT-4o mini",
        provider: "OpenAI",
        percent: 5,
        tokenTotal: 1300000,
      },
    ],
    recentRequests: requests.slice(0, 5),
  },
  requests: {
    totals: {
      requestsToday: 1847,
      avgLatencyMs: 842,
      errorRate: 1.9,
      streamingRate: 76.4,
    },
    filters: {
      providers: [
        "OpenAI",
        "Anthropic",
        "Gemini",
        "OpenRouter",
        "Ollama",
        "LM Studio",
      ],
      models: [
        "Claude 3.5 Sonnet",
        "Claude 3 Haiku",
        "GPT-4.1",
        "GPT-4o mini",
        "Gemini 2.5 Pro",
        "Gemini 2.5 Flash",
        "qwen2.5-coder",
      ],
      clients: ["Claude Code", "OpenAI SDK", "Gemini CLI", "Custom App", "Codex"],
      statuses: ["success", "error", "cancelled"],
      endpoints: ["/v1/messages", "/v1/chat/completions"],
    },
    rows: requests,
  },
  models: {
    totals: {
      tokenTotal: 24700000,
      costUsd: 8.62,
      requestCount: 1847,
      avgLatencyMs: 842,
      errorRate: 1.9,
    },
    models: [
      {
        id: "mod_01",
        provider: "Anthropic",
        model: "claude-3-5-sonnet-latest",
        displayName: "Claude 3.5 Sonnet",
        requestCount: 611,
        tokenTotal: 10600000,
        costUsd: 3.92,
        avgLatencyMs: 808,
        errorRate: 1.2,
      },
      {
        id: "mod_02",
        provider: "OpenAI",
        model: "gpt-4.1",
        displayName: "GPT-4.1",
        requestCount: 418,
        tokenTotal: 6900000,
        costUsd: 2.33,
        avgLatencyMs: 764,
        errorRate: 1.6,
      },
      {
        id: "mod_03",
        provider: "Gemini",
        model: "gemini-2.5-pro",
        displayName: "Gemini 2.5 Pro",
        requestCount: 276,
        tokenTotal: 4200000,
        costUsd: 1.51,
        avgLatencyMs: 935,
        errorRate: 2.4,
      },
      {
        id: "mod_04",
        provider: "OpenAI",
        model: "gpt-4o-mini",
        displayName: "GPT-4o Mini",
        requestCount: 229,
        tokenTotal: 1300000,
        costUsd: 0.23,
        avgLatencyMs: 522,
        errorRate: 2.1,
      },
      {
        id: "mod_05",
        provider: "Anthropic",
        model: "claude-3-haiku-20240307",
        displayName: "Claude 3 Haiku",
        requestCount: 313,
        tokenTotal: 1700000,
        costUsd: 0.63,
        avgLatencyMs: 551,
        errorRate: 1.8,
      },
      {
        id: "mod_06",
        provider: "OpenAI",
        model: "o1",
        displayName: "o1",
        requestCount: 192,
        tokenTotal: 960000,
        costUsd: 0.58,
        avgLatencyMs: 1221,
        errorRate: 1.4,
      },
      {
        id: "mod_07",
        provider: "OpenAI",
        model: "o3",
        displayName: "o3",
        requestCount: 157,
        tokenTotal: 882000,
        costUsd: 0.67,
        avgLatencyMs: 1316,
        errorRate: 1.9,
      },
      {
        id: "mod_08",
        provider: "Anthropic",
        model: "claude-3-opus-20240229",
        displayName: "Claude 3 Opus",
        requestCount: 144,
        tokenTotal: 840000,
        costUsd: 0.92,
        avgLatencyMs: 1490,
        errorRate: 2.6,
      },
      {
        id: "mod_09",
        provider: "OpenAI",
        model: "gpt-4o",
        displayName: "GPT-4o",
        requestCount: 139,
        tokenTotal: 790000,
        costUsd: 0.48,
        avgLatencyMs: 702,
        errorRate: 1.3,
      },
      {
        id: "mod_10",
        provider: "Gemini",
        model: "gemini-2.5-flash",
        displayName: "Gemini 2.5 Flash",
        requestCount: 178,
        tokenTotal: 760000,
        costUsd: 0.18,
        avgLatencyMs: 468,
        errorRate: 2.8,
      },
      {
        id: "mod_11",
        provider: "OpenAI",
        model: "gpt-4.1-mini",
        displayName: "GPT-4.1 Mini",
        requestCount: 166,
        tokenTotal: 720000,
        costUsd: 0.16,
        avgLatencyMs: 502,
        errorRate: 1.7,
      },
      {
        id: "mod_12",
        provider: "OpenAI",
        model: "gpt-4.1-nano",
        displayName: "GPT-4.1 Nano",
        requestCount: 129,
        tokenTotal: 610000,
        costUsd: 0.08,
        avgLatencyMs: 401,
        errorRate: 1.5,
      },
      {
        id: "mod_13",
        provider: "Anthropic",
        model: "claude-3-sonnet-20240229",
        displayName: "Claude 3 Sonnet",
        requestCount: 117,
        tokenTotal: 590000,
        costUsd: 0.28,
        avgLatencyMs: 734,
        errorRate: 1.9,
      },
      {
        id: "mod_14",
        provider: "Anthropic",
        model: "claude-instant-1.2",
        displayName: "Claude Instant 1.2",
        requestCount: 98,
        tokenTotal: 520000,
        costUsd: 0.07,
        avgLatencyMs: 455,
        errorRate: 2.2,
      },
      {
        id: "mod_15",
        provider: "Gemini",
        model: "gemini-1.5-flash",
        displayName: "Gemini 1.5 Flash",
        requestCount: 102,
        tokenTotal: 480000,
        costUsd: 0.09,
        avgLatencyMs: 439,
        errorRate: 2.6,
      },
      {
        id: "mod_16",
        provider: "Gemini",
        model: "gemini-1.5-pro",
        displayName: "Gemini 1.5 Pro",
        requestCount: 88,
        tokenTotal: 420000,
        costUsd: 0.17,
        avgLatencyMs: 845,
        errorRate: 3.2,
      },
      {
        id: "mod_17",
        provider: "Anthropic",
        model: "claude-2.1",
        displayName: "Claude 2.1",
        requestCount: 79,
        tokenTotal: 370000,
        costUsd: 0.14,
        avgLatencyMs: 673,
        errorRate: 2.4,
      },
      {
        id: "mod_18",
        provider: "OpenAI",
        model: "gpt-3.5-turbo",
        displayName: "GPT-3.5 Turbo",
        requestCount: 131,
        tokenTotal: 350000,
        costUsd: 0.04,
        avgLatencyMs: 392,
        errorRate: 1.8,
      },
      {
        id: "mod_19",
        provider: "OpenAI",
        model: "gpt-4-turbo",
        displayName: "GPT-4 Turbo",
        requestCount: 67,
        tokenTotal: 330000,
        costUsd: 0.21,
        avgLatencyMs: 882,
        errorRate: 2.3,
      },
      {
        id: "mod_20",
        provider: "Anthropic",
        model: "claude-3-opus-lite",
        displayName: "Claude 3 Opus Lite",
        requestCount: 52,
        tokenTotal: 280000,
        costUsd: 0.19,
        avgLatencyMs: 1033,
        errorRate: 2.9,
      },
      {
        id: "mod_21",
        provider: "Gemini",
        model: "gemini-2.0-flash",
        displayName: "Gemini 2.0 Flash",
        requestCount: 75,
        tokenTotal: 260000,
        costUsd: 0.05,
        avgLatencyMs: 421,
        errorRate: 2.7,
      },
      {
        id: "mod_22",
        provider: "Gemini",
        model: "gemini-2.0-pro",
        displayName: "Gemini 2.0 Pro",
        requestCount: 46,
        tokenTotal: 215000,
        costUsd: 0.11,
        avgLatencyMs: 792,
        errorRate: 3.1,
      },
      {
        id: "mod_23",
        provider: "OpenAI",
        model: "gpt-4o-realtime-preview",
        displayName: "GPT-4o Realtime",
        requestCount: 42,
        tokenTotal: 196000,
        costUsd: 0.12,
        avgLatencyMs: 289,
        errorRate: 2.5,
      },
      {
        id: "mod_24",
        provider: "Anthropic",
        model: "claude-3-7-sonnet-latest",
        displayName: "Claude 3.7 Sonnet",
        requestCount: 39,
        tokenTotal: 184000,
        costUsd: 0.09,
        avgLatencyMs: 912,
        errorRate: 2.2,
      },
      {
        id: "mod_25",
        provider: "OpenAI",
        model: "gpt-4o-mini-audio-preview",
        displayName: "GPT-4o Mini Audio",
        requestCount: 33,
        tokenTotal: 151000,
        costUsd: 0.06,
        avgLatencyMs: 341,
        errorRate: 2.9,
      },
      {
        id: "mod_26",
        provider: "Anthropic",
        model: "claude-3.5-nano-beta",
        displayName: "Claude 3.5 Nano Beta",
        requestCount: 51,
        tokenTotal: 128000,
        costUsd: 0.01,
        avgLatencyMs: 322,
        errorRate: 1.1,
      },
      {
        id: "mod_27",
        provider: "Gemini",
        model: "gemini-2.0-nano",
        displayName: "Gemini 2.0 Nano",
        requestCount: 73,
        tokenTotal: 162000,
        costUsd: 0.03,
        avgLatencyMs: 336,
        errorRate: 1.3,
      },
      {
        id: "mod_28",
        provider: "OpenAI",
        model: "gpt-4.1-ultra-mini",
        displayName: "GPT-4.1 Ultra Mini",
        requestCount: 86,
        tokenTotal: 214000,
        costUsd: 0.08,
        avgLatencyMs: 379,
        errorRate: 1.5,
      },
      {
        id: "mod_29",
        provider: "Gemini",
        model: "gemini-1.5-lite",
        displayName: "Gemini 1.5 Lite",
        requestCount: 94,
        tokenTotal: 243000,
        costUsd: 0.13,
        avgLatencyMs: 402,
        errorRate: 1.8,
      },
      {
        id: "mod_30",
        provider: "OpenAI",
        model: "gpt-4o-pico",
        displayName: "GPT-4o Pico",
        requestCount: 112,
        tokenTotal: 302000,
        costUsd: 0.21,
        avgLatencyMs: 447,
        errorRate: 1.9,
      },
      {
        id: "mod_31",
        provider: "Anthropic",
        model: "claude-3.5-haiku-plus",
        displayName: "Claude 3.5 Haiku Plus",
        requestCount: 124,
        tokenTotal: 385000,
        costUsd: 0.55,
        avgLatencyMs: 519,
        errorRate: 2.2,
      },
      {
        id: "mod_32",
        provider: "Gemini",
        model: "gemini-2.5-reasoner-mini",
        displayName: "Gemini 2.5 Reasoner Mini",
        requestCount: 137,
        tokenTotal: 448000,
        costUsd: 0.89,
        avgLatencyMs: 562,
        errorRate: 2.4,
      },
      {
        id: "mod_33",
        provider: "OpenAI",
        model: "gpt-4.1-reasoning-lite",
        displayName: "GPT-4.1 Reasoning Lite",
        requestCount: 149,
        tokenTotal: 522000,
        costUsd: 1.44,
        avgLatencyMs: 604,
        errorRate: 2.1,
      },
      {
        id: "mod_34",
        provider: "Anthropic",
        model: "claude-3-opus-edge",
        displayName: "Claude 3 Opus Edge",
        requestCount: 163,
        tokenTotal: 611000,
        costUsd: 2.33,
        avgLatencyMs: 662,
        errorRate: 2.3,
      },
      {
        id: "mod_35",
        provider: "OpenAI",
        model: "gpt-4.1-long-context-pro",
        displayName: "GPT-4.1 Long Context Pro",
        requestCount: 178,
        tokenTotal: 710000,
        costUsd: 3.77,
        avgLatencyMs: 734,
        errorRate: 2.2,
      },
      {
        id: "mod_36",
        provider: "Gemini",
        model: "gemini-2.5-pro-long",
        displayName: "Gemini 2.5 Pro Long",
        requestCount: 191,
        tokenTotal: 822000,
        costUsd: 6.1,
        avgLatencyMs: 788,
        errorRate: 2.5,
      },
      {
        id: "mod_37",
        provider: "Anthropic",
        model: "claude-3.7-sonnet-reasoning",
        displayName: "Claude 3.7 Sonnet Reasoning",
        requestCount: 206,
        tokenTotal: 953000,
        costUsd: 9.87,
        avgLatencyMs: 846,
        errorRate: 2.4,
      },
      {
        id: "mod_38",
        provider: "OpenAI",
        model: "o3-mini-pro",
        displayName: "O3 Mini Pro",
        requestCount: 218,
        tokenTotal: 1084000,
        costUsd: 15.97,
        avgLatencyMs: 923,
        errorRate: 2.6,
      },
      {
        id: "mod_39",
        provider: "Gemini",
        model: "gemini-2.5-thinking-pro",
        displayName: "Gemini 2.5 Thinking Pro",
        requestCount: 235,
        tokenTotal: 1265000,
        costUsd: 25.84,
        avgLatencyMs: 1012,
        errorRate: 2.7,
      },
      {
        id: "mod_40",
        provider: "Anthropic",
        model: "claude-opus-research",
        displayName: "Claude Opus Research",
        requestCount: 247,
        tokenTotal: 1489000,
        costUsd: 41.79,
        avgLatencyMs: 1098,
        errorRate: 2.8,
      },
      {
        id: "mod_41",
        provider: "OpenAI",
        model: "gpt-4.1-research",
        displayName: "GPT-4.1 Research",
        requestCount: 263,
        tokenTotal: 1733000,
        costUsd: 67.63,
        avgLatencyMs: 1154,
        errorRate: 2.9,
      },
      {
        id: "mod_42",
        provider: "Gemini",
        model: "gemini-ultra-enterprise",
        displayName: "Gemini Ultra Enterprise",
        requestCount: 279,
        tokenTotal: 2054000,
        costUsd: 109.46,
        avgLatencyMs: 1221,
        errorRate: 3.1,
      },
      {
        id: "mod_43",
        provider: "Anthropic",
        model: "claude-sovereign-max",
        displayName: "Claude Sovereign Max",
        requestCount: 295,
        tokenTotal: 2410000,
        costUsd: 177.11,
        avgLatencyMs: 1310,
        errorRate: 3.2,
      },
      {
        id: "mod_44",
        provider: "OpenAI",
        model: "gpt-inference-cluster-a",
        displayName: "GPT-inference Cluster A",
        requestCount: 316,
        tokenTotal: 2815000,
        costUsd: 286.57,
        avgLatencyMs: 1388,
        errorRate: 3.3,
      },
      {
        id: "mod_45",
        provider: "Gemini",
        model: "gemini-vertex-enterprise",
        displayName: "Gemini Vertex Enterprise",
        requestCount: 332,
        tokenTotal: 3256000,
        costUsd: 463.68,
        avgLatencyMs: 1452,
        errorRate: 3.4,
      },
      {
        id: "mod_46",
        provider: "Anthropic",
        model: "claude-gov-secure",
        displayName: "Claude Gov Secure",
        requestCount: 348,
        tokenTotal: 3712000,
        costUsd: 750.25,
        avgLatencyMs: 1518,
        errorRate: 3.6,
      },
      {
        id: "mod_47",
        provider: "OpenAI",
        model: "gpt-compute-reserved",
        displayName: "GPT-compute Reserved",
        requestCount: 366,
        tokenTotal: 4278000,
        costUsd: 1213.49,
        avgLatencyMs: 1599,
        errorRate: 3.8,
      },
      {
        id: "mod_48",
        provider: "Gemini",
        model: "gemini-dedicated-tenant",
        displayName: "Gemini Dedicated Tenant",
        requestCount: 389,
        tokenTotal: 4983000,
        costUsd: 1964.05,
        avgLatencyMs: 1677,
        errorRate: 4,
      },
      {
        id: "mod_49",
        provider: "Anthropic",
        model: "claude-private-cluster",
        displayName: "Claude Private Cluster",
        requestCount: 411,
        tokenTotal: 5791000,
        costUsd: 3178.91,
        avgLatencyMs: 1732,
        errorRate: 4.1,
      },
      {
        id: "mod_50",
        provider: "OpenAI",
        model: "gpt-premium-ops",
        displayName: "GPT-premium Ops",
        requestCount: 436,
        tokenTotal: 6710000,
        costUsd: 5142.77,
        avgLatencyMs: 1794,
        errorRate: 4.2,
      },
      {
        id: "mod_51",
        provider: "Gemini",
        model: "gemini-hyperscale-plus",
        displayName: "Gemini Hyperscale Plus",
        requestCount: 462,
        tokenTotal: 7755000,
        costUsd: 8320.44,
        avgLatencyMs: 1862,
        errorRate: 4.4,
      },
      {
        id: "mod_52",
        provider: "Anthropic",
        model: "claude-internal-mega",
        displayName: "Claude Internal Mega",
        requestCount: 489,
        tokenTotal: 8944000,
        costUsd: 13462.18,
        avgLatencyMs: 1939,
        errorRate: 4.5,
      },
      {
        id: "mod_53",
        provider: "OpenAI",
        model: "gpt-enterprise-regional",
        displayName: "GPT-enterprise Regional",
        requestCount: 521,
        tokenTotal: 10283000,
        costUsd: 21767.51,
        avgLatencyMs: 2018,
        errorRate: 4.7,
      },
      {
        id: "mod_54",
        provider: "Gemini",
        model: "gemini-global-fleet",
        displayName: "Gemini Global Fleet",
        requestCount: 557,
        tokenTotal: 11874000,
        costUsd: 35201.22,
        avgLatencyMs: 2089,
        errorRate: 4.9,
      },
      {
        id: "mod_55",
        provider: "Anthropic",
        model: "claude-planetary-max",
        displayName: "Claude Planetary Max",
        requestCount: 594,
        tokenTotal: 13699000,
        costUsd: 56952.41,
        avgLatencyMs: 2165,
        errorRate: 5.1,
      },
      {
        id: "mod_56",
        provider: "OpenAI",
        model: "gpt-singularity-enterprise",
        displayName: "GPT-singularity Enterprise",
        requestCount: 631,
        tokenTotal: 15821000,
        costUsd: 100000,
        avgLatencyMs: 2244,
        errorRate: 5.4,
      },
    ],
  },
  providers: {
    cards: [
      {
        id: "prov_openai",
        displayName: "OpenAI",
        type: "openai_compatible",
        status: "operational",
        baseUrl: "https://api.openai.com/v1",
        requestsToday: 621,
        successRate: 98.3,
        errorRate: 1.7,
        avgLatencyMs: 762,
        availableModelCount: 24,
        lastCheckedAt: "2026-05-27T09:29:40-07:00",
        lastError: null,
      },
      {
        id: "prov_azure_openai",
        displayName: "Azure OpenAI",
        type: "openai_compatible",
        status: "operational",
        baseUrl: "https://modelport-azure.openai.azure.com/openai/v1",
        requestsToday: 167,
        successRate: 98.7,
        errorRate: 1.3,
        avgLatencyMs: 801,
        availableModelCount: 14,
        lastCheckedAt: "2026-05-27T09:29:40-07:00",
        lastError: null,
      },
      {
        id: "prov_anthropic",
        displayName: "Anthropic",
        type: "anthropic_compatible",
        status: "operational",
        baseUrl: "https://api.anthropic.com",
        requestsToday: 694,
        successRate: 98.8,
        errorRate: 1.2,
        avgLatencyMs: 807,
        availableModelCount: 11,
        lastCheckedAt: "2026-05-27T09:29:40-07:00",
        lastError: null,
      },
      {
        id: "prov_gemini",
        displayName: "Gemini",
        type: "openai_compatible",
        status: "degraded",
        baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai",
        requestsToday: 303,
        successRate: 96.9,
        errorRate: 3.1,
        avgLatencyMs: 938,
        availableModelCount: 12,
        lastCheckedAt: "2026-05-27T09:29:40-07:00",
        lastError: "Intermittent 429 rate limits in the last 10 minutes",
      },
      {
        id: "prov_groq",
        displayName: "Groq",
        type: "openai_compatible",
        status: "operational",
        baseUrl: "https://api.groq.com/openai/v1",
        requestsToday: 218,
        successRate: 98.6,
        errorRate: 1.4,
        avgLatencyMs: 412,
        availableModelCount: 17,
        lastCheckedAt: "2026-05-27T09:29:40-07:00",
        lastError: null,
      },
      {
        id: "prov_together",
        displayName: "Together AI",
        type: "openai_compatible",
        status: "operational",
        baseUrl: "https://api.together.xyz/v1",
        requestsToday: 141,
        successRate: 97.4,
        errorRate: 2.6,
        avgLatencyMs: 933,
        availableModelCount: 62,
        lastCheckedAt: "2026-05-27T09:29:40-07:00",
        lastError: null,
      },
      {
        id: "prov_mistral",
        displayName: "Mistral",
        type: "openai_compatible",
        status: "operational",
        baseUrl: "https://api.mistral.ai/v1",
        requestsToday: 88,
        successRate: 98.1,
        errorRate: 1.9,
        avgLatencyMs: 684,
        availableModelCount: 9,
        lastCheckedAt: "2026-05-27T09:29:40-07:00",
        lastError: null,
      },
      {
        id: "prov_deepseek",
        displayName: "DeepSeek",
        type: "openai_compatible",
        status: "degraded",
        baseUrl: "https://api.deepseek.com/v1",
        requestsToday: 73,
        successRate: 94.6,
        errorRate: 5.4,
        avgLatencyMs: 1268,
        availableModelCount: 6,
        lastCheckedAt: "2026-05-27T09:29:40-07:00",
        lastError: "Upstream gateway timeouts detected for deepseek-reasoner",
      },
      {
        id: "prov_cerebras",
        displayName: "Cerebras",
        type: "openai_compatible",
        status: "operational",
        baseUrl: "https://api.cerebras.ai/v1",
        requestsToday: 52,
        successRate: 99.1,
        errorRate: 0.9,
        avgLatencyMs: 358,
        availableModelCount: 4,
        lastCheckedAt: "2026-05-27T09:29:40-07:00",
        lastError: null,
      },
      {
        id: "prov_fireworks",
        displayName: "Fireworks",
        type: "openai_compatible",
        status: "degraded",
        baseUrl: "https://api.fireworks.ai/inference/v1",
        requestsToday: 64,
        successRate: 95.8,
        errorRate: 4.2,
        avgLatencyMs: 1044,
        availableModelCount: 26,
        lastCheckedAt: "2026-05-27T09:29:40-07:00",
        lastError: "Elevated p95 latency on image-capable model endpoints",
      },
      {
        id: "prov_openrouter",
        displayName: "OpenRouter",
        type: "openai_compatible",
        status: "operational",
        baseUrl: "https://openrouter.ai/api/v1",
        requestsToday: 155,
        successRate: 97.9,
        errorRate: 2.1,
        avgLatencyMs: 1114,
        availableModelCount: 300,
        lastCheckedAt: "2026-05-27T09:29:40-07:00",
        lastError: null,
      },
      {
        id: "prov_xai",
        displayName: "xAI",
        type: "openai_compatible",
        status: "degraded",
        baseUrl: "https://api.x.ai/v1",
        requestsToday: 39,
        successRate: 93.7,
        errorRate: 6.3,
        avgLatencyMs: 1579,
        availableModelCount: 3,
        lastCheckedAt: "2026-05-27T09:29:40-07:00",
        lastError: "Frequent 5xx errors on grok-beta during peak traffic",
      },
      {
        id: "prov_ollama",
        displayName: "Ollama",
        type: "local_openai_compatible",
        status: "degraded",
        baseUrl: "http://localhost:11434/v1",
        requestsToday: 96,
        successRate: 94.8,
        errorRate: 5.2,
        avgLatencyMs: 1496,
        availableModelCount: 12,
        lastCheckedAt: "2026-05-27T09:29:40-07:00",
        lastError: "Local GPU memory pressure observed on larger quantized models",
      },
      {
        id: "prov_vllm_local",
        displayName: "vLLM Local",
        type: "local_openai_compatible",
        status: "operational",
        baseUrl: "http://localhost:8001/v1",
        requestsToday: 37,
        successRate: 97.2,
        errorRate: 2.8,
        avgLatencyMs: 522,
        availableModelCount: 15,
        lastCheckedAt: "2026-05-27T09:29:40-07:00",
        lastError: null,
      },
      {
        id: "prov_lmstudio",
        displayName: "LM Studio",
        type: "local_openai_compatible",
        status: "offline",
        baseUrl: "http://localhost:1234/v1",
        requestsToday: 10,
        successRate: 40,
        errorRate: 60,
        avgLatencyMs: 0,
        availableModelCount: 0,
        lastCheckedAt: "2026-05-27T09:29:40-07:00",
        lastError: "Connection refused on health check",
      },
    ],
    routingRules: [
      {
        match: "*",
        primaryProvider: "openai",
        fallbackProviders: ["anthropic", "gemini", "openrouter"],
      },
      {
        match: "gpt-*",
        primaryProvider: "openai",
        fallbackProviders: ["azure_openai", "anthropic", "openrouter"],
      },
      {
        match: "o*-*",
        primaryProvider: "openai",
        fallbackProviders: ["anthropic", "deepseek", "openrouter"],
      },
      {
        match: "claude-*",
        primaryProvider: "anthropic",
        fallbackProviders: ["openrouter", "gemini"],
      },
      {
        match: "gemini-*",
        primaryProvider: "gemini",
        fallbackProviders: ["openai", "anthropic", "openrouter"],
      },
      {
        match: "grok-*",
        primaryProvider: "xai",
        fallbackProviders: ["openrouter", "openai"],
      },
      {
        match: "deepseek-*",
        primaryProvider: "deepseek",
        fallbackProviders: ["openrouter", "together", "openai"],
      },
      {
        match: "mistral-*",
        primaryProvider: "mistral",
        fallbackProviders: ["openrouter", "together"],
      },
      {
        match: "llama-*",
        primaryProvider: "groq",
        fallbackProviders: ["openrouter", "cerebras", "together"],
      },
      {
        match: "qwen-*",
        primaryProvider: "openrouter",
        fallbackProviders: ["together", "ollama", "vllm_local"],
      },
      {
        match: "coder-*",
        primaryProvider: "deepseek",
        fallbackProviders: ["anthropic", "openai", "openrouter"],
      },
      {
        match: "local-*",
        primaryProvider: "vllm_local",
        fallbackProviders: ["ollama", "openrouter", "lmstudio"],
      },
      {
        match: "embeddings-*",
        primaryProvider: "openai",
        fallbackProviders: ["azure_openai", "openrouter"],
      },
      {
        match: "vision-*",
        primaryProvider: "openai",
        fallbackProviders: ["gemini", "anthropic", "openrouter"],
      },
      {
        match: "audio-*",
        primaryProvider: "openai",
        fallbackProviders: ["groq", "openrouter"],
      },
      {
        match: "rerank-*",
        primaryProvider: "together",
        fallbackProviders: ["openrouter", "mistral"],
      },
      {
        match: "batch-*",
        primaryProvider: "openrouter",
        fallbackProviders: ["openai", "together"],
      },
      {
        match: "reasoning-*",
        primaryProvider: "openai",
        fallbackProviders: ["anthropic", "deepseek", "openrouter"],
      },
      {
        match: "emergency-fallback",
        primaryProvider: "openrouter",
        fallbackProviders: ["openai", "anthropic", "groq"],
      },
    ],
    details: providerDetails,
  },
  costs: {
    note: "Costs are estimated using configured pricing and may differ from final provider billing.",
    totals: {
      todayUsd: 8.62,
      weekUsd: 51.84,
      monthUsd: 218.37,
    },
    byProvider: [
      { label: "Anthropic", amountUsd: 3.96 },
      { label: "OpenAI", amountUsd: 2.67 },
      { label: "Gemini", amountUsd: 1.59 },
      { label: "OpenRouter", amountUsd: 0.4 },
      { label: "Ollama", amountUsd: 0 },
      { label: "LM Studio", amountUsd: 0 },
    ],
    byModel: [
      { label: "Claude 3.5 Sonnet", amountUsd: 3.92 },
      { label: "GPT-4.1", amountUsd: 2.33 },
      { label: "Gemini 2.5 Pro", amountUsd: 1.51 },
      { label: "Claude 3 Haiku", amountUsd: 0.63 },
      { label: "GPT-4o mini", amountUsd: 0.23 },
    ],
    dailyTrend: [
      { label: "May 21", amountUsd: 6.92 },
      { label: "May 22", amountUsd: 7.34 },
      { label: "May 23", amountUsd: 8.01 },
      { label: "May 24", amountUsd: 6.14 },
      { label: "May 25", amountUsd: 6.72 },
      { label: "May 26", amountUsd: 8.09 },
      { label: "May 27", amountUsd: 8.62 },
    ],
  },
  settings: {
    defaults: {
      inputFormat: "anthropic",
      provider: "openrouter",
    },
    apiKeys: [
      {
        provider: "OpenAI",
        envVar: "OPENAI_API_KEY",
        configured: true,
        keyHint: "sk-**********AB12",
      },
      {
        provider: "Anthropic",
        envVar: "ANTHROPIC_API_KEY",
        configured: true,
        keyHint: "sk-ant-********9XZ4",
      },
      {
        provider: "Gemini",
        envVar: "GEMINI_API_KEY",
        configured: true,
        keyHint: "AIza********PQ8",
      },
      {
        provider: "OpenRouter",
        envVar: "OPENROUTER_API_KEY",
        configured: false,
        keyHint: "Not configured",
      },
      {
        provider: "Groq",
        envVar: "GROQ_API_KEY",
        configured: false,
        keyHint: "Not configured",
      },
      {
        provider: "Together AI",
        envVar: "TOGETHER_API_KEY",
        configured: false,
        keyHint: "Not configured",
      },
    ],
    pricingTable: [
      {
        provider: "Anthropic",
        model: "claude-3-5-sonnet-latest",
        inputPer1kUsd: 0.003,
        outputPer1kUsd: 0.015,
      },
      {
        provider: "Anthropic",
        model: "claude-3-haiku-20240307",
        inputPer1kUsd: 0.00025,
        outputPer1kUsd: 0.00125,
      },
      {
        provider: "OpenAI",
        model: "gpt-4.1",
        inputPer1kUsd: 0.002,
        outputPer1kUsd: 0.008,
      },
      {
        provider: "OpenAI",
        model: "gpt-4o-mini",
        inputPer1kUsd: 0.00015,
        outputPer1kUsd: 0.0006,
      },
      {
        provider: "Gemini",
        model: "gemini-2.5-pro",
        inputPer1kUsd: 0.00175,
        outputPer1kUsd: 0.007,
      },
      {
        provider: "OpenRouter",
        model: "openrouter/auto",
        inputPer1kUsd: 0.001,
        outputPer1kUsd: 0.003,
      },
    ],
    logging: {
      level: "info",
      availableLevels: ["debug", "info", "warn", "error"],
    },
    retention: {
      requestLogsDays: 30,
      providerHealthDays: 14,
      metricGranularity: "5m",
    },
  },
};
