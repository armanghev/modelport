"use client";

import { useEffect, useMemo, useState } from "react";

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
import { ProviderDetailsModal } from "@/components/dashboard/providers/provider-details-modal";
import { renderProviderIcon } from "@/components/brand/render-provider-icon";
import { Button } from "@/components/ui/button";
import { fetchProviderHealth } from "@/lib/admin-api";
import {
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
  const [providerCards, setProviderCards] = useState<ProviderHealth[]>([]);
  const [providerDetails, setProviderDetails] = useState<ProviderDetail[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    void (async () => {
      try {
        const payload = await fetchProviderHealth();
        if (!active) {
          return;
        }
        setProviderCards(payload.cards);
        setProviderDetails(payload.details);
        setErrorMessage(null);
      } catch (error) {
        if (!active) {
          return;
        }
        setErrorMessage(
          error instanceof Error ? error.message : "Failed to load provider health analytics.",
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
      subtext: "latest health checks",
      direction: "up",
      change: `${(operationalProviders.length / Math.max(1, providerCards.length) * 100).toFixed(0)}% healthy`,
      icon: PulseIcon,
    },
    {
      id: "failover",
      label: "Provider incidents",
      value: nonOperationalProviders.length.toString(),
      subtext: "degraded/offline providers",
      direction: "down",
      change: `${Math.max(0, nonOperationalProviders.length)} active alerts`,
      icon: ShieldCheckIcon,
    },
    {
      id: "latency",
      label: "Average response time",
      value: `${Math.round(averageLatency).toLocaleString("en-US")} ms`,
      subtext: "across active providers",
      direction: "down",
      change: `${avgLatencyProviders.length} sampled`,
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
        ? providerCards.find((provider) => provider.slug === selectedProviderId) ?? null
        : null,
    [providerCards, selectedProviderId],
  );

  const selectedProviderDetail = useMemo(
    () => (selectedProvider ? providerDetailsById.get(selectedProvider.slug) ?? null : null),
    [providerDetailsById, selectedProvider],
  );

  if (isLoading) {
    return <div className="text-sm text-text-secondary">Loading provider health analytics...</div>;
  }

  return (
    <div className="space-y-6">
      {errorMessage ? (
        <div className="rounded-xl border border-accent-red/20 bg-accent-red-bg px-4 py-3 text-sm text-accent-red">
          {errorMessage}
        </div>
      ) : null}
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
                  key={provider.slug}
                  className="cursor-pointer border-t border-border-subtle text-text-secondary transition-colors hover:bg-bg-card-muted/60"
                  onClick={() => setSelectedProviderId(provider.slug)}
                >
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-3">
                      <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-bg-card-muted text-text-primary">
                        {renderProviderIcon(provider.displayName, 18)}
                      </span>
                      <div className="min-w-0">
                        <p className="truncate font-medium text-text-primary">{provider.displayName}</p>
                        <p className="truncate text-xs text-text-muted">{provider.baseUrl}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-3">{formatProviderType(provider.type)}</td>
                  <td className="px-5 py-3">
                    <span className={`inline-flex items-center gap-2 font-medium ${statusTextStyles[provider.status]}`}>
                      <span className={`status-dot ${statusDotStyles[provider.status]}`} />
                      {formatProviderStatus(provider.status)}
                    </span>
                  </td>
                  <td className="px-5 py-3">{provider.availableModelCount}</td>
                  <td className="px-5 py-3">{provider.successRate.toFixed(1)}%</td>
                  <td className="px-5 py-3">{provider.avgLatencyMs.toLocaleString("en-US")} ms</td>
                  <td className="px-5 py-3">{provider.requestsToday.toLocaleString("en-US")}</td>
                  <td className="px-5 py-3">{formatTimestamp(provider.lastCheckedAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <footer className="flex flex-col gap-4 border-t border-border-subtle px-5 py-4 text-sm text-text-secondary md:flex-row md:items-center md:justify-between">
          <p>
            Showing {startRow}-{endRow} of {totalRows} providers
          </p>
          <div className="flex items-center gap-2 self-end md:self-auto">
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              className="h-9 w-9 rounded-lg border-border-default"
              onClick={() => canGoPrevious && setCurrentPage((page) => page - 1)}
              disabled={!canGoPrevious}
            >
              <CaretLeftIcon size={16} />
            </Button>
            <div className="flex items-center gap-2">
              {pageButtons.map((page) => (
                <Button
                  key={page}
                  type="button"
                  variant={page === safeCurrentPage ? "default" : "outline"}
                  size="sm"
                  className="h-9 min-w-9 rounded-lg px-3"
                  onClick={() => setCurrentPage(page)}
                >
                  {page}
                </Button>
              ))}
            </div>
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              className="h-9 w-9 rounded-lg border-border-default"
              onClick={() => canGoNext && setCurrentPage((page) => page + 1)}
              disabled={!canGoNext}
            >
              <CaretRightIcon size={16} />
            </Button>
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
