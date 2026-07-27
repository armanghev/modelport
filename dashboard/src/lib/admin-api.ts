import type {
  PricingEntry,
  ProviderDetail,
  ProviderHealth,
  ProviderType,
  SettingsAppearance,
  SettingsTrackingOption,
} from "@/lib/dashboard-types";
import { backendUrl as backendBaseUrl } from "@/lib/backend-url";

export interface AdminProvider {
  id: string;
  slug: string;
  display_name: string;
  provider_type: ProviderType;
  base_url: string;
  enabled: boolean;
}

export interface AdminCredential {
  id: string;
  provider_id: string;
  provider_slug: string;
  display_name: string;
  key_hint: string;
  configured: boolean;
  is_default: boolean;
  enabled: boolean;
}

export interface AdminPricingOverride {
  id: string;
  provider_id: string;
  provider_slug: string | null;
  model: string;
  input_per_1m_usd: number;
  output_per_1m_usd: number;
  currency: string;
  enabled: boolean;
}

export interface AdminSettingsPayload {
  providers: AdminProvider[];
  provider_credentials: AdminCredential[];
  pricing_overrides: AdminPricingOverride[];
  settings: {
    tracking: {
      request_logging?: boolean;
      cost_tracking?: boolean;
      io_logging?: boolean;
      retention_days?: number;
    };
    appearance: {
      theme?: string;
      refresh_interval_seconds?: number;
    };
  };
}

export interface ProviderConfigRow {
  id: string;
  providerUuid: string;
  credentialId: string | null;
  slug: string;
  providerType: ProviderType;
  provider: string;
  credentialName: string;
  configured: boolean;
  maskedKey: string;
  fullKey: string;
  baseUrl: string;
  isDefault: boolean;
  enabled: boolean;
}

export interface ProviderPreset {
  slug: string;
  display_name: string;
  provider_type: ProviderType;
  base_url: string;
  protocol: "openai" | "anthropic";
}

export interface ProviderConfigDraft {
  slug: string;
  providerType: ProviderType;
  provider: string;
  credentialName: string;
  fullKey: string;
  baseUrl: string;
}

export interface ProviderHealthPayload {
  cards: ProviderHealth[];
  details: ProviderDetail[];
}

export interface ModelUsageSnippet {
  requestCount: number;
  tokenTotal: number;
  costUsd: number;
  avgLatencyMs: number;
  errorRate: number;
}

export type ModelMetadataSource = "openrouter" | "local" | "pricing" | "unknown";

export interface ProviderCatalogModel {
  id: string;
  display_name: string;
  owned_by: string | null;
  metadata_source: ModelMetadataSource;
  canonical_slug: string | null;
  description: string | null;
  context_length: number | null;
  architecture: Record<string, unknown>;
  input_modalities: string[];
  output_modalities: string[];
  supported_parameters: string[];
  input_per_1m_usd: number | null;
  output_per_1m_usd: number | null;
  top_provider: Record<string, unknown> | null;
  expiration_date: string | null;
  openrouter_id: string | null;
  usage: ModelUsageSnippet | null;
}

export interface ProviderCatalogEntry {
  provider_id: string;
  provider_uuid?: string;
  display_name: string;
  provider_type: ProviderType;
  base_url: string;
  status: "operational" | "degraded" | "offline";
  available_model_count: number;
  fetched_at: string;
  models: ProviderCatalogModel[];
}

export interface ProviderModelsPayload {
  totals: {
    live_model_count: number;
    provider_count: number;
    priced_model_count: number;
    used_model_count: number;
    metadata_synced_at: string | null;
  };
  providers: ProviderCatalogEntry[];
}

const refreshIntervals = ["15s", "30s", "60s", "5m"] as const;
const trackingLabelMap: Record<
  string,
  Pick<SettingsTrackingOption, "label" | "description">
> = {
  request_logging: {
    label: "Request logging",
    description: "Log details of all incoming requests.",
  },
  cost_tracking: {
    label: "Cost tracking",
    description: "Estimate and track provider costs for requests.",
  },
  io_logging: {
    label: "I/O logging",
    description: "Store request and response bodies for debugging.",
  },
  retention_days: {
    label: "Retention window",
    description: "Keep analytics data for the configured number of days.",
  },
};

