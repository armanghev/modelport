import type { ProviderCatalogEntry, ProviderCatalogModel } from "@/lib/admin-api";

export type MetadataSource = "openrouter" | "local" | "pricing" | "unknown";

export interface ModelDirectoryRow {
  key: string;
  providerId: string;
  providerName: string;
  providerType: ProviderCatalogEntry["provider_type"];
  baseUrl: string;
  fetchedAt: string;
  model: ProviderCatalogModel;
}

export type ModelSortKey =
  | "name"
  | "provider"
  | "context"
  | "price"
  | "usage"
  | "fetched";

export type ContextFilter = "128k" | "200k" | "1m";
export type PriceTierFilter = "free" | "paid";
export type UsageFilter = "used" | "unused";

export interface ModelDirectoryFilters {
  search: string;
  providers: string[];
  modalities: string[];
  capabilities: string[];
  priceTiers: PriceTierFilter[];
  usage: UsageFilter[];
  contexts: ContextFilter[];
}

export const DEFAULT_MODEL_FILTERS: ModelDirectoryFilters = {
  search: "",
  providers: [],
  modalities: [],
  capabilities: [],
  priceTiers: [],
  usage: [],
  contexts: [],
};

export function encodeModelRouteSegment(value: string): string {
  return encodeURIComponent(value);
}

export function decodeModelRouteSegment(value: string): string {
  return decodeURIComponent(value);
}

export function buildModelDetailPath(providerId: string, modelId: string): string {
  return `/models/${encodeModelRouteSegment(providerId)}/${encodeModelRouteSegment(modelId)}`;
}

export function flattenProviderModels(
  providers: ProviderCatalogEntry[],
): ModelDirectoryRow[] {
  return providers.flatMap((provider) =>
    provider.models.map((model) => ({
      key: `${provider.provider_id}:${model.id}`,
      providerId: provider.provider_id,
      providerName: provider.display_name,
      providerType: provider.provider_type,
      baseUrl: provider.base_url,
      fetchedAt: provider.fetched_at,
      model,
    })),
  );
}

