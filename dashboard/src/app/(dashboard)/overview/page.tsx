"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowDownIcon,
  ArrowUpIcon,
  ClockIcon,
  PokerChipIcon,
  CurrencyDollarIcon,
  LightningIcon,
  RobotIcon,
} from "@phosphor-icons/react";
import {
  type OverviewMetric,
  type RequestStatus,
  type UsagePoint,
} from "@/lib/dashboard-types";
import { ProviderIcon } from "@/components/brand/render-provider-icon";
import { InteractiveAreaChart } from "@/components/dashboard/interactive-area-chart";
import { fetchOverviewAnalytics } from "@/lib/analytics-api";
import { formatCost, formatInteger, formatTimestamp } from "@/lib/format";

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

function formatLargeTokenValue(tokens: number): string {
  if (tokens >= 1_000_000) {
    return `${(tokens / 1_000_000).toFixed(1)}M`;
  }

  if (tokens >= 1_000) {
    return `${Math.round(tokens / 1_000)}K`;
  }

  return tokens.toString();
}

function buildTotalTokenSeries(
  points: UsagePoint[],
  referenceDate: Date,
  stepMs: number,
) {
  const start = new Date(referenceDate.getTime() - stepMs * (points.length - 1));

  return points.map((point, index) => ({
    date: new Date(start.getTime() + stepMs * index).toISOString(),
    primary: point.tokens,
    secondary: 0,
  }));
}

export default function OverviewPage() {
  const [overview, setOverview] = useState<Awaited<
    ReturnType<typeof fetchOverviewAnalytics>
  > | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [referenceDate] = useState(() => new Date());

  useEffect(() => {
    let active = true;

    void (async () => {
      try {
        const nextOverview = await fetchOverviewAnalytics();
        if (!active) {
          return;
        }
        setOverview(nextOverview);
        setErrorMessage(null);
      } catch (error) {
        if (!active) {
          return;
        }
        setErrorMessage(
          error instanceof Error
            ? error.message
            : "Backend unreachable. Start the ModelPort proxy and refresh this page.",
        );
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  const tokenAreaChartDataByRange = useMemo(() => {
    if (!overview) {
      return null;
    }

    const dayMs = 24 * 60 * 60 * 1000;
    const hourMs = 60 * 60 * 1000;
    const minuteMs = 60 * 1000;

    return {
      "30d": buildTotalTokenSeries(overview.tokenUsage["30d"].points, referenceDate, dayMs),
      "7d": buildTotalTokenSeries(overview.tokenUsage["7d"].points, referenceDate, dayMs),
      "1d": buildTotalTokenSeries(overview.tokenUsage["24h"].points, referenceDate, hourMs),
      "6h": buildTotalTokenSeries(overview.tokenUsage["6h"].points, referenceDate, 15 * minuteMs),
      "1h": buildTotalTokenSeries(overview.tokenUsage["1h"].points, referenceDate, 5 * minuteMs),
    };
  }, [overview, referenceDate]);

  const topMetricProvider = useMemo(() => {
    if (!overview) {
      return undefined;
    }

    const topMetricModelName = overview.metrics.find(
      (metric) => metric.id === "top_model",
    )?.value;

    return (
      overview.topModels.find(
        (model) =>
          model.displayName === topMetricModelName ||
          model.model === topMetricModelName,
      )?.provider ?? overview.topModels[0]?.provider
    );
  }, [overview]);

  if (isLoading) {
    return <div className="text-sm text-text-secondary">Loading overview...</div>;
  }

  if (errorMessage || !overview || !tokenAreaChartDataByRange) {
    return (
      <div className="rounded-xl border border-accent-red/20 bg-accent-red-bg px-4 py-3 text-sm text-accent-red">
        {errorMessage ??
          "Backend unreachable. Start the ModelPort proxy and refresh this page."}
      </div>
    );
  }

  const tokenAreaChartData = tokenAreaChartDataByRange["30d"];

  return (
    <div className="space-y-6">
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
                    <ProviderIcon
                      provider={topMetricProvider ?? ""}
                      size={20}
                      fallback={<RobotIcon size={20} />}
                    />
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
          description="Showing total token usage for the selected date range"
          data={tokenAreaChartData}
          dataByRange={tokenAreaChartDataByRange}
          primaryLabel="Total tokens"
          defaultRange="30d"
          showSecondary={false}
        />

        <article className="card-surface p-5 xl:col-span-2">
          <div className="flex items-center justify-between">
            <h2 className="text-xl">Top models</h2>
            <Link
              href="/models"
              className="text-sm text-text-secondary hover:text-text-primary"
            >
              View all
            </Link>
          </div>

          <div className="mt-5 space-y-4">
            {overview.topModels.map((model) => (
              <div
                key={model.id}
                className="grid grid-cols-10 items-center gap-2"
              >
                <div className="flex col-span-5 items-center gap-2">
                  <span className="inline-flex h-5 w-5 items-center justify-center text-sm font-semibold text-text-primary">
                    <ProviderIcon provider={model.provider} size={20} />
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-base font-semibold text-text-primary">
                      {model.displayName ?? model.model}
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
          <Link
            href="/requests"
            className="text-sm text-text-secondary hover:text-text-primary"
          >
            View all requests
          </Link>
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
                <td className="px-5 py-3">{formatCost(request.costUsd, 4)}</td>
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