function buildUrl(path: string) {
  return `${backendBaseUrl}${path}`;
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(buildUrl(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

function titleizeProvider(slug: string) {
  return slug
    .split(/[-_]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatRefreshInterval(seconds: number | undefined): string {
  if (!seconds) {
    return "30s";
  }

  if (seconds < 60) {
    return `${seconds}s`;
  }

  return `${Math.round(seconds / 60)}m`;
}

const PROVIDER_SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

/** Normalize for submit — trims edges and collapses dashes. */
export function normalizeProviderSlug(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** Light filter while typing — keeps partial slugs like `mock-` editable. */
export function sanitizeSlugInput(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9-]/g, "");
}

export function isValidProviderSlug(value: string): boolean {
  return PROVIDER_SLUG_PATTERN.test(value);
}

export function inferProviderType(
  slug: string,
  baseUrl: string,
): ProviderType {
  if (slug.includes("anthropic") || /anthropic/i.test(baseUrl)) {
    return "anthropic_compatible";
  }

  if (/localhost|127\.0\.0\.1/i.test(baseUrl)) {
    return "local_openai_compatible";
  }

  return "openai_compatible";
}

export function mapAdminSettingsToUi(payload: AdminSettingsPayload): {
  providerRows: ProviderConfigRow[];
  pricingTable: PricingEntry[];
  tracking: SettingsTrackingOption[];
  appearance: SettingsAppearance;
} {
  const providerByUuid = new Map(
    payload.providers.map((provider) => [provider.id, provider]),
  );

  const providersWithCredentials = new Set(
    payload.provider_credentials.map((credential) => credential.provider_id),
  );

  const credentialRows: ProviderConfigRow[] = payload.provider_credentials.map((credential) => {
    const provider = providerByUuid.get(credential.provider_id);
    const slug = credential.provider_slug || provider?.slug || "";
    return {
      id: credential.id,
      providerUuid: credential.provider_id,
      credentialId: credential.id,
      slug,
      providerType:
        provider?.provider_type ?? inferProviderType(slug, provider?.base_url ?? ""),
      provider: provider?.display_name ?? titleizeProvider(slug),
      credentialName: credential.display_name,
      configured: credential.configured,
      maskedKey: credential.key_hint,
      fullKey: "",
      baseUrl: provider?.base_url ?? "",
      isDefault: credential.is_default,
      enabled: credential.enabled,
    };
  });

  const providerOnlyRows: ProviderConfigRow[] = payload.providers
    .filter((provider) => !providersWithCredentials.has(provider.id))
    .map((provider) => ({
      id: provider.id,
      providerUuid: provider.id,
      credentialId: null,
      slug: provider.slug,
      providerType: provider.provider_type,
      provider: provider.display_name,
      credentialName: "No API key",
      configured: false,
      maskedKey: "Not configured",
      fullKey: "",
      baseUrl: provider.base_url,
      isDefault: true,
      enabled: provider.enabled,
    }));

  return {
    providerRows: [...credentialRows, ...providerOnlyRows],
    pricingTable: payload.pricing_overrides.map((entry) => {
      const provider = providerByUuid.get(entry.provider_id);
      const slug = entry.provider_slug || provider?.slug || entry.provider_id;
      return {
        provider: provider?.display_name ?? titleizeProvider(slug),
        model: entry.model,
        inputPer1kUsd: entry.input_per_1m_usd / 1000,
        outputPer1kUsd: entry.output_per_1m_usd / 1000,
      };
    }),
    tracking: Object.entries(payload.settings.tracking).map(([key, value]) => ({
      id: key,
      label: trackingLabelMap[key]?.label ?? titleizeProvider(key),
      description:
        trackingLabelMap[key]?.description ??
        "Configuration controlled by the backend.",
      enabled: typeof value === "boolean" ? value : Number(value ?? 0) > 0,
    })),
    appearance: {
      theme: payload.settings.appearance.theme ?? "system",
      themes: ["light", "dark", "system"],
      autoRefreshInterval: formatRefreshInterval(
        payload.settings.appearance.refresh_interval_seconds,
      ),
      autoRefreshIntervals: [...refreshIntervals],
    },
  };
}

export async function fetchAdminSettings() {
  return fetchJson<AdminSettingsPayload>("/admin/settings");
}

export async function fetchProviderPresets() {
  return fetchJson<ProviderPreset[]>("/admin/provider-presets");
}

export async function fetchProviderHealth() {
  return fetchJson<ProviderHealthPayload>("/admin/providers/health");
}

export async function fetchProviderModels() {
  return fetchJson<ProviderModelsPayload>("/admin/providers/models");
}

export async function revealCredentialSecret(credentialId: string) {
  return fetchJson<{ id: string; api_key: string | null }>(
    `/admin/provider-credentials/${credentialId}/secret`,
  );
}

export async function createProvider(payload: {
  slug: string;
  display_name: string;
  provider_type: ProviderType;
  base_url: string;
  api_key?: string;
  credential_name?: string;
}) {
  return fetchJson<AdminProvider>("/admin/providers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateProvider(
  providerUuid: string,
  payload: Partial<{
    display_name: string;
    provider_type: ProviderType;
    base_url: string;
    enabled: boolean;
  }>,
) {
  return fetchJson<AdminProvider>(`/admin/providers/${providerUuid}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function createProviderCredential(payload: {
  provider_id: string;
  display_name: string;
  api_key: string;
  is_default?: boolean;
  enabled?: boolean;
}) {
  return fetchJson<AdminCredential>("/admin/provider-credentials", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateProviderCredential(
  credentialId: string,
  payload: Partial<{
    display_name: string;
    api_key: string;
    is_default: boolean;
    enabled: boolean;
  }>,
) {
  return fetchJson<AdminCredential>(`/admin/provider-credentials/${credentialId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteProviderCredential(credentialId: string) {
  return fetchJson<void>(`/admin/provider-credentials/${credentialId}`, {
    method: "DELETE",
  });
}

export async function deleteProvider(providerUuid: string) {
  return fetchJson<void>(`/admin/providers/${providerUuid}`, {
    method: "DELETE",
  });
}

export async function patchTrackingSettings(payload: {
  request_logging?: boolean;
  cost_tracking?: boolean;
  io_logging?: boolean;
  retention_days?: number;
}) {
  return fetchJson<AdminSettingsPayload["settings"]["tracking"]>("/admin/settings/tracking", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function updateAppearanceSettings(payload: {
  theme: string;
  refresh_interval_seconds: number;
}) {
  return fetchJson("/admin/settings/appearance", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
