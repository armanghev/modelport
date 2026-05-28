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
  client: "Claude Code" | "OpenAI SDK" | "Gemini CLI" | "Custom App" | "Codex";
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
  alias: string;
  provider: string;
  model: string;
  requestCount: number;
  tokenTotal: number;
  costUsd: number;
  avgLatencyMs: number;
  errorRate: number;
}

export interface AliasMapping {
  alias: string;
  provider: string;
  model: string;
  description: string;
}

export interface ProviderHealth {
  id: string;
  displayName: string;
  type: ProviderType;
  status: ProviderStatus;
  baseUrl: string;
  defaultModel: string;
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
    aliases: AliasMapping[];
  };
  providers: {
    cards: ProviderHealth[];
    routingRules: RoutingRule[];
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
      modelAlias: string;
    };
    modelAliases: AliasMapping[];
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
        alias: "claude-sonnet",
        provider: "Anthropic",
        model: "claude-3-5-sonnet-latest",
        requestCount: 611,
        tokenTotal: 10600000,
        costUsd: 3.92,
        avgLatencyMs: 808,
        errorRate: 1.2,
      },
      {
        id: "mod_02",
        alias: "gpt",
        provider: "OpenAI",
        model: "gpt-4.1",
        requestCount: 418,
        tokenTotal: 6900000,
        costUsd: 2.33,
        avgLatencyMs: 764,
        errorRate: 1.6,
      },
      {
        id: "mod_03",
        alias: "gemini",
        provider: "Gemini",
        model: "gemini-2.5-pro",
        requestCount: 276,
        tokenTotal: 4200000,
        costUsd: 1.51,
        avgLatencyMs: 935,
        errorRate: 2.4,
      },
      {
        id: "mod_04",
        alias: "claude-haiku",
        provider: "Anthropic",
        model: "claude-3-haiku-20240307",
        requestCount: 313,
        tokenTotal: 1700000,
        costUsd: 0.63,
        avgLatencyMs: 551,
        errorRate: 1.8,
      },
      {
        id: "mod_05",
        alias: "fast",
        provider: "OpenAI",
        model: "gpt-4o-mini",
        requestCount: 229,
        tokenTotal: 1300000,
        costUsd: 0.23,
        avgLatencyMs: 522,
        errorRate: 2.1,
      },
    ],
    aliases: [
      {
        alias: "claude-sonnet",
        provider: "anthropic",
        model: "claude-3-5-sonnet-latest",
        description: "Default high-intelligence Claude model",
      },
      {
        alias: "gpt",
        provider: "openai",
        model: "gpt-4.1",
        description: "Default GPT model",
      },
      {
        alias: "gemini",
        provider: "gemini",
        model: "gemini-2.5-pro",
        description: "Default Gemini reasoning model",
      },
      {
        alias: "fast",
        provider: "openai",
        model: "gpt-4o-mini",
        description: "Low-latency, cost-efficient model",
      },
      {
        alias: "local",
        provider: "ollama",
        model: "qwen2.5-coder",
        description: "Local coding model through Ollama",
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
        defaultModel: "gpt-4.1",
        requestsToday: 621,
        successRate: 98.3,
        errorRate: 1.7,
        avgLatencyMs: 762,
        availableModelCount: 24,
        lastCheckedAt: "2026-05-27T09:29:40-07:00",
        lastError: null,
      },
      {
        id: "prov_anthropic",
        displayName: "Anthropic",
        type: "anthropic_compatible",
        status: "operational",
        baseUrl: "https://api.anthropic.com",
        defaultModel: "claude-3-5-sonnet-latest",
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
        defaultModel: "gemini-2.5-pro",
        requestsToday: 303,
        successRate: 96.9,
        errorRate: 3.1,
        avgLatencyMs: 938,
        availableModelCount: 12,
        lastCheckedAt: "2026-05-27T09:29:40-07:00",
        lastError: "Intermittent 429 rate limits in the last 10 minutes",
      },
      {
        id: "prov_openrouter",
        displayName: "OpenRouter",
        type: "openai_compatible",
        status: "operational",
        baseUrl: "https://openrouter.ai/api/v1",
        defaultModel: "openrouter/auto",
        requestsToday: 155,
        successRate: 97.9,
        errorRate: 2.1,
        avgLatencyMs: 1114,
        availableModelCount: 300,
        lastCheckedAt: "2026-05-27T09:29:40-07:00",
        lastError: null,
      },
      {
        id: "prov_ollama",
        displayName: "Ollama",
        type: "local_openai_compatible",
        status: "operational",
        baseUrl: "http://localhost:11434/v1",
        defaultModel: "qwen2.5-coder",
        requestsToday: 64,
        successRate: 95.4,
        errorRate: 4.6,
        avgLatencyMs: 1468,
        availableModelCount: 9,
        lastCheckedAt: "2026-05-27T09:29:40-07:00",
        lastError: null,
      },
      {
        id: "prov_lmstudio",
        displayName: "LM Studio",
        type: "local_openai_compatible",
        status: "offline",
        baseUrl: "http://localhost:1234/v1",
        defaultModel: "local-default",
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
        match: "claude-*",
        primaryProvider: "anthropic",
        fallbackProviders: ["openrouter", "gemini"],
      },
      {
        match: "gemini-*",
        primaryProvider: "gemini",
        fallbackProviders: ["openrouter"],
      },
      {
        match: "local-*",
        primaryProvider: "ollama",
        fallbackProviders: ["openrouter"],
      },
    ],
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
      modelAlias: "claude-sonnet",
    },
    modelAliases: [
      {
        alias: "claude-sonnet",
        provider: "anthropic",
        model: "claude-3-5-sonnet-latest",
        description: "Default high-intelligence Claude model",
      },
      {
        alias: "gpt",
        provider: "openai",
        model: "gpt-4.1",
        description: "Default GPT model",
      },
      {
        alias: "gemini",
        provider: "gemini",
        model: "gemini-2.5-pro",
        description: "Default Gemini reasoning model",
      },
      {
        alias: "fast",
        provider: "openai",
        model: "gpt-4o-mini",
        description: "Low-latency, cost-efficient model",
      },
      {
        alias: "local",
        provider: "ollama",
        model: "qwen2.5-coder",
        description: "Local coding model through Ollama",
      },
    ],
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
