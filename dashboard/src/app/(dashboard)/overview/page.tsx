import {
  ArrowDownIcon,
  ArrowUpIcon,
  ClockIcon,
  PokerChipIcon,
  CurrencyDollarIcon,
  LightningIcon,
  RobotIcon,
} from "@phosphor-icons/react/dist/ssr";
import { Anthropic, Gemini, OpenAI, Google } from "@lobehub/icons";
import {
  dashboardMockData,
  type OverviewMetric,
  type RequestStatus,
  type UsagePoint,
} from "@/lib/mock-dashboard-data";
import { InteractiveAreaChart } from "@/components/dashboard/interactive-area-chart";
import { PageHeader } from "@/components/dashboard/page-header";

type MetricIcon = typeof LightningIcon;

const metricIcons: Record<OverviewMetric["id"], MetricIcon> = {
  total_tokens: PokerChipIcon,
  estimated_cost: CurrencyDollarIcon,
  top_model: RobotIcon,
  average_latency: ClockIcon,
};

const statusStyles: Record<RequestStatus, string> = {
  success: "bg-accent-green-bg text-accent-green",
  error: "bg-accent-red-bg text-accent-red",
  cancelled: "bg-bg-card-muted text-text-muted",
};

function renderProviderIcon(
  provider: string | undefined,
  size: number,
  fallback: "robot" | "google" = "google",
) {
  if (provider === "Anthropic") {
    return <Anthropic size={size} />;
  }

  if (provider === "Gemini") {
    return <Gemini.Color size={size} />;
  }

  if (provider === "OpenAI") {
    return <OpenAI size={size} />;
  }

  return fallback === "robot" ? <RobotIcon size={size} /> : <Google size={size} />;
}

function formatLargeTokenValue(tokens: number): string {
  if (tokens >= 1_000_000) {
    return `${(tokens / 1_000_000).toFixed(1)}M`;
  }

  if (tokens >= 1_000) {
    return `${Math.round(tokens / 1_000)}K`;
  }

  return tokens.toString();
}

function formatInteger(value: number): string {
  return value.toLocaleString("en-US");
}

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatCost(value: number): string {
  return `$${value.toFixed(4)}`;
}

function buildSeriesFromPoints(
  points: UsagePoint[],
  referenceDate: Date,
  stepMs: number,
) {
  const start = new Date(referenceDate.getTime() - stepMs * (points.length - 1));

  return points.map((point, index) => {
    const date = new Date(start.getTime() + stepMs * index);
    const primary = Math.round(point.tokens * 0.62);
    const secondary = point.tokens - primary;
    const cacheRead = Math.round(point.tokens * 0.24);
    const cacheWrite = Math.round(point.tokens * 0.08);

    return {
      date: date.toISOString(),
      primary,
      secondary,
      cacheRead,
      cacheWrite,
    };
  });
}

const tokenAreaChartDataByRange = (() => {
  const usage = dashboardMockData.overview.tokenUsage;
  const referenceDate = new Date(dashboardMockData.generatedAt);
  const dayMs = 24 * 60 * 60 * 1000;
  const hourMs = 60 * 60 * 1000;
  const minuteMs = 60 * 1000;

  return {
    "30d": buildSeriesFromPoints(usage["30d"].points, referenceDate, dayMs),
    "7d": buildSeriesFromPoints(usage["7d"].points, referenceDate, dayMs),
    "1d": buildSeriesFromPoints(usage["24h"].points, referenceDate, hourMs),
    "6h": buildSeriesFromPoints(usage["6h"].points, referenceDate, 15 * minuteMs),
    "1h": buildSeriesFromPoints(usage["1h"].points, referenceDate, 5 * minuteMs),
  };
})();
const tokenAreaChartData = tokenAreaChartDataByRange["30d"];

