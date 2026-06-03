"use client";

import { useEffect, useMemo, useState } from "react";

import {
  CaretLeftIcon,
  CaretRightIcon,
  ClockIcon,
  CubeIcon,
  RobotIcon,
  StackIcon,
} from "@phosphor-icons/react";

import { renderProviderIcon } from "@/components/brand/render-provider-icon";
import {
  fetchProviderModels,
  type ProviderCatalogEntry,
} from "@/lib/admin-api";

interface ModelTableRow {
  id: string;
  displayName: string;
  provider: string;
  owner: string;
  contextWindow: string;
  modelId: string;
  fetchedAt: string;
  providerModelCount: number;
  baseUrl: string;
}

function formatInteger(value: number): string {
  return value.toLocaleString("en-US");
}

function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "Unknown";
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(parsed);
}

function formatModelLabel(modelSlug: string): string {
  if (/^o\d+$/i.test(modelSlug)) {
    return modelSlug.toLowerCase();
  }

  const cleaned = modelSlug
    .replace(/:latest$/i, "")
    .replace(/-latest$/i, "")
    .replace(/-preview$/i, "")
    .replace(/-\d{8}$/i, "");
  const parts = cleaned.split(/[-_:]/).filter(Boolean);

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
  if (
    model.includes("gpt-4.1") ||
    model.includes("gemini-2.5") ||
    model.includes("gemini-2.0")
  ) {
    return "1M";
  }

  if (model.includes("gpt-3.5")) {
    return "16K";
  }

  if (model.includes("gpt-4o-mini")) {
    return "128K";
  }

  return "Unknown";
}

function largestCatalogProvider(
  providers: ProviderCatalogEntry[],
): ProviderCatalogEntry | null {
  if (providers.length === 0) {
    return null;
  }

  return [...providers].sort(
    (left, right) => right.available_model_count - left.available_model_count,
  )[0];
}