export function formatContextLength(value: number | null | undefined): string {
  if (value == null || value <= 0) {
    return "Unknown";
  }
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(value % 1_000_000 === 0 ? 0 : 1)}M`;
  }
  if (value >= 1_000) {
    return `${Math.round(value / 1_000)}K`;
  }
  return value.toLocaleString("en-US");
}

export function isKnownPricePerMillion(
  value: number | null | undefined,
): value is number {
  return value != null && value >= 0;
}

export function formatPricePerMillion(value: number | null | undefined): string {
  if (!isKnownPricePerMillion(value)) {
    return "—";
  }
  if (value === 0) {
    return "Free";
  }
  if (value < 0.01) {
    return `$${value.toFixed(4)}/M`;
  }
  if (value < 1) {
    return `$${value.toFixed(3)}/M`;
  }
  return `$${value.toFixed(2)}/M`;
}

export function formatInteger(value: number): string {
  return value.toLocaleString("en-US");
}

export function formatCost(value: number): string {
  return `$${value.toFixed(2)}`;
}

export function modelHasPricing(model: ProviderCatalogModel): boolean {
  return (
    isKnownPricePerMillion(model.input_per_1m_usd) ||
    isKnownPricePerMillion(model.output_per_1m_usd)
  );
}

export function modelIsFree(model: ProviderCatalogModel): boolean {
  return (
    model.input_per_1m_usd === 0 &&
    (model.output_per_1m_usd == null || model.output_per_1m_usd === 0)
  );
}

function matchesContextBucket(
  contextLength: number | null | undefined,
  filter: ContextFilter,
): boolean {
  if (contextLength == null) {
    return false;
  }
  if (filter === "1m") {
    return contextLength >= 1_000_000;
  }
  if (filter === "200k") {
    return contextLength >= 200_000 && contextLength < 1_000_000;
  }
  return contextLength > 0 && contextLength < 200_000;
}

function matchesAnyContext(
  contextLength: number | null | undefined,
  contexts: ContextFilter[],
): boolean {
  if (contexts.length === 0) {
    return true;
  }
  return contexts.some((filter) => matchesContextBucket(contextLength, filter));
}

export function filterModelRows(
  rows: ModelDirectoryRow[],
  filters: ModelDirectoryFilters,
): ModelDirectoryRow[] {
  const search = filters.search.trim().toLowerCase();

  return rows.filter((row) => {
    const model = row.model;

    if (filters.providers.length > 0 && !filters.providers.includes(row.providerId)) {
      return false;
    }

    if (filters.modalities.length > 0) {
      const modalities = [
        ...model.input_modalities,
        ...model.output_modalities,
      ].map((value) => value.toLowerCase());
      const matchesModality = filters.modalities.some((modality) =>
        modalities.includes(modality.toLowerCase()),
      );
      if (!matchesModality) {
        return false;
      }
    }

    if (filters.capabilities.length > 0) {
      const capabilities = model.supported_parameters.map((value) =>
        value.toLowerCase(),
      );
      const matchesCapability = filters.capabilities.some((capability) =>
        capabilities.includes(capability.toLowerCase()),
      );
      if (!matchesCapability) {
        return false;
      }
    }

    if (filters.priceTiers.length > 0) {
      const matchesPriceTier = filters.priceTiers.some((tier) =>
        tier === "free" ? modelIsFree(model) : modelHasPricing(model),
      );
      if (!matchesPriceTier) {
        return false;
      }
    }

    if (filters.usage.length > 0) {
      const isUsed = Boolean(model.usage && model.usage.requestCount > 0);
      const matchesUsage =
        (filters.usage.includes("used") && isUsed) ||
        (filters.usage.includes("unused") && !isUsed);
      if (!matchesUsage) {
        return false;
      }
    }

    if (!matchesAnyContext(model.context_length, filters.contexts)) {
      return false;
    }

    if (!search) {
      return true;
    }

    const haystack = [
      model.id,
      model.display_name,
      row.providerName,
      row.providerId,
      model.description,
      model.canonical_slug,
      model.metadata_source,
      ...model.input_modalities,
      ...model.output_modalities,
      ...model.supported_parameters,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return haystack.includes(search);
  });
}

export function sortModelRows(
  rows: ModelDirectoryRow[],
  sortKey: ModelSortKey,
): ModelDirectoryRow[] {
  const sorted = [...rows];

  sorted.sort((left, right) => {
    switch (sortKey) {
      case "provider":
        return (
          left.providerName.localeCompare(right.providerName) ||
          left.model.display_name.localeCompare(right.model.display_name)
        );
      case "context":
        return (
          (right.model.context_length ?? 0) - (left.model.context_length ?? 0)
        );
      case "price": {
        const leftPrice = isKnownPricePerMillion(left.model.input_per_1m_usd)
          ? left.model.input_per_1m_usd
          : Number.POSITIVE_INFINITY;
        const rightPrice = isKnownPricePerMillion(right.model.input_per_1m_usd)
          ? right.model.input_per_1m_usd
          : Number.POSITIVE_INFINITY;
        return leftPrice - rightPrice;
      }
      case "usage":
        return (
          (right.model.usage?.requestCount ?? 0) -
          (left.model.usage?.requestCount ?? 0)
        );
      case "fetched":
        return right.fetchedAt.localeCompare(left.fetchedAt);
      case "name":
      default:
        return left.model.display_name.localeCompare(right.model.display_name);
    }
  });

  return sorted;
}

export function collectFilterOptions(rows: ModelDirectoryRow[]) {
  const providers = new Map<string, string>();
  const modalities = new Set<string>();
  const capabilities = new Set<string>();

  for (const row of rows) {
    providers.set(row.providerId, row.providerName);
    for (const modality of [...row.model.input_modalities, ...row.model.output_modalities]) {
      modalities.add(modality);
    }
    for (const capability of row.model.supported_parameters) {
      capabilities.add(capability);
    }
  }

  return {
    providers: [...providers.entries()]
      .map(([value, label]) => ({ value, label }))
      .sort((a, b) => a.label.localeCompare(b.label)),
    modalities: [...modalities].sort((a, b) => a.localeCompare(b)),
    capabilities: [...capabilities].sort((a, b) => a.localeCompare(b)),
  };
}