export default function OverviewPage() {
  const { overview } = dashboardMockData;
  const topMetricModelName = overview.metrics.find(
    (metric) => metric.id === "top_model",
  )?.value;
  const topMetricProvider =
    overview.topModels.find((model) => model.model === topMetricModelName)?.provider ??
    overview.topModels[0]?.provider;

  return (
    <div className="space-y-6">
      <PageHeader title="Overview" description="Key metrics and usage overview" />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {overview.metrics.map((metric) => {
          const Icon = metricIcons[metric.id];
          const trendColor = metric.trend
            ? "text-accent-green"
            : "text-text-muted";
          const TrendIcon =
            metric.trend?.direction === "up" ? ArrowUpIcon : ArrowDownIcon;

          return (
            <article key={metric.id} className="card-surface p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="flex flex-col">
                  <p className="text-sm font-medium text-text-secondary">
                    {metric.label}
                  </p>
                  <p className="mt-1 text-lg font-semibold text-text-primary">
                    {metric.value}
                  </p>
                </div>
                <span className="card-surface-soft inline-flex h-10 w-10 items-center justify-center rounded-xl text-text-secondary">
                  {metric.id === "top_model" ? (
                    renderProviderIcon(topMetricProvider, 20, "robot")
                  ) : (
                    <Icon size={20} />
                  )}
                </span>
              </div>
              <div className="mt-2 flex items-center gap-2 text-sm">
                {metric.trend ? (
                  <>
                    <span className={`inline-flex items-center ${trendColor}`}>
                      <TrendIcon size={14} weight="bold" />
                      {metric.trend.percent}%
                    </span>
                    <span className="text-text-muted">
                      {metric.trend.comparisonLabel}
                    </span>
                  </>
                ) : (
                  <span className="text-text-muted">{metric.subtext}</span>
                )}
              </div>
            </article>
          );
        })}
      </section>

      <section className="grid gap-4 xl:grid-cols-5">
        <InteractiveAreaChart
          className="xl:col-span-3"
          title="Token usage over time"
          description="Showing token usage for the selected date range"
          data={tokenAreaChartData}
          dataByRange={tokenAreaChartDataByRange}
          primaryLabel="Input tokens"
          secondaryLabel="Output tokens"
          cacheReadLabel="Cache read"
          cacheWriteLabel="Cache write"
          defaultRange="30d"
        />

        <article className="card-surface p-5 xl:col-span-2">
          <div className="flex items-center justify-between">
            <h2 className="text-xl">Top models</h2>
            <button
              type="button"
              className="text-sm text-text-secondary hover:text-text-primary"
            >
              View all
            </button>
          </div>

          <div className="mt-5 space-y-4">
            {overview.topModels.map((model) => (
              <div
                key={model.id}
                className="grid grid-cols-10 items-center gap-2"
              >
                <div className="flex col-span-5 items-center gap-2">
                  <span className="inline-flex h-5 w-5 items-center justify-center text-sm font-semibold text-text-primary">
                    {renderProviderIcon(model.provider, 20)}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-base font-semibold text-text-primary">
                      {model.model}
                    </p>
                    <p className="text-sm text-text-secondary">
                      {model.provider}
                    </p>
                  </div>
                </div>
                <div className="grid grid-cols-4 col-span-5 items-center gap-2">
                  <p className="col-span-1 text-right text-sm font-medium text-text-secondary">
                    {model.percent}%
                  </p>
                  <div className="col-span-2 w-full h-2 rounded-full bg-bg-card-muted">
                    <div
                      className="h-full rounded-full bg-accent-slate"
                      style={{ width: `${model.percent}%` }}
                    />
                  </div>
                  <p className="col-span-1 text-right text-sm text-text-secondary">
                    {formatLargeTokenValue(model.tokenTotal)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="card-surface overflow-x-auto">
        <div className="flex items-center justify-between border-b border-border-subtle px-5 py-4">
          <h2 className="text-xl">Recent requests</h2>
          <button
            type="button"
            className="text-sm text-text-secondary hover:text-text-primary"
          >
            View all requests
          </button>
        </div>

        <table className="min-w-full border-collapse text-left">
          <thead>
            <tr className="bg-bg-card-muted text-sm text-text-secondary">
              <th className="px-5 py-3 font-medium">Time</th>
              <th className="px-5 py-3 font-medium">Client</th>
              <th className="px-5 py-3 font-medium">Provider</th>
              <th className="px-5 py-3 font-medium">Model</th>
              <th className="px-5 py-3 font-medium">Tokens</th>
              <th className="px-5 py-3 font-medium">Cost</th>
              <th className="px-5 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {overview.recentRequests.map((request) => (
              <tr
                key={request.id}
                className="border-t border-border-subtle text-sm text-text-secondary"
              >
                <td className="px-5 py-3">
                  {formatTimestamp(request.timestamp)}
                </td>
                <td className="px-5 py-3 font-medium text-text-primary">
                  {request.client}
                </td>
                <td className="px-5 py-3">{request.provider}</td>
                <td className="px-5 py-3">{request.model}</td>
                <td className="px-5 py-3">
                  {formatInteger(request.totalTokens)}
                </td>
                <td className="px-5 py-3">{formatCost(request.costUsd)}</td>
                <td className="px-5 py-3">
                  <span
                    className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${statusStyles[request.status]}`}
                  >
                    <span className="status-dot bg-current" />
                    {request.status.charAt(0).toUpperCase() +
                      request.status.slice(1)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
