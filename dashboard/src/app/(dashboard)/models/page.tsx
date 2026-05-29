"use client";

import { useMemo, useState } from "react";

import {
  ArrowDownIcon,
  ArrowUpIcon,
  CaretLeftIcon,
  CaretRightIcon,
  ClockIcon,
  CubeIcon,
  StackIcon,
  RobotIcon,
} from "@phosphor-icons/react";
import { Anthropic, Gemini, OpenAI } from "@lobehub/icons";

import { ModelDetailsModal } from "@/components/dashboard/models/model-details-modal";
import { dashboardMockData } from "@/lib/mock-dashboard-data";

interface ModelTableRow {
  id: string;
  displayName: string;
  provider: string;
  usageShare: number;
  contextWindow: string;
  usageBars: number[];
  modelId: string;
  requestCount: number;
  tokenTotal: number;
  costUsd: number;
  avgLatencyMs: number;
  errorRate: number;
}

function formatInteger(value: number): string {
  return value.toLocaleString("en-US");
}

function formatMillions(value: number): string {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`;
  }

  if (value >= 1_000) {
    return `${Math.round(value / 1_000)}K`;
  }

  return value.toString();
}

function formatCost(value: number): string {
  return `$${value.toFixed(2)}`;
}

function formatModelLabel(modelSlug: string): string {
  if (/^o\d+$/i.test(modelSlug)) {
    return modelSlug.toLowerCase();
  }

  const cleaned = modelSlug
    .replace(/-latest$/i, "")
    .replace(/-preview$/i, "")
    .replace(/-\d{8}$/i, "");
  const parts = cleaned.split("-").filter(Boolean);

  if (parts.length === 0) {
    return modelSlug;
  }

  const titleCase = (word: string) => word.charAt(0).toUpperCase() + word.slice(1);

  if (parts[0] === "gpt") {
    const base = parts[1] ? `GPT-${parts[1]}` : "GPT";
    return [base, ...parts.slice(2).map(titleCase)].join(" ");
  }

  if (parts[0] === "claude" || parts[0] === "gemini") {
    const brand = titleCase(parts[0]);
    let index = 1;
    let version = "";

    if (/^\d+$/.test(parts[index] ?? "") && /^\d+$/.test(parts[index + 1] ?? "")) {
      version = `${parts[index]}.${parts[index + 1]}`;
      index += 2;
    } else if (/^\d+$/.test(parts[index] ?? "")) {
      version = parts[index];
      index += 1;
    }

    return [brand, version, ...parts.slice(index).map(titleCase)]
      .filter(Boolean)
      .join(" ");
  }

  return parts.map(titleCase).join(" ");
}

function getContextWindow(model: string): string {
  if (model.includes("gpt-4.1") || model.includes("gemini-2.5") || model.includes("gemini-2.0")) {
    return "1M";
  }

  if (model.includes("gpt-3.5")) {
    return "16K";
  }

  if (model.includes("gpt-4o-mini")) {
    return "128K";
  }

  return "200K";
}

function buildUsageBars(seed: number): number[] {
  const bars: number[] = [];
  let state = (seed % 97) + 11;

  for (let index = 0; index < 20; index += 1) {
    state = (state * 17 + 31 + index * 7) % 89;
    bars.push((state % 9) + 1);
  }

  return bars;
}

function buildSparklinePoints(values: number[], width = 128, height = 24): string {
  if (values.length === 0) {
    return "";
  }

  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = Math.max(1, maxValue - minValue);
  const stepX = values.length > 1 ? width / (values.length - 1) : width;

  return values
    .map((value, index) => {
      const x = index * stepX;
      const y = height - ((value - minValue) / range) * (height - 2) - 1;
      return `${x},${y}`;
    })
    .join(" ");
}

function renderProviderIcon(provider: string) {
  if (provider === "Anthropic") {
    return <Anthropic size={20} />;
  }

  if (provider === "Gemini") {
    return <Gemini.Color size={20} />;
  }

  if (provider === "OpenAI") {
    return <OpenAI size={20} />;
  }

  return (
    <span className="text-xs font-semibold text-text-secondary">
      {provider.slice(0, 2).toUpperCase()}
    </span>
  );
}

export default function ModelsPage() {
  const rowsPerPage = 8;
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedModel, setSelectedModel] = useState<ModelTableRow | null>(null);

  const rawModels = dashboardMockData.models.models;
  const totalTokens = rawModels.reduce((sum, model) => sum + model.tokenTotal, 0);

  const modelRows: ModelTableRow[] = useMemo(() => {
    return [...rawModels]
      .sort((left, right) => right.tokenTotal - left.tokenTotal)
      .map((model) => ({
        id: model.id,
        displayName: model.displayName ?? formatModelLabel(model.model),
        provider: model.provider,
        usageShare: Math.max(1, Math.round((model.tokenTotal / totalTokens) * 100)),
        contextWindow: getContextWindow(model.model),
        usageBars: buildUsageBars(model.tokenTotal + model.requestCount),
        modelId: model.model,
        requestCount: model.requestCount,
        tokenTotal: model.tokenTotal,
        costUsd: model.costUsd,
        avgLatencyMs: model.avgLatencyMs,
        errorRate: model.errorRate,
      }));
  }, [rawModels, totalTokens]);

  const topModel = modelRows[0];
  const totalRows = modelRows.length;
  const totalPages = Math.max(1, Math.ceil(totalRows / rowsPerPage));

  const pagedRows = useMemo(() => {
    const startIndex = (currentPage - 1) * rowsPerPage;
    return modelRows.slice(startIndex, startIndex + rowsPerPage);
  }, [currentPage, modelRows]);

  const pageButtons = useMemo(() => {
    if (totalPages <= 7) {
      return Array.from({ length: totalPages }, (_, index) => index + 1);
    }

    const pages = new Set<number>([1, totalPages]);
    for (let page = currentPage - 1; page <= currentPage + 1; page += 1) {
      if (page > 1 && page < totalPages) {
        pages.add(page);
      }
    }

    if (currentPage <= 3) {
      pages.add(2);
      pages.add(3);
      pages.add(4);
    }

    if (currentPage >= totalPages - 2) {
      pages.add(totalPages - 1);
      pages.add(totalPages - 2);
      pages.add(totalPages - 3);
    }

    return [...pages].sort((left, right) => left - right);
  }, [currentPage, totalPages]);

  const startRow = totalRows === 0 ? 0 : (currentPage - 1) * rowsPerPage + 1;
  const endRow = Math.min(currentPage * rowsPerPage, totalRows);
  const canGoPrevious = currentPage > 1;
  const canGoNext = currentPage < totalPages;
  const emptyRowCount = Math.max(0, rowsPerPage - pagedRows.length);

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article className="card-surface p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="flex flex-col">
              <p className="text-sm font-medium text-text-secondary">Active models</p>
              <p className="mt-1 text-lg font-semibold text-text-primary">
                {modelRows.length}
              </p>
            </div>
            <span className="card-surface-soft inline-flex h-10 w-10 items-center justify-center rounded-xl text-text-secondary">
              <CubeIcon size={20} />
            </span>
          </div>
          <div className="mt-2 flex items-center gap-2 text-sm">
            <span className="inline-flex items-center gap-1 text-accent-green">
              <ArrowUpIcon size={14} weight="bold" />1
            </span>
            <span className="text-text-muted">vs last week</span>
          </div>
        </article>

        <article className="card-surface p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="flex flex-col">
              <p className="text-sm font-medium text-text-secondary">Total tokens this week</p>
              <p className="mt-1 text-lg font-semibold text-text-primary">
                {formatMillions(totalTokens)}
              </p>
            </div>
            <span className="card-surface-soft inline-flex h-10 w-10 items-center justify-center rounded-xl text-text-secondary">
              <StackIcon size={20} />
            </span>
          </div>
          <div className="mt-2 flex items-center gap-2 text-sm">
            <span className="inline-flex items-center gap-1 text-accent-green">
              <ArrowUpIcon size={14} weight="bold" />22.7%
            </span>
            <span className="text-text-muted">vs last week</span>
          </div>
        </article>

        <article className="card-surface p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="flex flex-col">
              <p className="text-sm font-medium text-text-secondary">Most used model</p>
              <p className="mt-1 truncate text-lg font-semibold text-text-primary">
                {topModel?.displayName}
              </p>
            </div>
            <span className="card-surface-soft inline-flex h-10 w-10 items-center justify-center rounded-xl text-text-secondary">
              {renderProviderIcon(topModel?.provider) ?? <RobotIcon size={20} />}
            </span>
          </div>
          <div className="mt-2 flex items-center gap-2 text-sm">
            <span className="text-text-muted">{topModel?.usageShare ?? 0}% of total tokens</span>
          </div>
        </article>

        <article className="card-surface p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="flex flex-col">
              <p className="text-sm font-medium text-text-secondary">Average latency</p>
              <p className="mt-1 text-lg font-semibold text-text-primary">
                {dashboardMockData.models.totals.avgLatencyMs} ms
              </p>
            </div>
            <span className="card-surface-soft inline-flex h-10 w-10 items-center justify-center rounded-xl text-text-secondary">
              <ClockIcon size={20} />
            </span>
          </div>
          <div className="mt-2 flex items-center gap-2 text-sm">
            <span className="inline-flex items-center gap-1 text-accent-green">
              <ArrowDownIcon size={14} weight="bold" />6.1%
            </span>
            <span className="text-text-muted">vs last week</span>
          </div>
        </article>
      </section>

      <section className="card-surface overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full table-fixed border-collapse text-left text-sm tabular-nums">
            <colgroup>
              <col style={{ width: "28%" }} />
              <col style={{ width: "13%" }} />
              <col style={{ width: "23%" }} />
              <col style={{ width: "9%" }} />
              <col style={{ width: "12%" }} />
              <col style={{ width: "15%" }} />
            </colgroup>
            <thead>
              <tr className="bg-bg-card-muted text-text-secondary">
                <th className="px-5 py-3 font-medium whitespace-nowrap">Model</th>
                <th className="px-5 py-3 font-medium whitespace-nowrap">Provider</th>
                <th className="px-5 py-3 font-medium whitespace-nowrap">Usage share</th>
                <th className="px-5 py-3 font-medium whitespace-nowrap">Cost</th>
                <th className="px-5 py-3 font-medium whitespace-nowrap">Context window</th>
                <th className="px-5 py-3 font-medium whitespace-nowrap">Usage (7D)</th>
              </tr>
            </thead>
            <tbody>
              {pagedRows.map((model) => (
                <tr
                  key={model.id}
                  onClick={() => setSelectedModel(model)}
                  className="border-t border-border-subtle text-text-secondary hover:bg-bg-card-muted cursor-pointer"
                >
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-3">
                      <span className="inline-flex h-6 w-6 items-center justify-center text-text-primary">
                        {renderProviderIcon(model.provider)}
                      </span>
                      <span className="max-w-48 truncate font-medium text-text-primary whitespace-nowrap">
                        {model.displayName}
                      </span>
                    </div>
                  </td>
                  <td className="px-5 py-3">{model.provider}</td>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-3">
                      <span className="w-9 text-sm text-text-primary">{model.usageShare}%</span>
                      <div className="h-1.5 w-32 rounded-full bg-bg-card-muted">
                        <div
                          className="h-full rounded-full bg-accent-slate"
                          style={{ width: `${model.usageShare}%` }}
                        />
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-3 text-text-primary">{formatCost(model.costUsd)}</td>
                  <td className="px-5 py-3 text-text-primary">{model.contextWindow}</td>
                  <td className="px-5 py-3">
                    <svg
                      viewBox="0 0 128 24"
                      className="h-6 w-32 text-accent-slate"
                      role="img"
                      aria-label={`${model.displayName} seven day usage trend`}
                    >
                      <polyline
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        points={buildSparklinePoints(model.usageBars)}
                      />
                    </svg>
                  </td>
                </tr>
              ))}
              {Array.from({ length: emptyRowCount }).map((_, index) => (
                <tr
                  key={`empty-row-${index}`}
                  className="border-t border-border-subtle"
                  aria-hidden="true"
                >
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-3 opacity-0">
                      <span className="inline-flex h-6 w-6 items-center justify-center" />
                      <span className="max-w-48 truncate font-medium whitespace-nowrap">
                        placeholder
                      </span>
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    <span className="opacity-0">placeholder</span>
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-3 opacity-0">
                      <span className="w-9 text-sm">00%</span>
                      <div className="h-1.5 w-32 rounded-full" />
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    <span className="opacity-0">$0.00</span>
                  </td>
                  <td className="px-5 py-3">
                    <span className="opacity-0">000K</span>
                  </td>
                  <td className="px-5 py-3">
                    <div className="h-6 w-32 opacity-0" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex flex-col gap-3 border-t border-border-subtle px-5 py-3 text-sm text-text-secondary sm:flex-row sm:items-center sm:justify-between">
          <p>
            Showing {formatInteger(startRow)} to {formatInteger(endRow)} of {formatInteger(totalRows)} models
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
                  {showEllipsis && <span className="px-1 text-text-muted">...</span>}
                  <button
                    type="button"
                    onClick={() => setCurrentPage(page)}
                    className={
                      page === currentPage
                        ? "inline-flex h-7 min-w-7 items-center justify-center rounded-md border border-text-primary px-2 text-text-primary"
                        : "inline-flex h-7 min-w-7 items-center justify-center rounded-md border border-border-subtle px-2"
                    }
                    aria-current={page === currentPage ? "page" : undefined}
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
        </div>
      </section>

      <ModelDetailsModal
        model={selectedModel}
        onClose={() => setSelectedModel(null)}
        renderProviderIcon={renderProviderIcon}
      />
    </div>
  );
}
