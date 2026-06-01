"use client";

import { useMemo, useState } from "react";

import {
  ArrowDownIcon,
  ArrowUpIcon,
  CaretLeftIcon,
  CaretRightIcon,
  ClockIcon,
  PlugsIcon,
  PulseIcon,
  ShieldCheckIcon,
} from "@phosphor-icons/react";
import { Anthropic, Gemini, OpenAI, OpenRouter, Ollama } from "@lobehub/icons";

import { ProviderDetailsModal } from "@/components/dashboard/providers/provider-details-modal";
import {
  dashboardMockData,
  type ProviderDetail,
  type ProviderHealth,
  type ProviderStatus,
} from "@/lib/mock-dashboard-data";

type TrendDirection = "up" | "down";

interface SummaryMetric {
  id: string;
  label: string;
  value: string;
  subtext: string;
  direction: TrendDirection;
  change: string;
  icon: typeof PlugsIcon;
}

const statusTextStyles: Record<ProviderStatus, string> = {
  operational: "text-accent-green",
  degraded: "text-accent-amber",
  offline: "text-accent-red",
};

const statusDotStyles: Record<ProviderStatus, string> = {
  operational: "bg-accent-green",
  degraded: "bg-accent-amber",
  offline: "bg-accent-red",
};

function formatProviderStatus(status: ProviderStatus): string {
  if (status === "operational") {
    return "Healthy";
  }

  if (status === "degraded") {
    return "Degraded";
  }

  return "Offline";
}

function formatProviderType(type: ProviderHealth["type"]): string {
  if (type === "anthropic_compatible") {
    return "Anthropic-compatible";
  }

  if (type === "local_openai_compatible") {
    return "Local OpenAI-compatible";
  }

  return "OpenAI-compatible";
}

function renderProviderIcon(name: string, size = 20) {
  const normalized = name.toLowerCase();

  if (normalized.includes("anthropic")) {
    return <Anthropic size={size} />;
  }

  if (normalized.includes("gemini")) {
    return <Gemini.Color size={size} />;
  }

  if (normalized.includes("openrouter")) {
    return <OpenRouter size={size} />;
  }

  if (normalized.includes("ollama")) {
    return <Ollama size={size} />;
  }

  if (normalized.includes("openai") || normalized.includes("azure")) {
    return <OpenAI size={size} />;
  }

  return (
    <span className="text-xs font-semibold text-text-secondary">
      {name.slice(0, 2).toUpperCase()}
    </span>
  );
}

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function buildPageButtons(currentPage: number, totalPages: number): number[] {
  const buttons = new Set<number>([1, totalPages, currentPage - 1, currentPage, currentPage + 1]);

  return Array.from(buttons)
    .filter((page) => page >= 1 && page <= totalPages)
    .sort((a, b) => a - b);
}

