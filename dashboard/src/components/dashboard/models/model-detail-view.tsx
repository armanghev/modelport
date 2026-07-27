"use client";

import { ProviderIcon } from "@/components/brand/render-provider-icon";
import {
  formatContextLength,
  formatPricePerMillion,
  type ModelDirectoryRow,
} from "@/lib/models-directory";
import { formatCost, formatInteger } from "@/lib/format";

function DetailMetric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <article className="card-surface-soft p-4">
      <p className="text-xs text-text-secondary">{label}</p>
      <p className="mt-1 text-sm font-semibold text-text-primary">{value}</p>
    </article>
  );
}

function ChipList({ items, emptyLabel }: { items: string[]; emptyLabel: string }) {
  if (items.length === 0) {
    return <p className="text-sm text-text-muted">{emptyLabel}</p>;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span
          key={item}
          className="rounded-md border border-border-subtle bg-bg-card-muted px-2.5 py-1 text-xs text-text-secondary"
        >
          {item}
        </span>
      ))}
    </div>
  );
}

export function ModelDetailView({
  row,
}: {
  row: ModelDirectoryRow;
}) {
  const { model, providerName, providerId, baseUrl, fetchedAt } = row;
  const usage = model.usage;
  const architectureEntries = Object.entries(model.architecture ?? {}).filter(
    ([, value]) => value != null && value !== "",
  );

  return (
    <div className="space-y-6">
      <section className="card-surface p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 space-y-3">
            <p className="text-sm text-text-secondary">Model details</p>
            <div className="flex items-center gap-3">
              <span className="inline-flex h-10 w-10 items-center justify-center text-text-primary">
                <ProviderIcon provider={providerName} />
              </span>
              <div className="min-w-0">
                <h2 className="truncate text-2xl leading-tight">{model.display_name}</h2>
                <p className="truncate font-mono text-sm text-text-muted">{model.id}</p>
              </div>
            </div>
            {model.description ? (
              <p className="max-w-3xl text-sm text-text-secondary">{model.description}</p>
            ) : (
              <p className="text-sm text-text-muted">No description available for this model.</p>
            )}
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="rounded-md border border-border-subtle bg-bg-card-muted px-2.5 py-1 text-text-primary">
                {providerName}
              </span>
              <span className="rounded-md border border-border-subtle px-2.5 py-1 text-text-secondary">
                Source: {model.metadata_source}
              </span>
              {model.openrouter_id ? (
                <span className="rounded-md border border-border-subtle px-2.5 py-1 font-mono text-text-muted">
                  {model.openrouter_id}
                </span>
              ) : null}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <DetailMetric
          label="Context window"
          value={formatContextLength(model.context_length)}
        />
        <DetailMetric
          label="Input price"
          value={formatPricePerMillion(model.input_per_1m_usd)}
        />
        <DetailMetric
          label="Output price"
          value={formatPricePerMillion(model.output_per_1m_usd)}
        />
        <DetailMetric
          label="Requests (tracked)"
          value={formatInteger(usage?.requestCount ?? 0)}
        />
        <DetailMetric
          label="Token usage"
          value={formatInteger(usage?.tokenTotal ?? 0)}
        />
        <DetailMetric
          label="Estimated cost"
          value={formatCost(usage?.costUsd ?? 0)}
        />
        <DetailMetric
          label="Average latency"
          value={usage?.avgLatencyMs ? `${usage.avgLatencyMs} ms` : "—"}
        />
        <DetailMetric
          label="Error rate"
          value={usage ? `${usage.errorRate}%` : "—"}
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <article className="card-surface p-5">
          <h3 className="text-sm font-semibold text-text-primary">Capabilities</h3>
          <div className="mt-4 space-y-4">
            <div>
              <p className="text-xs font-medium text-text-muted">Input modalities</p>
              <div className="mt-2">
                <ChipList items={model.input_modalities} emptyLabel="Not reported" />
              </div>
            </div>
            <div>
              <p className="text-xs font-medium text-text-muted">Output modalities</p>
              <div className="mt-2">
                <ChipList items={model.output_modalities} emptyLabel="Not reported" />
              </div>
            </div>
            <div>
              <p className="text-xs font-medium text-text-muted">Supported parameters</p>
              <div className="mt-2">
                <ChipList
                  items={model.supported_parameters}
                  emptyLabel="No supported parameters listed"
                />
              </div>
            </div>
          </div>
        </article>

        <article className="card-surface p-5">
          <h3 className="text-sm font-semibold text-text-primary">Architecture</h3>
          <div className="mt-4 space-y-3">
            {architectureEntries.length > 0 ? (
              architectureEntries.map(([key, value]) => (
                <div key={key} className="flex items-start justify-between gap-4 text-sm">
                  <span className="text-text-muted">{key}</span>
                  <span className="text-right font-medium text-text-primary">
                    {Array.isArray(value) ? value.join(", ") : String(value)}
                  </span>
                </div>
              ))
            ) : (
              <p className="text-sm text-text-muted">Architecture details not available.</p>
            )}
            {model.canonical_slug ? (
              <div className="flex items-start justify-between gap-4 border-t border-border-subtle pt-3 text-sm">
                <span className="text-text-muted">Canonical slug</span>
                <span className="font-mono text-text-primary">{model.canonical_slug}</span>
              </div>
            ) : null}
            {model.expiration_date ? (
              <div className="flex items-start justify-between gap-4 text-sm">
                <span className="text-text-muted">Expiration</span>
                <span className="text-text-primary">{model.expiration_date}</span>
              </div>
            ) : null}
          </div>
        </article>
      </section>

      <section className="card-surface p-5">
        <h3 className="text-sm font-semibold text-text-primary">Provider availability</h3>
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-text-muted">Provider</dt>
            <dd className="mt-1 font-medium text-text-primary">{providerName}</dd>
          </div>
          <div>
            <dt className="text-text-muted">Provider ID</dt>
            <dd className="mt-1 font-mono text-text-primary">{providerId}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-text-muted">Base URL</dt>
            <dd className="mt-1 truncate font-mono text-text-primary" title={baseUrl}>
              {baseUrl}
            </dd>
          </div>
          <div>
            <dt className="text-text-muted">Catalog fetched</dt>
            <dd className="mt-1 text-text-primary">
              {new Date(fetchedAt).toLocaleString("en-US", {
                month: "short",
                day: "numeric",
                hour: "numeric",
                minute: "2-digit",
              })}
            </dd>
          </div>
          <div>
            <dt className="text-text-muted">Owned by</dt>
            <dd className="mt-1 text-text-primary">{model.owned_by ?? providerName}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
