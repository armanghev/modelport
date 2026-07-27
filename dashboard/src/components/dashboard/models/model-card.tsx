"use client";

import Link from "next/link";

import { ProviderIcon } from "@/components/brand/render-provider-icon";
import {
  buildModelDetailPath,
  formatContextLength,
  formatCost,
  formatInteger,
  formatPricePerMillion,
  type ModelDirectoryRow,
} from "@/lib/models-directory";

function metadataSourceLabel(source: string): string {
  if (source === "openrouter") {
    return "OpenRouter";
  }
  if (source === "pricing") {
    return "Local pricing";
  }
  if (source === "local") {
    return "Local";
  }
  return "Provider";
}

function modelDescriptionPreview(description: string | null): string {
  const trimmed = description?.trim();
  return trimmed ? trimmed : "No description available.";
}

export function ModelCard({ row }: { row: ModelDirectoryRow }) {
  const { model, providerName, providerId } = row;
  const detailHref = buildModelDetailPath(providerId, model.id);

  return (
    <Link
      href={detailHref}
      className="card-surface flex h-full flex-col p-5 transition-colors hover:bg-bg-card-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-default"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center text-text-primary">
              <ProviderIcon provider={providerName} />
            </span>
            <p className="truncate text-sm font-semibold text-text-primary">
              {model.display_name}
            </p>
          </div>
          <p className="mt-1 truncate font-mono text-xs text-text-muted" title={model.id}>
            {model.id}
          </p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-xs text-text-muted">Context</p>
          <p className="mt-0.5 font-medium text-text-primary">
            {formatContextLength(model.context_length)}
          </p>
        </div>
        <div>
          <p className="text-xs text-text-muted">Input / Output</p>
          <p className="mt-0.5 font-medium text-text-primary">
            {formatPricePerMillion(model.input_per_1m_usd)} /{" "}
            {formatPricePerMillion(model.output_per_1m_usd)}
          </p>
        </div>
      </div>

      <div className="mt-3 min-h-18 flex-1">
        <p
          className={`line-clamp-3 text-xs leading-relaxed ${
            model.description?.trim()
              ? "text-text-secondary"
              : "text-text-muted"
          }`}
        >
          {modelDescriptionPreview(model.description)}
        </p>
      </div>

      <div className="mt-4 shrink-0 border-t border-border-subtle pt-3 text-xs text-text-secondary">
        {model.usage && model.usage.requestCount > 0 ? (
          <p>
            {formatInteger(model.usage.requestCount)} requests ·{" "}
            {formatInteger(model.usage.tokenTotal)} tokens · {formatCost(model.usage.costUsd)}
          </p>
        ) : (
          <p className="text-text-muted">No tracked usage yet</p>
        )}
      </div>

      <p className="mt-4 truncate text-xs text-text-muted">{providerName}</p>
    </Link>
  );
}
