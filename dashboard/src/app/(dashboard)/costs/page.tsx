"use client";

import { useMemo, useState } from "react";

import {
  ArrowDownIcon,
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
import { renderProviderIcon } from "@/components/brand/render-provider-icon";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { dashboardMockData, type RequestRow } from "@/lib/mock-dashboard-data";

type CostBreakdownView = "provider" | "model";

interface CostBreakdownItem {
  id: string;
  label: string;
  amountUsd: number;
  provider?: string;
}

const costBreakdownByProvider: CostBreakdownItem[] = [
  { id: "prov_anthropic", label: "Anthropic", amountUsd: 111.8, provider: "Anthropic" },
  { id: "prov_openai", label: "OpenAI", amountUsd: 77.06, provider: "OpenAI" },
  { id: "prov_google", label: "Google", amountUsd: 34.29, provider: "Google" },
  { id: "prov_meta", label: "Meta", amountUsd: 17.36, provider: "Meta" },
  { id: "prov_mistral", label: "Mistral AI", amountUsd: 7.85, provider: "Mistral AI" },
];

const costBreakdownByModel: CostBreakdownItem[] = [
  {
    id: "model_claude_35_sonnet",
    label: "Claude 3.5 Sonnet",
    amountUsd: 93.42,
    provider: "Anthropic",
  },
  {
    id: "model_gpt_41",
    label: "GPT-4.1",
    amountUsd: 71.15,
    provider: "OpenAI",
  },
  {
    id: "model_gemini_25_pro",
    label: "Gemini 2.5 Pro",
    amountUsd: 40.76,
    provider: "Google",
  },
  {
    id: "model_gpt_4o_mini",
    label: "GPT-4o mini",
    amountUsd: 24.54,
    provider: "OpenAI",
  },
  {
    id: "model_claude_3_haiku",
    label: "Claude 3 Haiku",
    amountUsd: 18.49,
    provider: "Anthropic",
  },
];

function formatCost(value: number, minimumFractionDigits = 2): string {
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits,
    maximumFractionDigits: minimumFractionDigits,
  });
}

function formatPercentage(value: number): string {
  return `${value.toFixed(1)}%`;
}