export default function ModelsPage() {
  const rowsPerPage = 12;
  const [currentPage, setCurrentPage] = useState(1);
  const [payload, setPayload] = useState<Awaited<ReturnType<typeof fetchProviderModels>> | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    void (async () => {
      try {
        const nextPayload = await fetchProviderModels();
        if (!active) {
          return;
        }
        setPayload(nextPayload);
        setErrorMessage(null);
      } catch (error) {
        if (!active) {
          return;
        }
        setErrorMessage(
          error instanceof Error ? error.message : "Failed to load live provider models.",
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

  const healthyProviders = useMemo(() => payload?.providers ?? [], [payload]);

  const modelRows: ModelTableRow[] = useMemo(() => {
    return healthyProviders
      .flatMap((provider) =>
        provider.models.map((model) => ({
          id: `${provider.provider_id}:${model.id}`,
          displayName: model.display_name ?? formatModelLabel(model.id),
          provider: provider.display_name,
          owner: model.owned_by ?? provider.display_name,
          contextWindow: getContextWindow(model.id),
          modelId: model.id,
          fetchedAt: provider.fetched_at,
          providerModelCount: provider.available_model_count,
          baseUrl: provider.base_url,
        })),
      )
      .sort((left, right) => {
        if (right.providerModelCount !== left.providerModelCount) {
          return right.providerModelCount - left.providerModelCount;
        }
        return left.displayName.localeCompare(right.displayName);
      });
  }, [healthyProviders]);

  const providerCount = healthyProviders.length;
  const totalRows = modelRows.length;
  const largestProvider = useMemo(
    () => largestCatalogProvider(healthyProviders),
    [healthyProviders],
  );
  const latestFetch = useMemo(() => {
    const latest = [...healthyProviders]
      .map((provider) => provider.fetched_at)
      .sort()
      .at(-1);
    return latest ? formatTimestamp(latest) : "Unknown";
  }, [healthyProviders]);

  const totalPages = Math.max(1, Math.ceil(totalRows / rowsPerPage));
  const safeCurrentPage = Math.min(currentPage, totalPages);

  const pagedRows = useMemo(() => {
    const startIndex = (safeCurrentPage - 1) * rowsPerPage;
    return modelRows.slice(startIndex, startIndex + rowsPerPage);
  }, [modelRows, rowsPerPage, safeCurrentPage]);

  const pageButtons = useMemo(() => {
    if (totalPages <= 7) {
      return Array.from({ length: totalPages }, (_, index) => index + 1);
    }

    const pages = new Set<number>([1, totalPages]);
    for (let page = safeCurrentPage - 1; page <= safeCurrentPage + 1; page += 1) {
      if (page > 1 && page < totalPages) {
        pages.add(page);
      }
    }

    if (safeCurrentPage <= 3) {
      pages.add(2);
      pages.add(3);
      pages.add(4);
    }

    if (safeCurrentPage >= totalPages - 2) {
      pages.add(totalPages - 1);
      pages.add(totalPages - 2);
      pages.add(totalPages - 3);
    }

    return [...pages].sort((left, right) => left - right);
  }, [safeCurrentPage, totalPages]);

  const startRow = totalRows === 0 ? 0 : (safeCurrentPage - 1) * rowsPerPage + 1;
  const endRow = Math.min(safeCurrentPage * rowsPerPage, totalRows);
  const canGoPrevious = safeCurrentPage > 1;
  const canGoNext = safeCurrentPage < totalPages;
  const emptyRowCount = Math.max(0, rowsPerPage - pagedRows.length);

  if (isLoading) {
    return <div className="text-sm text-text-secondary">Loading live provider models...</div>;
  }

  return (
    <div className="space-y-6">
      {errorMessage ? (
        <div className="rounded-xl border border-accent-red/20 bg-accent-red-bg px-4 py-3 text-sm text-accent-red">
          {errorMessage}
        </div>
      ) : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article className="card-surface p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="flex flex-col">
              <p className="text-sm font-medium text-text-secondary">Live models</p>
              <p className="mt-1 text-lg font-semibold text-text-primary">{formatInteger(totalRows)}</p>
            </div>
            <span className="card-surface-soft inline-flex h-10 w-10 items-center justify-center rounded-xl text-text-secondary">
              <CubeIcon size={20} />
            </span>
          </div>
          <div className="mt-2 text-sm text-text-muted">
            Fetched from healthy provider model catalogs
          </div>
        </article>

        <article className="card-surface p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="flex flex-col">
              <p className="text-sm font-medium text-text-secondary">Healthy providers</p>
              <p className="mt-1 text-lg font-semibold text-text-primary">{formatInteger(providerCount)}</p>
            </div>
            <span className="card-surface-soft inline-flex h-10 w-10 items-center justify-center rounded-xl text-text-secondary">
              <StackIcon size={20} />
            </span>
          </div>
          <div className="mt-2 text-sm text-text-muted">
            Providers returning at least one model right now
          </div>
        </article>

        <article className="card-surface p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1 flex flex-col">
              <p className="text-sm font-medium text-text-secondary">Largest catalog</p>
              <p className="mt-1 truncate text-lg font-semibold text-text-primary">
                {largestProvider?.display_name ?? "None"}
              </p>
            </div>
            <span className="card-surface-soft inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-text-secondary">
              {largestProvider ? renderProviderIcon(largestProvider.display_name) : <RobotIcon size={20} />}
            </span>
          </div>
          <div className="mt-2 text-sm text-text-muted">
            {largestProvider ? `${largestProvider.available_model_count} live models` : "No healthy provider catalogs yet"}
          </div>
        </article>

        <article className="card-surface p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="flex flex-col">
              <p className="text-sm font-medium text-text-secondary">Latest refresh</p>
              <p className="mt-1 text-lg font-semibold text-text-primary">{latestFetch}</p>
            </div>
            <span className="card-surface-soft inline-flex h-10 w-10 items-center justify-center rounded-xl text-text-secondary">
              <ClockIcon size={20} />
            </span>
          </div>
          <div className="mt-2 text-sm text-text-muted">
            Last successful provider-model fetch timestamp
          </div>
        </article>
      </section>

      <section className="card-surface overflow-hidden">
        <div className="border-b border-border-subtle px-5 py-4 text-sm text-text-secondary">
          Live model discovery only. This table comes directly from healthy providers&apos; upstream model-list APIs.
        </div>
        <div className="overflow-x-auto">
          <table className="w-full table-fixed border-collapse text-left text-sm tabular-nums">
            <colgroup>
              <col style={{ width: "22%" }} />
              <col style={{ width: "15%" }} />
              <col style={{ width: "26%" }} />
              <col style={{ width: "12%" }} />
              <col style={{ width: "11%" }} />
              <col style={{ width: "14%" }} />
            </colgroup>
            <thead>
              <tr className="bg-bg-card-muted text-text-secondary">
                <th className="px-5 py-3 font-medium whitespace-nowrap">Model</th>
                <th className="px-5 py-3 font-medium whitespace-nowrap">Provider</th>
                <th className="px-5 py-3 font-medium whitespace-nowrap">Model ID</th>
                <th className="px-5 py-3 font-medium whitespace-nowrap">Owner</th>
                <th className="px-5 py-3 font-medium whitespace-nowrap">Context</th>
                <th className="px-5 py-3 font-medium whitespace-nowrap">Fetched</th>
              </tr>
            </thead>
            <tbody>
              {pagedRows.map((model) => (
                <tr
                  key={model.id}
                  className="border-t border-border-subtle text-text-secondary hover:bg-bg-card-muted"
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
                  <td className="px-5 py-3 text-text-primary">{model.provider}</td>
                  <td className="px-5 py-3">
                    <div className="truncate text-text-primary" title={model.modelId}>
                      {model.modelId}
                    </div>
                    <div className="mt-1 truncate text-xs text-text-muted" title={model.baseUrl}>
                      {model.baseUrl}
                    </div>
                  </td>
                  <td className="px-5 py-3 text-text-primary">{model.owner}</td>
                  <td className="px-5 py-3 text-text-primary">{model.contextWindow}</td>
                  <td className="px-5 py-3 text-text-primary">{formatTimestamp(model.fetchedAt)}</td>
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
                    <div className="opacity-0">placeholder</div>
                    <div className="mt-1 opacity-0">placeholder</div>
                  </td>
                  <td className="px-5 py-3">
                    <span className="opacity-0">placeholder</span>
                  </td>
                  <td className="px-5 py-3">
                    <span className="opacity-0">Unknown</span>
                  </td>
                  <td className="px-5 py-3">
                    <span className="opacity-0">Unknown</span>
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
                      page === safeCurrentPage
                        ? "inline-flex h-7 min-w-7 items-center justify-center rounded-md border border-text-primary px-2 text-text-primary"
                        : "inline-flex h-7 min-w-7 items-center justify-center rounded-md border border-border-subtle px-2"
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
        </div>
      </section>
    </div>
  );
}
