"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import {
  CaretLeftIcon,
  CaretRightIcon,
  ClockIcon,
  CurrencyDollarIcon,
  GaugeIcon,
  ReceiptIcon,
} from "@phosphor-icons/react";
import {
  InteractiveAreaChart,
  type InteractiveAreaChartPoint,
} from "@/components/dashboard/interactive-area-chart";
import { ProviderIcon } from "@/components/brand/render-provider-icon";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  fetchCostsAnalytics,
  fetchRequestsAnalytics,
} from "@/lib/analytics-api";
import { type RequestRow } from "@/lib/dashboard-types";
import {
  buildPageButtons,
  formatCost,
  formatInteger,
  formatTimestamp,
} from "@/lib/format";

type CostBreakdownView = "provider" | "model";

interface CostBreakdownItem {
  id: string;
  label: string;
  amountUsd: number;
  provider?: string;
}

function getProviderDisplayName(provider: string): string {
  if (provider === "Gemini") {
    return "Google";
  }

  return provider;
}

function buildCostRangeSeries(
  rows: RequestRow[],
  hours: number,
  buckets: number,
  referenceDate: Date,
): InteractiveAreaChartPoint[] {
  const bucketMs = (hours * 60 * 60 * 1000) / buckets;
  const startTime = referenceDate.getTime() - bucketMs * (buckets - 1);

  return Array.from({ length: buckets }, (_, index) => {
    const bucketStart = startTime + bucketMs * index;
    const bucketEnd = bucketStart + bucketMs;
    const primary = rows.reduce((sum, row) => {
      const timestamp = new Date(row.timestamp).getTime();
      if (timestamp >= bucketStart && timestamp < bucketEnd) {
        return sum + row.costUsd;
      }
      return sum;
    }, 0);

    return {
      date: new Date(bucketStart).toISOString(),
      primary: Number(primary.toFixed(4)),
      secondary: 0,
    };
  });
}

function CostMetricCard({
  label,
  value,
  subtext,
  icon,
}: {
  label: string;
  value: string;
  subtext: string;
  icon: React.ComponentType<{ size?: string | number }>;
}) {
  const Icon = icon;

  return (
    <article className="card-surface p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col">
          <p className="text-sm font-medium text-text-secondary">{label}</p>
          <p className="mt-1 text-lg font-semibold text-text-primary">{value}</p>
        </div>
        <span className="card-surface-soft inline-flex h-10 w-10 items-center justify-center rounded-xl text-text-secondary">
          <Icon size={20} />
        </span>
      </div>
      <div className="mt-2 flex items-center gap-2 text-sm">
        <span className="text-text-muted">{subtext}</span>
      </div>
    </article>
  );
}

