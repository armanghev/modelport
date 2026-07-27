"use client";

import { useEffect, useMemo } from "react";

import { XIcon } from "@phosphor-icons/react";

import { ProviderIcon } from "@/components/brand/render-provider-icon";
import {
  InteractiveAreaChart,
  type InteractiveAreaChartPoint,
} from "@/components/dashboard/interactive-area-chart";
import { formatCost, formatInteger } from "@/lib/format";
import {
  type ProviderDetail,
  type ProviderHealth,
  type ProviderStatus,
} from "@/lib/dashboard-types";
import { formatProviderStatus } from "@/lib/provider-status";

interface ProviderDetailsModalProps {
  provider: ProviderHealth | null;
  detail: ProviderDetail | null;
  onClose: () => void;
}

const statusStyles: Record<ProviderStatus, string> = {
  operational: "text-accent-green",
  degraded: "text-accent-amber",
  offline: "text-accent-red",
};

const statusDotStyles: Record<ProviderStatus, string> = {
  operational: "bg-accent-green",
  degraded: "bg-accent-amber",
  offline: "bg-accent-red",
};

function toRangeData(points: InteractiveAreaChartPoint[], count: number) {
  return points.slice(Math.max(0, points.length - count));
}

function formatAxisTick(value: number): string {
  if (value >= 1000) {
    return `${Math.round(value / 100) / 10}K`;
  }

  return value.toString();
}

export function ProviderDetailsModal({
  provider,
  detail,
  onClose,
}: ProviderDetailsModalProps) {
  useEffect(() => {
    if (!provider) {
      return;
    }

    const previousBodyOverflow = document.body.style.overflow;
    const previousHtmlOverflow = document.documentElement.style.overflow;

    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousBodyOverflow;
      document.documentElement.style.overflow = previousHtmlOverflow;
    };
  }, [provider]);

  useEffect(() => {
    if (!provider) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [provider, onClose]);

  const chartData: InteractiveAreaChartPoint[] = useMemo(() => {
    if (!detail?.requestTrend.length) {
      return [];
    }

    return detail.requestTrend.map((point) => ({
      date: point.date,
      primary: point.requests,
      secondary: point.successfulRequests,
    }));
  }, [detail]);

  const chartDataByRange = useMemo(() => {
    if (chartData.length === 0) {
      return undefined;
    }

    return {
      "30d": toRangeData(chartData, 30),
      "7d": toRangeData(chartData, 7),
      "1d": toRangeData(chartData, 2),
      "6h": toRangeData(chartData, 2),
      "1h": toRangeData(chartData, 1),
    } as const;
  }, [chartData]);

  if (!provider) {
    return null;
  }

  const totalBreakdownCost =
    detail?.costBreakdown.reduce((sum, item) => sum + item.amountUsd, 0) ?? 0;

  return (
    <div
      className="fixed inset-0 z-50 overflow-hidden overscroll-none bg-black/35 p-4 backdrop-blur-sm"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="card-surface mx-auto my-4 max-h-[90vh] w-full max-w-6xl overflow-y-auto p-5 sm:my-6 sm:p-6"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`${provider.displayName} details`}
      >
        <div className="flex items-start justify-between gap-4 border-b border-border-subtle pb-4">
          <div className="min-w-0 space-y-2">
            <p className="text-sm text-text-secondary">Provider details</p>
            <h2 className="truncate text-2xl leading-tight">{provider.displayName}</h2>
            <div className="flex flex-wrap items-center gap-2 text-sm text-text-secondary">
              <span className="inline-flex items-center gap-2 rounded-md border border-border-subtle bg-bg-card-muted px-2.5 py-1 text-xs font-medium text-text-primary">
                <span className="inline-flex h-4 w-4 items-center justify-center text-text-primary">
                  <ProviderIcon provider={provider.displayName} size={16} />
                </span>
                {provider.baseUrl}
              </span>
              <span className={`inline-flex items-center gap-2 font-medium ${statusStyles[provider.status]}`}>
                <span className={`status-dot ${statusDotStyles[provider.status]}`} />
                {formatProviderStatus(provider.status)}
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border-subtle text-text-muted hover:bg-bg-card-muted hover:text-text-primary"
            aria-label="Close provider details"
          >
            <XIcon size={16} />
          </button>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2">
          <article className="card-surface-soft p-4">
            <p className="text-xs text-text-secondary">Requests today</p>
            <p className="mt-1 text-sm font-semibold text-text-primary">
              {formatInteger(provider.requestsToday)}
            </p>
          </article>
          <article className="card-surface-soft p-4">
            <p className="text-xs text-text-secondary">Success rate</p>
            <p className="mt-1 text-sm font-semibold text-text-primary">
              {provider.successRate.toFixed(1)}%
            </p>
          </article>
        </div>

        <div className="mt-4">
          <article className="card-surface-soft p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs text-text-secondary">Request trend</p>
              <p className="text-xs text-text-muted">
                Primary: total requests · Secondary: successful requests
              </p>
            </div>
            {chartData.length > 0 ? (
              <InteractiveAreaChart
                className="mt-2"
                data={chartData}
                dataByRange={chartDataByRange}
                title="Request trend"
                description="Provider request volume over billing cycle"
                primaryLabel="Requests"
                secondaryLabel="Successful"
                defaultRange="30d"
                showHeader={false}
                showLegend={true}
                showYAxis
                showVerticalGrid
                chartHeightClassName="h-64"
                yAxisTickFormatter={formatAxisTick}
                tooltipIncludeTime
                surface={false}
              />
            ) : (
              <p className="mt-4 text-sm text-text-muted">
                Request trend data is not available for this provider.
              </p>
            )}
          </article>
        </div>

        <article className="card-surface-soft mt-4 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-text-primary">Estimated cost breakdown</p>
            {detail?.costBreakdown.length ? (
              <p className="text-sm text-text-muted">{formatCost(totalBreakdownCost)}</p>
            ) : null}
          </div>
          {detail?.costBreakdown.length ? (
            <div className="mt-3 space-y-3">
              {detail.costBreakdown.map((item) => {
                const pct =
                  totalBreakdownCost > 0
                    ? (item.amountUsd / totalBreakdownCost) * 100
                    : 0;

                return (
                  <div key={item.label}>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-text-secondary">{item.label}</span>
                      <span className="font-medium text-text-primary">
                        {formatCost(item.amountUsd)}
                      </span>
                    </div>
                    <div className="mt-1 h-1.5 rounded-full bg-bg-card-muted">
                      <div
                        className="h-full rounded-full bg-accent-slate"
                        style={{ width: `${Math.max(4, pct)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="mt-3 text-sm text-text-muted">
              Cost breakdown is not available for this provider.
            </p>
          )}
        </article>
      </div>
    </div>
  );
}