function formatLongTimestamp(value: string): string {
  return new Date(value).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatInteger(value: number): string {
  return value.toLocaleString("en-US");
}

function getProviderDisplayName(provider: string): string {
  if (provider === "Gemini") {
    return "Google";
  }

  return provider;
}

function buildCostSeries(values: number[], stepMs: number, endDate: Date): InteractiveAreaChartPoint[] {
  const startTime = endDate.getTime() - stepMs * (values.length - 1);

  return values.map((value, index) => ({
    date: new Date(startTime + stepMs * index).toISOString(),
    primary: value,
    secondary: 0,
  }));
}

function buildCostChartData(referenceDate: Date) {
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;

  const oneHour = buildCostSeries(
    [2.6, 2.9, 3.1, 3.4, 3.8, 4.2, 4.6, 5.1, 4.9, 4.5, 4.1, 3.7],
    5 * minute,
    referenceDate,
  );

  const sixHours = buildCostSeries(
    [
      4.2, 4.1, 4.3, 4.6, 4.8, 5.1, 5.4, 5.9, 6.3, 6.8, 7.2, 7.7, 8.1, 8.5, 8.2,
      7.9, 7.4, 6.9, 6.5, 6.1, 5.7, 5.4, 5.1, 4.8,
    ],
    15 * minute,
    referenceDate,
  );

  const oneDay = buildCostSeries(
    [
      4.8, 4.4, 4.0, 4.2, 5.0, 6.1, 7.5, 9.9, 10.4, 12.9, 11.3, 12.4, 14.5, 15.2,
      17.1, 16.2, 14.7, 12.1, 13.6, 12.2, 11.4, 10.1, 8.8, 7.4, 6.5, 5.1,
    ],
    hour,
    referenceDate,
  );

  const sevenDays = buildCostSeries([6.9, 7.3, 8.0, 6.1, 6.7, 8.1, 8.6], day, referenceDate);

  const thirtyDays = buildCostSeries(
    [
      5.6, 5.9, 5.8, 6.1, 6.3, 6.5, 6.8, 7.2, 7.1, 7.4, 7.8, 8.0, 8.2, 8.1, 8.4,
      8.7, 8.6, 8.9, 9.1, 9.0, 9.4, 9.6, 9.3, 9.7, 9.9, 10.1, 10.2, 10.4, 10.7,
      10.9,
    ],
    day,
    referenceDate,
  );

  return {
    "1h": oneHour,
    "6h": sixHours,
    "1d": oneDay,
    "7d": sevenDays,
    "30d": thirtyDays,
  };
}

function buildRecentHighCostRows(sourceRows: RequestRow[]): RequestRow[] {
  const baseRows = sourceRows.slice(0, 5);
  const referenceTime = new Date(baseRows[0]?.timestamp ?? dashboardMockData.generatedAt).getTime();

  return Array.from({ length: 25 }, (_, index) => {
    const baseRow = baseRows[index % baseRows.length];
    const sequence = Math.floor(index / baseRows.length);
    const tokenDecay = 1 - Math.min(0.28, sequence * 0.05);
    const costDecay = 1 - Math.min(0.2, sequence * 0.04);

    return {
      ...baseRow,
      id: `high_cost_${index + 1}`,
      timestamp: new Date(referenceTime - index * 44_000).toISOString(),
      totalTokens: Math.round(baseRow.totalTokens * tokenDecay),
      costUsd: Number((baseRow.costUsd * costDecay).toFixed(4)),
    };
  });
}

function buildPageButtons(currentPage: number, totalPages: number): number[] {
  const buttons = new Set<number>([1, totalPages, currentPage - 1, currentPage, currentPage + 1]);

  return Array.from(buttons)
    .filter((page) => page >= 1 && page <= totalPages)
    .sort((a, b) => a - b);
}

function CostMetricCard({
  label,
  value,
  changePercent,
  comparisonLabel,
  icon,
}: {
  label: string;
  value: string;
  changePercent: number;
  comparisonLabel: string;
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
        <span className="inline-flex items-center gap-1 text-accent-green">
          <ArrowDownIcon size={14} weight="bold" />
          {formatPercentage(changePercent)}
        </span>
        <span className="text-text-muted">{comparisonLabel}</span>
      </div>
    </article>
  );
}

export default function CostsPage() {
  const [breakdownView, setBreakdownView] = useState<CostBreakdownView>("provider");
  const [currentPage, setCurrentPage] = useState(1);

  const rowsPerPage = 5;

  const chartDataByRange = useMemo(
    () => buildCostChartData(new Date(dashboardMockData.generatedAt)),
    [],
  );

  const highCostRows = useMemo(
    () => buildRecentHighCostRows(dashboardMockData.requests.rows),
    [],
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

  const breakdownItems =
    breakdownView === "provider" ? costBreakdownByProvider : costBreakdownByModel;
  const breakdownTotal = breakdownItems.reduce((sum, item) => sum + item.amountUsd, 0);

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <CostMetricCard
          label="Spend today"
          value={formatCost(8.42)}
          changePercent={12.7}
          comparisonLabel="vs yesterday"
          icon={CurrencyDollarIcon}
        />
        <CostMetricCard
          label="Spend this week"
          value={formatCost(56.71)}
          changePercent={8.9}
          comparisonLabel="vs last week"
          icon={ClockIcon}
        />
        <CostMetricCard
          label="Projected monthly cost"
          value={formatCost(248.36)}
          changePercent={6.3}
          comparisonLabel="vs last month"
          icon={GaugeIcon}
        />
        <CostMetricCard
          label="Average cost per request"
          value={formatCost(0.0031, 4)}
          changePercent={7.4}
          comparisonLabel="vs yesterday"
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
                      {renderProviderIcon(item.provider ?? item.label, 20)}
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
          <button
            type="button"
            className="text-sm text-text-secondary hover:text-text-primary"
          >
            View all requests
          </button>
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
                    {formatLongTimestamp(row.timestamp)}
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-3">
                      <span className="inline-flex h-6 w-6 items-center justify-center rounded-sm bg-bg-card-muted">
                        {renderProviderIcon(row.provider)}
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