export default function CostsPage() {
  const [breakdownView, setBreakdownView] = useState<CostBreakdownView>("provider");
  const [currentPage, setCurrentPage] = useState(1);
  const [costsPayload, setCostsPayload] = useState<Awaited<ReturnType<typeof fetchCostsAnalytics>> | null>(null);
  const [requestRows, setRequestRows] = useState<RequestRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const rowsPerPage = 5;

  useEffect(() => {
    let active = true;

    void (async () => {
      try {
        const [nextCosts, nextRequests] = await Promise.all([
          fetchCostsAnalytics(),
          fetchRequestsAnalytics(),
        ]);
        if (!active) {
          return;
        }
        setCostsPayload(nextCosts);
        setRequestRows(nextRequests.rows);
        setErrorMessage(null);
      } catch {
        if (!active) {
          return;
        }
        setErrorMessage("Backend unreachable. Start the ModelPort proxy and refresh this page.");
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

  const chartDataByRange = useMemo(() => {
    const referenceDate = new Date();
    return {
      "1h": buildCostRangeSeries(requestRows, 1, 12, referenceDate),
      "6h": buildCostRangeSeries(requestRows, 6, 24, referenceDate),
      "1d": buildCostRangeSeries(requestRows, 24, 24, referenceDate),
      "7d": buildCostRangeSeries(requestRows, 24 * 7, 7, referenceDate),
      "30d": buildCostRangeSeries(requestRows, 24 * 30, 30, referenceDate),
    };
  }, [requestRows]);

  const highCostRows = useMemo(
    () => costsPayload?.recentHighCostRequests ?? [],
    [costsPayload],
  );

  const totalRows = highCostRows.length;
  const totalPages = Math.max(1, Math.ceil(totalRows / rowsPerPage));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const canGoPrevious = safeCurrentPage > 1;
  const canGoNext = safeCurrentPage < totalPages;

  const pageRows = useMemo(() => {
    const startIndex = (safeCurrentPage - 1) * rowsPerPage;
    return highCostRows.slice(startIndex, startIndex + rowsPerPage);
  }, [highCostRows, safeCurrentPage]);

  const pageButtons = useMemo(
    () => buildPageButtons(safeCurrentPage, totalPages),
    [safeCurrentPage, totalPages],
  );

  const breakdownItems: CostBreakdownItem[] =
    breakdownView === "provider"
      ? (costsPayload?.byProvider ?? []).map((item) => ({
          id: `provider_${item.label}`,
          label: item.label,
          amountUsd: item.amountUsd,
          provider: item.label,
        }))
      : (costsPayload?.byModel ?? []).map((item) => ({
          id: `model_${item.label}`,
          label: item.label,
          amountUsd: item.amountUsd,
        }));
  const breakdownTotal = breakdownItems.reduce((sum, item) => sum + item.amountUsd, 0);
  const averageCostPerRequest =
    requestRows.length > 0
      ? requestRows.reduce((sum, row) => sum + row.costUsd, 0) / requestRows.length
      : 0;

  if (isLoading) {
    return <div className="text-sm text-text-secondary">Loading cost analytics...</div>;
  }

  return (
    <div className="space-y-6">
      {errorMessage ? (
        <div className="rounded-xl border border-accent-red/20 bg-accent-red-bg px-4 py-3 text-sm text-accent-red">
          {errorMessage}
        </div>
      ) : null}
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <CostMetricCard
          label="Spend today"
          value={formatCost(costsPayload?.totals.todayUsd ?? 0)}
          subtext="Tracked since UTC midnight"
          icon={CurrencyDollarIcon}
        />
        <CostMetricCard
          label="Spend this week"
          value={formatCost(costsPayload?.totals.weekUsd ?? 0)}
          subtext="Last 7 days"
          icon={ClockIcon}
        />
        <CostMetricCard
          label="Spend this month"
          value={formatCost(costsPayload?.totals.monthUsd ?? 0)}
          subtext="Last 30 days"
          icon={GaugeIcon}
        />
        <CostMetricCard
          label="Average cost per request"
          value={formatCost(averageCostPerRequest, 4)}
          subtext="Across tracked requests"
          icon={ReceiptIcon}
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-5">
        <InteractiveAreaChart
          className="xl:col-span-3"
          title="Spending over time"
          description="Estimated cost trend"
          data={chartDataByRange["1d"]}
          dataByRange={chartDataByRange}
          showLegend={false}
          showSecondary={false}
          chartHeightClassName="h-64"
          showYAxis
          yAxisTickFormatter={(value) => `$${value}`}
          defaultRange="1d"
          tooltipIncludeTime
        />

        <article className="card-surface p-5 xl:col-span-2 flex flex-col justify-between">
          <header className="flex items-center justify-between gap-3">
            <h2 className="text-xl whitespace-nowrap">Cost breakdown by {breakdownView}</h2>
            <Select
              value={breakdownView}
              onValueChange={(value) => setBreakdownView(value as CostBreakdownView)}
            >
              <SelectTrigger className="w-40 rounded-lg bg-bg-card-muted text-sm text-text-primary">
                <SelectValue />
              </SelectTrigger>
              <SelectContent align="end" className="rounded-lg p-1">
                <SelectItem value="provider" className="rounded-md text-sm">
                  Provider
                </SelectItem>
                <SelectItem value="model" className="rounded-md text-sm">
                  Model
                </SelectItem>
              </SelectContent>
            </Select>
          </header>

          <div className="mt-5 space-y-4">
            {breakdownItems.map((item) => {
              const share = breakdownTotal === 0 ? 0 : (item.amountUsd / breakdownTotal) * 100;

              return (
                <div key={item.id} className="grid grid-cols-10 items-center gap-2">
                  <div className="col-span-5 flex min-w-0 items-center gap-2">
                    <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center text-text-primary">
                      <ProviderIcon provider={item.provider ?? item.label} size={20} />
                    </span>
                    <p className="truncate text-base font-semibold text-text-primary">
                      {item.label}
                    </p>
                  </div>
                  <div className="col-span-5 grid grid-cols-4 items-center gap-2">
                    <p className="col-span-1 text-right text-sm font-medium text-text-secondary">
                      {Math.round(share)}%
                    </p>
                    <div className="col-span-2 h-2 w-full rounded-full bg-bg-card-muted">
                      <div
                        className="h-full rounded-full bg-accent-slate"
                        style={{ width: `${share}%` }}
                      />
                    </div>
                    <p className="col-span-1 text-right text-sm text-text-secondary">
                      {formatCost(item.amountUsd)}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-3 border-t border-border-subtle pt-3">
            <div className="flex items-center justify-between">
              <p className="text-lg font-medium text-text-primary">Total</p>
              <p className="text-lg font-semibold text-text-primary">
                {formatCost(breakdownTotal)}
              </p>
            </div>
          </div>
        </article>
      </section>

      <section className="card-surface overflow-hidden">
        <header className="flex items-center justify-between border-b border-border-subtle px-5 py-4">
          <h2 className="text-xl">Recent high-cost requests</h2>
          <Link
            href="/requests"
            className="text-sm text-text-secondary hover:text-text-primary"
          >
            View all requests
          </Link>
        </header>

        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm tabular-nums">
            <thead>
              <tr className="bg-bg-card-muted text-xs text-text-secondary">
                <th className="px-5 py-3.5 font-medium whitespace-nowrap">Date</th>
                <th className="px-5 py-3.5 font-medium whitespace-nowrap">Provider</th>
                <th className="px-5 py-3.5 font-medium whitespace-nowrap">Model</th>
                <th className="px-5 py-3.5 font-medium whitespace-nowrap">Tokens</th>
                <th className="px-5 py-3.5 font-medium whitespace-nowrap">Cost</th>
              </tr>
            </thead>
            <tbody>
              {pageRows.map((row) => (
                <tr
                  key={row.id}
                  className="border-t border-border-subtle text-sm text-text-secondary"
                >
                  <td className="px-5 py-3.5 whitespace-nowrap">
                    {formatTimestamp(row.timestamp)}
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-3">
                      <span className="inline-flex h-6 w-6 items-center justify-center rounded-sm bg-bg-card-muted">
                        <ProviderIcon provider={row.provider} />
                      </span>
                      <span className="font-medium text-text-primary">
                        {getProviderDisplayName(row.provider)}
                      </span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5 text-text-primary">{row.model}</td>
                  <td className="px-5 py-3.5 text-text-primary">
                    {formatInteger(row.totalTokens)}
                  </td>
                  <td className="px-5 py-3.5 text-text-primary">{formatCost(row.costUsd, 4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <footer className="flex flex-col gap-3 border-t border-border-subtle px-5 py-3 text-sm text-text-secondary sm:flex-row sm:items-center sm:justify-between">
          <p>
            Showing {Math.min(rowsPerPage, totalRows)} of {formatInteger(totalRows)} results
          </p>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              aria-label="Previous page"
              onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
              disabled={!canGoPrevious}
              className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-border-subtle text-text-muted disabled:cursor-not-allowed disabled:opacity-50"
            >
              <CaretLeftIcon size={14} />
            </button>

            {pageButtons.map((page, index) => {
              const previousPage = pageButtons[index - 1];
              const showEllipsis = previousPage !== undefined && page - previousPage > 1;

              return (
                <div key={page} className="flex items-center gap-1.5">
                  {showEllipsis ? <span className="px-1 text-text-muted">...</span> : null}
                  <button
                    type="button"
                    onClick={() => setCurrentPage(page)}
                    className={
                      page === safeCurrentPage
                        ? "inline-flex h-7 min-w-7 items-center justify-center rounded-md border border-text-primary px-2 text-text-primary"
                        : "inline-flex h-7 min-w-7 items-center justify-center rounded-md border border-border-subtle px-2 text-text-secondary hover:text-text-primary"
                    }
                    aria-current={page === safeCurrentPage ? "page" : undefined}
                  >
                    {page}
                  </button>
                </div>
              );
            })}

            <button
              type="button"
              aria-label="Next page"
              onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
              disabled={!canGoNext}
              className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-border-subtle text-text-muted disabled:cursor-not-allowed disabled:opacity-50"
            >
              <CaretRightIcon size={14} />
            </button>
          </div>
        </footer>
      </section>
    </div>
  );
}
