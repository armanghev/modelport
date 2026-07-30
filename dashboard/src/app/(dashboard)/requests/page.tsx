"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  CaretDownIcon,
  CaretLeftIcon,
  CaretRightIcon,
  CaretUpIcon,
  MagnifyingGlassIcon,
} from "@phosphor-icons/react";
import { ClaudeCode, GeminiCLI, Codex, Cursor, OpenAI } from "@lobehub/icons";

import { ProviderIcon } from "@/components/brand/render-provider-icon";
import { RequestDetailSheet } from "@/components/dashboard/requests/request-detail-sheet";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { fetchRequestDetail, fetchRequestsAnalytics } from "@/lib/analytics-api";
import { fetchAdminSettings, patchTrackingSettings } from "@/lib/admin-api";
import { type RequestRow, type RequestStatus } from "@/lib/dashboard-types";
import {
  formatCost,
  formatInteger,
  formatTimestamp,
} from "@/lib/format";

type RequestOutcome = RequestStatus;
type SortDirection = "asc" | "desc";
type SortKey = "timestamp" | "client" | "provider" | "model" | "totalTokens" | "latencyMs" | "costUsd" | "status";
type RequestTimeRange = "1h" | "6h" | "24h" | "7d";

interface SortConfig {
  key: SortKey;
  direction: SortDirection;
}

const sortableColumns: Array<{ key: SortKey; label: string }> = [
  { key: "timestamp", label: "Time" },
  { key: "client", label: "Client" },
  { key: "provider", label: "Provider" },
  { key: "model", label: "Model" },
  { key: "totalTokens", label: "Tokens" },
  { key: "latencyMs", label: "Duration" },
  { key: "costUsd", label: "Cost" },
  { key: "status", label: "Status" },
];

const requestOutcomeStyles: Record<RequestOutcome, string> = {
  success: "bg-accent-green-bg text-accent-green",
  error: "bg-accent-red-bg text-accent-red",
  cancelled: "bg-bg-card-muted text-text-muted",
};

function formatDuration(latencyMs: number): string {
  if (latencyMs >= 1000) {
    return `${(latencyMs / 1000).toFixed(2)} s`;
  }

  return `${latencyMs} ms`;
}

function getOutcome(row: RequestRow): RequestOutcome {
  return row.status;
}

function renderClientIcon(client: RequestRow["client"]) {
  switch (client) {
    case "Claude Code":
      return <ClaudeCode.Color size={20} />;
    case "OpenAI SDK":
      return <OpenAI size={20} />;
    case "Gemini CLI":
      return <GeminiCLI.Color size={20} />;
    case "Codex":
      return <Codex.Color size={20} />;
    case "Cursor":
      return <Cursor size={20} />;
    default:
      return <span className="text-sm leading-none font-semibold text-text-secondary">
        {client.slice(0, 2).toUpperCase()}
      </span>;
  }
}

