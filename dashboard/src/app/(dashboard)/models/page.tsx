"use client";

import { useEffect, useMemo, useState } from "react";

import {
  CubeIcon,
  CurrencyDollarIcon,
  MagnifyingGlassIcon,
  PulseIcon,
  StackIcon,
} from "@phosphor-icons/react";

import { ModelCard } from "@/components/dashboard/models/model-card";
import { MultiFilterSelect } from "@/components/dashboard/models/multi-filter-select";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { fetchProviderModels } from "@/lib/admin-api";
import {
  collectFilterOptions,
  DEFAULT_MODEL_FILTERS,
  filterModelRows,
  flattenProviderModels,
  sortModelRows,
  type ModelDirectoryFilters,
  type ModelSortKey,
} from "@/lib/models-directory";
import { formatInteger, formatOptionalTimestamp } from "@/lib/format";

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

export default function ModelsPage() {
  const [payload, setPayload] = useState<Awaited<ReturnType<typeof fetchProviderModels>> | null>(
    null,
  );
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [filters, setFilters] = useState<ModelDirectoryFilters>(DEFAULT_MODEL_FILTERS);
  const [sortKey, setSortKey] = useState<ModelSortKey>("usage");

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

  const allRows = useMemo(
    () => flattenProviderModels(payload?.providers ?? []),
    [payload],
  );

  const filterOptions = useMemo(() => collectFilterOptions(allRows), [allRows]);

  const filteredRows = useMemo(
    () => sortModelRows(filterModelRows(allRows, filters), sortKey),
    [allRows, filters, sortKey],
  );

  const totals = payload?.totals;

  if (isLoading) {
    return <div className="text-sm text-text-secondary">Loading model directory...</div>;
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
            <div>
              <p className="text-sm font-medium text-text-secondary">Live models</p>
              <p className="mt-1 text-lg font-semibold text-text-primary">
                {formatInteger(totals?.live_model_count ?? allRows.length)}
              </p>
            </div>
            <span className="card-surface-soft inline-flex h-10 w-10 items-center justify-center rounded-xl text-text-secondary">
              <CubeIcon size={20} />
            </span>
          </div>
          <p className="mt-2 text-sm text-text-muted">Across healthy provider catalogs</p>
        </article>

        <article className="card-surface p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-text-secondary">Providers</p>
              <p className="mt-1 text-lg font-semibold text-text-primary">
                {formatInteger(totals?.provider_count ?? payload?.providers.length ?? 0)}
              </p>
            </div>
            <span className="card-surface-soft inline-flex h-10 w-10 items-center justify-center rounded-xl text-text-secondary">
              <StackIcon size={20} />
            </span>
          </div>
          <p className="mt-2 text-sm text-text-muted">Operational upstream catalogs</p>
        </article>

        <article className="card-surface p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-text-secondary">Priced models</p>
              <p className="mt-1 text-lg font-semibold text-text-primary">
                {formatInteger(totals?.priced_model_count ?? 0)}
              </p>
            </div>
            <span className="card-surface-soft inline-flex h-10 w-10 items-center justify-center rounded-xl text-text-secondary">
              <CurrencyDollarIcon size={20} />
            </span>
          </div>
          <p className="mt-2 text-sm text-text-muted">OpenRouter or local pricing metadata</p>
        </article>

        <article className="card-surface p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-text-secondary">Used in proxy</p>
              <p className="mt-1 text-lg font-semibold text-text-primary">
                {formatInteger(totals?.used_model_count ?? 0)}
              </p>
            </div>
            <span className="card-surface-soft inline-flex h-10 w-10 items-center justify-center rounded-xl text-text-secondary">
              <PulseIcon size={20} />
            </span>
          </div>
          <p className="mt-2 text-sm text-text-muted">
            Metadata sync {formatOptionalTimestamp(totals?.metadata_synced_at)}
          </p>
        </article>
      </section>

      <section className="card-surface p-5">
        <div className="flex flex-col gap-4">
          <div>
            <p className="text-sm font-medium text-text-primary">Search and filter</p>
            <p className="mt-1 text-sm text-text-muted">
              Browse enriched model metadata from live provider catalogs and OpenRouter reference data.
            </p>
          </div>

          <div className="relative">
            <MagnifyingGlassIcon
              size={16}
              className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-text-faint"
            />
            <Input
              type="search"
              placeholder="Search models, providers, capabilities..."
              value={filters.search}
              onChange={(event) =>
                setFilters((current) => ({ ...current, search: event.target.value }))
              }
              className="h-11 rounded-lg border-border-default pl-9"
            />
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <MultiFilterSelect
              id="provider-filter"
              label="Provider"
              emptyLabel="All providers"
              selectedValues={filters.providers}
              onSelectedValuesChange={(providers) =>
                setFilters((current) => ({ ...current, providers }))
              }
              options={filterOptions.providers.map((provider) => ({
                label: provider.label,
                value: provider.value,
              }))}
            />
            <MultiFilterSelect
              id="modality-filter"
              label="Modality"
              emptyLabel="All modalities"
              selectedValues={filters.modalities}
              onSelectedValuesChange={(modalities) =>
                setFilters((current) => ({ ...current, modalities }))
              }
              options={filterOptions.modalities.map((modality) => ({
                label: modality,
                value: modality,
              }))}
            />
            <MultiFilterSelect
              id="capability-filter"
              label="Capability"
              emptyLabel="All capabilities"
              selectedValues={filters.capabilities}
              onSelectedValuesChange={(capabilities) =>
                setFilters((current) => ({ ...current, capabilities }))
              }
              options={filterOptions.capabilities.map((capability) => ({
                label: capability,
                value: capability,
              }))}
            />
            <MultiFilterSelect
              id="price-filter"
              label="Pricing"
              emptyLabel="Any pricing"
              selectedValues={filters.priceTiers}
              onSelectedValuesChange={(priceTiers) =>
                setFilters((current) => ({
                  ...current,
                  priceTiers: priceTiers as ModelDirectoryFilters["priceTiers"],
                }))
              }
              options={[
                { label: "Free", value: "free" },
                { label: "Has pricing", value: "paid" },
              ]}
            />
            <MultiFilterSelect
              id="usage-filter"
              label="Usage"
              emptyLabel="All models"
              selectedValues={filters.usage}
              onSelectedValuesChange={(usage) =>
                setFilters((current) => ({
                  ...current,
                  usage: usage as ModelDirectoryFilters["usage"],
                }))
              }
              options={[
                { label: "Used in proxy", value: "used" },
                { label: "Not used yet", value: "unused" },
              ]}
            />
            <MultiFilterSelect
              id="context-filter"
              label="Context"
              emptyLabel="Any context"
              selectedValues={filters.contexts}
              onSelectedValuesChange={(contexts) =>
                setFilters((current) => ({
                  ...current,
                  contexts: contexts as ModelDirectoryFilters["contexts"],
                }))
              }
              options={[
                { label: "Up to 128K", value: "128k" },
                { label: "200K+", value: "200k" },
                { label: "1M+", value: "1m" },
              ]}
            />
            <FilterSelect
              id="sort-filter"
              label="Sort"
              value={sortKey}
              onValueChange={(value) => setSortKey(value as ModelSortKey)}
              options={[
                { label: "Most used", value: "usage" },
                { label: "Name", value: "name" },
                { label: "Provider", value: "provider" },
                { label: "Context window", value: "context" },
                { label: "Input price", value: "price" },
                { label: "Recently fetched", value: "fetched" },
              ]}
            />
          </div>
        </div>
      </section>

      <section className="space-y-4">
        <div className="flex items-center justify-between gap-3 text-sm text-text-secondary">
          <p>
            Showing {formatInteger(filteredRows.length)} of {formatInteger(allRows.length)} models
          </p>
        </div>

        {filteredRows.length === 0 ? (
          <div className="card-surface px-5 py-10 text-center text-sm text-text-muted">
            No models match the current filters.
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {filteredRows.map((row) => (
              <ModelCard key={row.key} row={row} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