export default function ProvidersPage() {
  const providerRowsPerPage = 8;

  const [currentPage, setCurrentPage] = useState(1);
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(null);

  const providerCards = dashboardMockData.providers.cards;
  const providerDetails = dashboardMockData.providers.details;

  const providerDetailsById = useMemo(() => {
    const map = new Map<string, ProviderDetail>();

    for (const detail of providerDetails) {
      map.set(detail.providerId, detail);
    }

    return map;
  }, [providerDetails]);

  const operationalProviders = providerCards.filter(
    (provider) => provider.status === "operational",
  );
  const activeProviders = providerCards.filter(
    (provider) => provider.status !== "offline",
  );
  const avgLatencyProviders = providerCards.filter(
    (provider) => provider.avgLatencyMs > 0,
  );
  const nonOperationalProviders = providerCards.filter(
    (provider) => provider.status !== "operational",
  );

  const averageUptime =
    activeProviders.reduce((sum, provider) => sum + provider.successRate, 0) /
    Math.max(1, activeProviders.length);
  const averageLatency =
    avgLatencyProviders.reduce((sum, provider) => sum + provider.avgLatencyMs, 0) /
    Math.max(1, avgLatencyProviders.length);

  const summaryMetrics: SummaryMetric[] = [
    {
      id: "active",
      label: "Active providers",
      value: activeProviders.length.toString(),
      subtext: `of ${providerCards.length} total`,
      direction: "up",
      change: "0",
      icon: PlugsIcon,
    },
    {
      id: "uptime",
      label: "Average uptime",
      value: `${averageUptime.toFixed(1)}%`,
      subtext: "vs yesterday",
      direction: "up",
      change: `${(operationalProviders.length / Math.max(1, providerCards.length) * 0.03).toFixed(2)}%`,
      icon: PulseIcon,
    },
    {
      id: "failover",
      label: "Provider incidents",
      value: nonOperationalProviders.length.toString(),
      subtext: "degraded/offline providers",
      direction: "down",
      change: `${Math.max(1, providerCards.length - operationalProviders.length) * 5}%`,
      icon: ShieldCheckIcon,
    },
    {
      id: "latency",
      label: "Average response time",
      value: `${Math.round(averageLatency).toLocaleString("en-US")} ms`,
      subtext: "across active providers",
      direction: "down",
      change: `${(Math.max(1, providerCards.length - operationalProviders.length) * 1.2).toFixed(1)}%`,
      icon: ClockIcon,
    },
  ];

  const totalRows = providerCards.length;
  const totalPages = Math.max(1, Math.ceil(totalRows / providerRowsPerPage));
  const safeCurrentPage = Math.min(currentPage, totalPages);

  const pagedProviders = useMemo(() => {
    const startIndex = (safeCurrentPage - 1) * providerRowsPerPage;
    return providerCards.slice(startIndex, startIndex + providerRowsPerPage);
  }, [providerCards, safeCurrentPage]);

  const startRow = totalRows === 0 ? 0 : (safeCurrentPage - 1) * providerRowsPerPage + 1;
  const endRow = totalRows === 0 ? 0 : Math.min(safeCurrentPage * providerRowsPerPage, totalRows);
  const canGoPrevious = safeCurrentPage > 1;
  const canGoNext = safeCurrentPage < totalPages;

  const pageButtons = useMemo(
    () => buildPageButtons(safeCurrentPage, totalPages),
    [safeCurrentPage, totalPages],
  );

  const selectedProvider = useMemo(
    () =>
      selectedProviderId
        ? providerCards.find((provider) => provider.id === selectedProviderId) ?? null
        : null,
    [providerCards, selectedProviderId],
  );

  const selectedProviderDetail = useMemo(
    () => (selectedProvider ? providerDetailsById.get(selectedProvider.id) ?? null : null),
    [providerDetailsById, selectedProvider],
  );

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {summaryMetrics.map((metric) => {
          const Icon = metric.icon;
          const TrendIcon = metric.direction === "up" ? ArrowUpIcon : ArrowDownIcon;
          const trendColor = metric.change === "0" ? "text-text-muted" : "text-accent-green";

          return (
            <article key={metric.id} className="card-surface p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="flex flex-col">
                  <p className="text-sm font-medium text-text-secondary">{metric.label}</p>
                  <p className="mt-1 text-lg font-semibold text-text-primary">{metric.value}</p>
                </div>
                <span className="card-surface-soft inline-flex h-11 w-11 items-center justify-center rounded-xl text-text-secondary">
                  <Icon size={20} />
                </span>
              </div>
              <div className="mt-2 flex items-center gap-2 text-sm">
                {metric.change === "0" ? (
                  <span className="text-text-muted">{metric.subtext}</span>
                ) : (
                  <>
                    <span className={`inline-flex items-center gap-1 ${trendColor}`}>
                      <TrendIcon size={14} weight="bold" />
                      {metric.change}
                    </span>
                    <span className="text-text-muted">{metric.subtext}</span>
                  </>
                )}
              </div>
            </article>
          );
        })}
      </section>

      <section className="card-surface overflow-hidden">
        <header className="flex items-center justify-between border-b border-border-subtle px-5 py-4">
          <div>
            <h2>Providers</h2>
            <p className="text-sm text-text-secondary">Provider health and routing readiness</p>
          </div>
        </header>

        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="bg-bg-card-muted text-text-secondary">
                <th className="px-5 py-3 font-medium whitespace-nowrap">Provider</th>
                <th className="px-5 py-3 font-medium whitespace-nowrap">Type</th>
                <th className="px-5 py-3 font-medium whitespace-nowrap">Status</th>
                <th className="px-5 py-3 font-medium whitespace-nowrap">Models</th>
                <th className="px-5 py-3 font-medium whitespace-nowrap">Success</th>
                <th className="px-5 py-3 font-medium whitespace-nowrap">Avg latency</th>
                <th className="px-5 py-3 font-medium whitespace-nowrap">Requests today</th>
                <th className="px-5 py-3 font-medium whitespace-nowrap">Last check</th>
              </tr>
            </thead>
            <tbody>
              {pagedProviders.map((provider) => (
                <tr
                  key={provider.id}
                  onClick={() => setSelectedProviderId(provider.id)}
                  className="border-t border-border-subtle text-text-secondary cursor-pointer hover:bg-bg-card-muted"
                >
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <span className="inline-flex h-6 w-6 items-center justify-center text-text-primary">
                        {renderProviderIcon(provider.displayName)}
                      </span>
                      <span className="font-medium text-text-primary">{provider.displayName}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3 text-text-primary">{formatProviderType(provider.type)}</td>
                  <td className="px-5 py-3">
                    <span className={`inline-flex items-center gap-2 font-medium ${statusTextStyles[provider.status]}`}>
                      <span className={`status-dot ${statusDotStyles[provider.status]}`} />
                      {formatProviderStatus(provider.status)}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-text-primary">{provider.availableModelCount}</td>
                  <td className="px-5 py-3 text-text-primary">{provider.successRate.toFixed(1)}%</td>
                  <td className="px-5 py-3 text-text-primary">
                    {provider.avgLatencyMs > 0 ? `${provider.avgLatencyMs.toLocaleString("en-US")} ms` : "n/a"}
                  </td>
                  <td className="px-5 py-3 text-text-primary">{provider.requestsToday.toLocaleString("en-US")}</td>
                  <td className="px-5 py-3 text-text-primary">{formatTimestamp(provider.lastCheckedAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <footer className="flex flex-col gap-3 border-t border-border-subtle px-5 py-3 text-sm text-text-secondary sm:flex-row sm:items-center sm:justify-between">
          <p>
            Showing {startRow} to {endRow} of {totalRows} providers
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setCurrentPage(Math.max(1, safeCurrentPage - 1))}
              className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-border-subtle text-text-muted disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!canGoPrevious}
              aria-label="Previous page"
            >
              <CaretLeftIcon size={14} />
            </button>

            {pageButtons.map((page, index) => {
              const previousPage = pageButtons[index - 1];
              const showEllipsis = previousPage !== undefined && page - previousPage > 1;

              return (
                <div key={page} className="flex items-center gap-2">
                  {showEllipsis && <span className="px-1 text-text-muted">...</span>}
                  <button
                    type="button"
                    onClick={() => setCurrentPage(page)}
                    className={
                      page === safeCurrentPage
                        ? "inline-flex h-7 min-w-7 items-center justify-center rounded-md border border-text-primary px-2 text-text-primary"
                        : "inline-flex h-7 min-w-7 items-center justify-center rounded-md border border-border-subtle px-2"
                    }
                    aria-label={`Go to page ${page}`}
                  >
                    {page}
                  </button>
                </div>
              );
            })}

            <button
              type="button"
              onClick={() => setCurrentPage(Math.min(totalPages, safeCurrentPage + 1))}
              className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-border-subtle text-text-muted disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!canGoNext}
              aria-label="Next page"
            >
              <CaretRightIcon size={14} />
            </button>
          </div>
        </footer>
      </section>

      <ProviderDetailsModal
        provider={selectedProvider}
        detail={selectedProviderDetail}
        onClose={() => setSelectedProviderId(null)}
        renderProviderIcon={renderProviderIcon}
      />
    </div>
  );
}
