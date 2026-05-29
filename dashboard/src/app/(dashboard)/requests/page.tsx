"use client";

import { useMemo, useState } from "react";

import {
  CaretDownIcon,
  CaretLeftIcon,
  CaretRightIcon,
  CaretUpIcon,
  CopyIcon,
  DownloadSimpleIcon,
  MagnifyingGlassIcon,
} from "@phosphor-icons/react";
import { Anthropic, Gemini, OpenAI, ClaudeCode, GeminiCLI, Codex, Cursor, OpenRouter, Ollama } from "@lobehub/icons";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { dashboardMockData, type RequestRow, type RequestStatus } from "@/lib/mock-dashboard-data";

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

const TIME_RANGE_IN_MS: Record<RequestTimeRange, number> = {
  "1h": 60 * 60 * 1000,
  "6h": 6 * 60 * 60 * 1000,
  "24h": 24 * 60 * 60 * 1000,
  "7d": 7 * 24 * 60 * 60 * 1000,
};

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString("en-US", {
    month: "2-digit",
    day: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDuration(latencyMs: number): string {
  if (latencyMs >= 1000) {
    return `${(latencyMs / 1000).toFixed(2)} s`;
  }

  return `${latencyMs} ms`;
}

function formatCost(value: number): string {
  return `$${value.toFixed(4)}`;
}

function formatInteger(value: number): string {
  return value.toLocaleString("en-US");
}

function getOutcome(row: RequestRow): RequestOutcome {
  return row.status;
}

function renderProviderIcon(provider: string) {

  switch (provider) {
    case "Anthropic":
      return <Anthropic size={20} />;
    case "Gemini":
      return <Gemini.Color size={20} />;
    case "OpenAI":
      return <OpenAI size={20} />;
    case "OpenRouter":
      return <OpenRouter size={20} />;
    case "Ollama":
      return <Ollama size={20} />;
    default:
      return <span className="text-sm leading-none font-semibold text-text-secondary">
        {provider.slice(0, 2).toUpperCase()}
      </span>;
  }
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
        <SelectTrigger id={id} aria-label={label} className="h-11 w-full rounded-lg text-xs text-text-primary">
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
  const allRows = dashboardMockData.requests.rows;
  const rowsPerPage = 5;
  const [sortConfig, setSortConfig] = useState<SortConfig>({
    key: "timestamp",
    direction: "desc",
  });
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedRowId, setSelectedRowId] = useState<string | null>(allRows[0]?.id ?? null);
  const [searchQuery, setSearchQuery] = useState("");
  const [clientFilter, setClientFilter] = useState<RequestRow["client"] | "all">("all");
  const [providerFilter, setProviderFilter] = useState<string>("all");
  const [modelFilter, setModelFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<RequestStatus | "all">("all");
  const [timeRangeFilter, setTimeRangeFilter] = useState<RequestTimeRange>("24h");
  const [referenceNow] = useState(() => Date.now());

  const filteredRows = useMemo(() => {
    const cutoffTimestamp = referenceNow - TIME_RANGE_IN_MS[timeRangeFilter];
    const normalizedSearch = searchQuery.trim().toLowerCase();

    return allRows.filter((row) => {
      if (clientFilter !== "all" && row.client !== clientFilter) {
        return false;
      }
      if (providerFilter !== "all" && row.provider !== providerFilter) {
        return false;
      }
      if (modelFilter !== "all" && row.model !== modelFilter) {
        return false;
      }
      if (statusFilter !== "all" && row.status !== statusFilter) {
        return false;
      }
      if (new Date(row.timestamp).getTime() < cutoffTimestamp) {
        return false;
      }
      if (!normalizedSearch) {
        return true;
      }

      const searchableText = [
        row.id,
        row.client,
        row.provider,
        row.model,
        row.endpoint,
        row.status,
      ]
        .join(" ")
        .toLowerCase();

      return searchableText.includes(normalizedSearch);
    });
  }, [allRows, clientFilter, modelFilter, providerFilter, referenceNow, searchQuery, statusFilter, timeRangeFilter]);

  const sortedRows = useMemo(() => {
    const rowsToSort = [...filteredRows];
    const directionMultiplier = sortConfig.direction === "asc" ? 1 : -1;

    rowsToSort.sort((left, right) => {
      switch (sortConfig.key) {
        case "timestamp":
          return (new Date(left.timestamp).getTime() - new Date(right.timestamp).getTime()) * directionMultiplier;
        case "client":
          return left.client.localeCompare(right.client) * directionMultiplier;
        case "provider":
          return left.provider.localeCompare(right.provider) * directionMultiplier;
        case "model":
          return left.model.localeCompare(right.model) * directionMultiplier;
        case "totalTokens":
          return (left.totalTokens - right.totalTokens) * directionMultiplier;
        case "latencyMs":
          return (left.latencyMs - right.latencyMs) * directionMultiplier;
        case "costUsd":
          return (left.costUsd - right.costUsd) * directionMultiplier;
        case "status":
          return getOutcome(left).localeCompare(getOutcome(right)) * directionMultiplier;
        default:
          return 0;
      }
    });

    return rowsToSort;
  }, [filteredRows, sortConfig]);

  const totalRows = sortedRows.length;
  const totalPages = Math.max(1, Math.ceil(totalRows / rowsPerPage));

  const rows = useMemo(() => {
    const startIndex = (currentPage - 1) * rowsPerPage;
    return sortedRows.slice(startIndex, startIndex + rowsPerPage);
  }, [currentPage, sortedRows]);

  const selectedRow = useMemo(() => {
    if (sortedRows.length === 0) {
      return null;
    }
    if (!selectedRowId) {
      return sortedRows[0];
    }

    return sortedRows.find((row) => row.id === selectedRowId) ?? sortedRows[0];
  }, [selectedRowId, sortedRows]);
  const selectedOutcome: RequestOutcome = selectedRow ? getOutcome(selectedRow) : "success";

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
      ...dashboardMockData.requests.filters.clients.map((client) => ({
        value: client,
        label: client,
      })),
    ],
    provider: [
      { value: "all", label: "All Providers" },
      ...dashboardMockData.requests.filters.providers.map((provider) => ({
        value: provider,
        label: provider,
      })),
    ],
    model: [
      { value: "all", label: "All Models" },
      ...dashboardMockData.requests.filters.models.map((model) => ({
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

  return (
    <div className="space-y-5">
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
              setCurrentPage(1);
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
            <SelectTrigger id="time-range-filter" className="h-11 w-full rounded-lg text-sm text-text-primary">
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

        <Button
          type="button"
          variant="outline"
          size="lg"
          className="h-11 w-full rounded-lg border-border-default px-4 text-sm sm:w-auto"
        >
          <DownloadSimpleIcon size={16} />
          Export
        </Button>
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
                  onClick={() => setSelectedRowId(row.id)}
                  className="border-b border-border-subtle hover:bg-bg-card-muted text-sm text-text-secondary last:border-b-0"
                >
                  <td className="px-5 py-3.5 whitespace-nowrap">{formatTimestamp(row.timestamp)}</td>
                  <td className="px-5 py-3.5">
                    <div className="flex min-w-0 items-center gap-3">
                      {renderClientIcon(row.client)}
                      <span className="truncate font-medium text-text-primary">{row.client}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex min-w-0 items-center gap-2.5">
                      {renderProviderIcon(row.provider)}
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
                  <td className="px-5 py-3.5 whitespace-nowrap">{formatCost(row.costUsd)}</td>
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

      <section className="card-surface overflow-hidden">
        {selectedRow ? (
          <div className="grid lg:grid-cols-[1fr_2fr]">
            <div className="p-5 lg:border-r lg:border-border-subtle">
              <div className="mb-4 flex items-center gap-3">
                <h3>Request details</h3>
                <span
                  className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${requestOutcomeStyles[selectedOutcome]}`}
                >
                  <span className="status-dot bg-current" />
                  {selectedOutcome.charAt(0).toUpperCase() + selectedOutcome.slice(1)}
                </span>
              </div>

              <dl className="grid grid-cols-[120px_1fr] gap-y-2 text-sm">
                <dt className="text-text-secondary">Request ID</dt>
                <dd className="flex items-center gap-2 font-medium text-text-primary">
                  {selectedRow.id}
                  <button
                    type="button"
                    aria-label="Copy request ID"
                    className="inline-flex h-5 w-5 items-center justify-center rounded-sm text-text-muted hover:bg-bg-card-muted"
                  >
                    <CopyIcon size={13} />
                  </button>
                </dd>

                <dt className="text-text-secondary">Endpoint</dt>
                <dd className="font-medium text-text-primary">{selectedRow.endpoint}</dd>

                <dt className="text-text-secondary">Client</dt>
                <dd className="font-medium text-text-primary">{selectedRow.client}</dd>

                <dt className="text-text-secondary">Provider</dt>
                <dd className="font-medium text-text-primary">{selectedRow.provider}</dd>

                <dt className="text-text-secondary">Model</dt>
                <dd className="font-medium text-text-primary">{selectedRow.model}</dd>
              </dl>
            </div>

            <div className="p-5">
              <div className="mb-4 flex items-center justify-between">
                <h3>Metrics</h3>
              </div>

              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <article className="card-surface-soft p-4">
                  <p className="text-xs text-text-secondary">Tokens</p>
                  <p className="mt-2 text-xl leading-none font-semibold text-text-primary">
                    {formatInteger(selectedRow.totalTokens)}
                  </p>
                  <div className="mt-3 space-y-1 text-sm text-text-secondary">
                    <p>
                      <span className="font-medium text-sm text-text-primary">
                        {formatInteger(selectedRow.inputTokens)}
                      </span>{" "}
                      Input
                    </p>
                    <p>
                      <span className="font-medium text-sm text-text-primary">
                        {formatInteger(selectedRow.outputTokens)}
                      </span>{" "}
                      Output
                    </p>
                  </div>
                </article>

                <article className="card-surface-soft p-4">
                  <p className="text-xs text-text-secondary">Latency</p>
                  <p className="mt-2 text-xl leading-none font-semibold text-text-primary">
                    {formatDuration(selectedRow.latencyMs)}
                  </p>
                  <div className="mt-3 space-y-1 text-sm text-text-secondary">
                    <p>
                      <span className="font-medium text-sm text-text-primary">
                        {Math.round(selectedRow.latencyMs * 0.42)} ms
                      </span>{" "}
                      TTFB
                    </p>
                    <p>
                      <span className="font-medium text-sm text-text-primary">
                        {selectedRow.latencyMs} ms
                      </span>{" "}
                      Total
                    </p>
                  </div>
                </article>

                <article className="card-surface-soft p-4">
                  <p className="text-xs text-text-secondary">Estimated cost</p>
                  <p className="mt-2 text-xl leading-none font-semibold text-text-primary">
                    {formatCost(selectedRow.costUsd)}
                  </p>
                  <div className="mt-3 space-y-1 text-sm text-text-secondary">
                    <p>
                      <span className="font-medium text-sm text-text-primary">
                        {formatCost(selectedRow.costUsd * 0.71)}
                      </span>{" "}
                      Input
                    </p>
                    <p>
                      <span className="font-medium text-sm text-text-primary">
                        {formatCost(selectedRow.costUsd * 0.29)}
                      </span>{" "}
                      Output
                    </p>
                  </div>
                </article>

                <article className="card-surface-soft p-4">
                  <p className="text-xs text-text-secondary">Status</p>
                  <p className={`mt-2 text-xl leading-none font-semibold ${requestOutcomeStyles[selectedOutcome]} bg-transparent!`}>
                    {selectedOutcome.charAt(0).toUpperCase() + selectedOutcome.slice(1)}
                  </p>
                  <div className="mt-3 space-y-1 text-sm text-text-secondary">
                    <p>{formatTimestamp(selectedRow.timestamp)}</p>
                  </div>
                </article>
              </div>
            </div>
          </div>
        ) : (
          <div className="p-8 text-sm text-text-secondary">
            No requests match the current search and filters.
          </div>
        )}
      </section>
    </div>
  );
}