function FilterSelect({
  id,
  label,
  value,
  onValueChange,
  options,
}: {
  id: string;
  label: string;
  value: string;
  onValueChange: (value: string) => void;
  options: { label: string; value: string }[];
}) {
  return (
    <div className="min-w-0 space-y-1">
      <Select value={value} onValueChange={onValueChange}>
        <SelectTrigger
          id={id}
          aria-label={label}
          className="h-11 w-full rounded-lg border-border-default text-xs text-text-primary"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent position="popper" align="start" className="rounded-lg p-1">
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value} className="rounded-md text-xs">
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

export default function RequestsPage() {
  const hasLoadedRequests = useRef(false);
  const [payload, setPayload] = useState<Awaited<ReturnType<typeof fetchRequestsAnalytics>> | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const rowsPerPage = 5;
  const [sortConfig, setSortConfig] = useState<SortConfig>({
    key: "timestamp",
    direction: "desc",
  });
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedRowId, setSelectedRowId] = useState<string | null>(null);
  const [selectedRow, setSelectedRow] = useState<RequestRow | null>(null);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [clientFilter, setClientFilter] = useState<RequestRow["client"] | "all">("all");
  const [providerFilter, setProviderFilter] = useState<string>("all");
  const [modelFilter, setModelFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<RequestStatus | "all">("all");
  const [timeRangeFilter, setTimeRangeFilter] = useState<RequestTimeRange>("24h");
  const [ioLoggingEnabled, setIoLoggingEnabled] = useState(false);
  const [refreshIntervalMs, setRefreshIntervalMs] = useState(30_000);
  const [isEnablingIoLogging, setIsEnablingIoLogging] = useState(false);
  const [ioEnableError, setIoEnableError] = useState<string | null>(null);
  const rows = payload?.rows ?? [];

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setDebouncedSearch(searchQuery.trim());
      setCurrentPage(1);
    }, 300);
    return () => window.clearTimeout(timeoutId);
  }, [searchQuery]);

  useEffect(() => {
    let active = true;

    void fetchAdminSettings()
      .then((settings) => {
        if (!active) {
          return;
        }
        setIoLoggingEnabled(settings.settings.tracking.io_logging ?? false);
        const seconds = settings.settings.appearance.refresh_interval_seconds ?? 30;
        setRefreshIntervalMs(seconds * 1000);
      })
      .catch(() => {
        if (!active) {
          return;
        }
        setIoLoggingEnabled(false);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    const loadRequests = async () => {
      try {
        const nextPayload = await fetchRequestsAnalytics({
          page: currentPage,
          pageSize: rowsPerPage,
          search: debouncedSearch || undefined,
          client: clientFilter === "all" ? undefined : clientFilter,
          provider: providerFilter === "all" ? undefined : providerFilter,
          model: modelFilter === "all" ? undefined : modelFilter,
          status: statusFilter === "all" ? undefined : statusFilter,
          timeRange: timeRangeFilter,
          sort: sortConfig.key,
          direction: sortConfig.direction,
        });
        if (!active) {
          return;
        }
        setPayload(nextPayload);
        setErrorMessage(null);
        if (currentPage > Math.max(1, nextPayload.pagination.totalPages)) {
          setCurrentPage(Math.max(1, nextPayload.pagination.totalPages));
        }
      } catch {
        if (active) {
          setErrorMessage("Backend unreachable. Start the ModelPort proxy and refresh this page.");
        }
      } finally {
        if (active) {
          setIsLoading(false);
          hasLoadedRequests.current = true;
        }
      }
    };

    setIsLoading(!hasLoadedRequests.current);
    void loadRequests();
    const intervalId = window.setInterval(() => void loadRequests(), refreshIntervalMs);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [
    clientFilter,
    currentPage,
    debouncedSearch,
    modelFilter,
    providerFilter,
    refreshIntervalMs,
    sortConfig.direction,
    sortConfig.key,
    statusFilter,
    timeRangeFilter,
  ]);

  const handleEnableIoLogging = async () => {
    setIsEnablingIoLogging(true);
    setIoEnableError(null);

    try {
      const tracking = await patchTrackingSettings({ io_logging: true });
      setIoLoggingEnabled(tracking.io_logging ?? true);
    } catch (error) {
      setIoEnableError(
        error instanceof Error ? error.message : "Failed to enable I/O logging.",
      );
    } finally {
      setIsEnablingIoLogging(false);
    }
  };

  const totalRows = payload?.pagination.totalItems ?? 0;
  const totalPages = Math.max(1, payload?.pagination.totalPages ?? 0);

  const openRequestDetails = async (rowId: string) => {
    setSelectedRowId(rowId);
    setSelectedRow(null);
    setDetailError(null);
    setIsDetailLoading(true);
    setDetailOpen(true);
    try {
      setSelectedRow(await fetchRequestDetail(rowId));
    } catch (error) {
      setDetailError(
        error instanceof Error ? error.message : "Failed to load request details.",
      );
    } finally {
      setIsDetailLoading(false);
    }
  };

  const startRow = totalRows === 0 ? 0 : (currentPage - 1) * rowsPerPage + 1;
  const endRow = totalRows === 0 ? 0 : Math.min(currentPage * rowsPerPage, totalRows);
  const canGoPrevious = currentPage > 1;
  const canGoNext = currentPage < totalPages;

  const pageButtons = useMemo(() => {
    const buttons = new Set<number>([1, totalPages, currentPage - 1, currentPage, currentPage + 1]);

    return Array.from(buttons)
      .filter((page) => page >= 1 && page <= totalPages)
      .sort((a, b) => a - b);
  }, [currentPage, totalPages]);

  const onSort = (key: SortKey) => {
    setSortConfig((currentSort) => {
      const nextDirection =
        currentSort.key === key
          ? currentSort.direction === "asc"
            ? "desc"
            : "asc"
          : key === "timestamp"
            ? "desc"
            : "asc";

      return { key, direction: nextDirection };
    });
    setCurrentPage(1);
  };

  const filterOptions = {
    client: [
      { value: "all", label: "All Clients" },
      ...(payload?.filters.clients ?? []).map((client) => ({
        value: client,
        label: client,
      })),
    ],
    provider: [
      { value: "all", label: "All Providers" },
      ...(payload?.filters.providers ?? []).map((provider) => ({
        value: provider,
        label: provider,
      })),
    ],
    model: [
      { value: "all", label: "All Models" },
      ...(payload?.filters.models ?? []).map((model) => ({
        value: model,
        label: model,
      })),
    ],
    status: [
      { value: "all", label: "All Statuses" },
      { value: "success", label: "Success" },
      { value: "error", label: "Error" },
      { value: "cancelled", label: "Cancelled" },
    ],
    timeRange: [
      { value: "1h", label: "Last hour" },
      { value: "6h", label: "Last 6 hours" },
      { value: "24h", label: "Last 24 hours" },
      { value: "7d", label: "Last 7 days" },
    ],
  };

  if (isLoading) {
    return <div className="text-sm text-text-secondary">Loading request analytics...</div>;
  }

  return (
    <div className="space-y-5">
      {errorMessage ? (
        <div className="rounded-xl border border-accent-red/20 bg-accent-red-bg px-4 py-3 text-sm text-accent-red">
          {errorMessage}
        </div>
      ) : null}
      <section className="grid items-end gap-3 sm:grid-cols-2 xl:grid-cols-[minmax(0,1.9fr)_repeat(4,minmax(0,1fr))_minmax(0,1.1fr)_auto]">
        <div className="relative min-w-0 xl:col-span-1">
          <MagnifyingGlassIcon
            size={16}
            className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-text-faint"
          />
          <Input
            type="search"
            placeholder="Search requests"
            value={searchQuery}
            onChange={(event) => {
              setSearchQuery(event.target.value);
            }}
            className="h-11 w-full rounded-lg border-border-default pr-3 pl-9 text-sm"
          />
        </div>

        <FilterSelect
          id="client-filter"
          label="Client"
          value={clientFilter}
          onValueChange={(value) => {
            setClientFilter(value as RequestRow["client"] | "all");
            setCurrentPage(1);
          }}
          options={filterOptions.client}
        />
        <FilterSelect
          id="provider-filter"
          label="Provider"
          value={providerFilter}
          onValueChange={(value) => {
            setProviderFilter(value);
            setCurrentPage(1);
          }}
          options={filterOptions.provider}
        />
        <FilterSelect
          id="model-filter"
          label="Model"
          value={modelFilter}
          onValueChange={(value) => {
            setModelFilter(value);
            setCurrentPage(1);
          }}
          options={filterOptions.model}
        />
        <FilterSelect
          id="status-filter"
          label="Status"
          value={statusFilter}
          onValueChange={(value) => {
            setStatusFilter(value as RequestStatus | "all");
            setCurrentPage(1);
          }}
          options={filterOptions.status}
        />
        <div className="min-w-0 space-y-1">
          <Select
            value={timeRangeFilter}
            onValueChange={(value) => {
              setTimeRangeFilter(value as RequestTimeRange);
              setCurrentPage(1);
            }}
          >
            <SelectTrigger
              id="time-range-filter"
              className="h-11 w-full rounded-lg border-border-default text-sm text-text-primary"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent position="popper" align="start" className="rounded-lg p-1">
              {filterOptions.timeRange.map((range) => (
                <SelectItem key={range.value} value={range.value} className="rounded-md text-sm">
                  {range.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

      </section>

      <section className="card-surface max-w-full overflow-hidden">
        <div className="max-w-full">
          <table className="w-full table-fixed border-collapse text-left tabular-nums">
            <colgroup>
              <col style={{ width: "14%" }} />
              <col style={{ width: "14%" }} />
              <col style={{ width: "14%" }} />
              <col style={{ width: "15%" }} />
              <col style={{ width: "14%" }} />
              <col style={{ width: "9%" }} />
              <col style={{ width: "8%" }} />
              <col style={{ width: "12%" }} />
            </colgroup>
          <thead>
            <tr className="border-b borer-border-subtle bg-bg-card-muted text-sm text-text-secondary">
              {sortableColumns.map((column) => {
                const isSortedColumn = sortConfig.key === column.key;
                const SortIcon = isSortedColumn && sortConfig.direction === "asc" ? CaretUpIcon : CaretDownIcon;

                return (
                  <th key={column.key} className="px-5 py-3 font-medium whitespace-nowrap">
                    <button
                      type="button"
                      onClick={() => onSort(column.key)}
                      className="inline-flex max-w-full items-center gap-2"
                    >
                      <span className="truncate">{column.label}</span>
                      {isSortedColumn ? (
                        <SortIcon size={12} className="text-text-primary" />
                      ) : null}
                    </button>
                  </th>
                );
              })}
              <th className="px-3 py-3 font-medium" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const outcome = getOutcome(row);
              const outcomeLabel = outcome.charAt(0).toUpperCase() + outcome.slice(1);

              return (
                <tr
                  key={row.id}
                  onClick={() => void openRequestDetails(row.id)}
                  className={cn(
                    "cursor-pointer border-b border-border-subtle text-sm text-text-secondary last:border-b-0 hover:bg-bg-card-muted",
                    selectedRowId === row.id && detailOpen && "bg-bg-card-muted",
                  )}
                >
                  <td className="px-5 py-3.5 whitespace-nowrap">{formatTimestamp(row.timestamp, "table")}</td>
                  <td className="px-5 py-3.5">
                    <div className="flex min-w-0 items-center gap-3">
                      {renderClientIcon(row.client)}
                      <span className="truncate font-medium text-text-primary">{row.client}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex min-w-0 items-center gap-2.5">
                      <ProviderIcon provider={row.provider} />
                      <span className="truncate">{row.provider}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5 truncate">{row.model}</td>
                  <td className="px-5 py-3.5">
                    <div className="space-y-0.5 overflow-hidden whitespace-nowrap">
                      <p className="font-medium text-text-primary">
                        {formatInteger(row.totalTokens)}
                      </p>
                      <p className="truncate text-xs text-text-muted">
                        {formatInteger(row.inputTokens)} / {formatInteger(row.outputTokens)}
                      </p>
                    </div>
                  </td>
                  <td className="px-5 py-3.5 whitespace-nowrap">{formatDuration(row.latencyMs)}</td>
                  <td className="px-5 py-3.5 whitespace-nowrap">{formatCost(row.costUsd, 4)}</td>
                  <td className="px-5 py-3.5 whitespace-nowrap">
                    <span
                      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${requestOutcomeStyles[outcome]}`}
                    >
                      <span className="status-dot bg-current" />
                      <span>{outcomeLabel}</span>
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
          </table>
        </div>

        <div className="flex flex-col gap-3 border-t border-border-subtle px-5 py-3 text-sm text-text-secondary sm:flex-row sm:items-center sm:justify-between">
          <p>
            Showing {formatInteger(startRow)} to {formatInteger(endRow)} of {formatInteger(totalRows)} requests
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

      <RequestDetailSheet
        row={selectedRow}
        open={detailOpen}
        isLoading={isDetailLoading}
        errorMessage={detailError}
        onOpenChange={(open) => {
          setDetailOpen(open);
          if (!open) {
            setSelectedRowId(null);
            setSelectedRow(null);
            setDetailError(null);
            setIoEnableError(null);
          }
        }}
        ioLoggingEnabled={ioLoggingEnabled}
        isEnablingIoLogging={isEnablingIoLogging}
        ioEnableError={ioEnableError}
        onEnableIoLogging={() => void handleEnableIoLogging()}
      />
    </div>
  );
}
