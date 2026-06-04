"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useTheme } from "next-themes";

import {
  CheckIcon,
  CopyIcon,
  DesktopIcon,
  DotsThreeIcon,
  EyeIcon,
  EyeSlashIcon,
  MoonIcon,
  PencilSimpleIcon,
  SunDimIcon,
} from "@phosphor-icons/react";

import {
  AddProviderModal,
  EditProviderModal,
} from "@/components/dashboard/settings/add-provider-modal";
import { ProviderIcon } from "@/components/brand/render-provider-icon";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  createProvider,
  createProviderCredential,
  fetchAdminSettings,
  mapAdminSettingsToUi,
  revealCredentialSecret,
  slugifyProviderId,
  updateAppearanceSettings,
  updateProvider,
  updateProviderCredential,
  updateTrackingSettings,
  type AdminSettingsPayload,
  type ProviderConfigDraft,
  type ProviderConfigRow,
} from "@/lib/admin-api";

const themeOptions = [
  { value: "light", label: "Light", icon: SunDimIcon },
  { value: "dark", label: "Dark", icon: MoonIcon },
  { value: "system", label: "System", icon: DesktopIcon },
] as const;

type ThemeOption = (typeof themeOptions)[number];

function SettingsCard({
  title,
  description,
  children,
  className = "",
}: {
  title: string;
  description: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <article className={`card-surface rounded-2xl border border-border-subtle p-5 ${className}`}>
      <div className="space-y-1">
        <h2 className="text-xl font-semibold text-text-primary">{title}</h2>
        <p className="text-sm text-text-secondary">{description}</p>
      </div>
      <div className="mt-5">{children}</div>
    </article>
  );
}

function ToggleRow({
  label,
  description,
  enabled,
  onCheckedChange,
}: {
  label: string;
  description: string;
  enabled: boolean;
  onCheckedChange: (checked: boolean) => void;
}) {
  return (
    <div className="flex items-start gap-3">
      <Switch checked={enabled} onCheckedChange={onCheckedChange} className="mt-0.5" />
      <div className="space-y-0.5">
        <p className="text-sm font-medium text-text-primary">{label}</p>
        <p className="text-sm text-text-secondary">{description}</p>
      </div>
    </div>
  );
}

function formatTrackingPayload(
  tracking: Array<{ id: string; enabled: boolean }>,
) {
  return {
    request_logging:
      tracking.find((item) => item.id === "request_logging")?.enabled ?? true,
    cost_tracking:
      tracking.find((item) => item.id === "cost_tracking")?.enabled ?? true,
    io_logging:
      tracking.find((item) => item.id === "io_logging")?.enabled ?? false,
    retention_days:
      tracking.find((item) => item.id === "retention_days")?.enabled ? 30 : 0,
  };
}

function parseRefreshInterval(value: string) {
  if (value.endsWith("m")) {
    return Number.parseInt(value, 10) * 60;
  }
  return Number.parseInt(value, 10);
}

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const [settingsPayload, setSettingsPayload] = useState<AdminSettingsPayload | null>(null);
  const [apiKeys, setApiKeys] = useState<ProviderConfigRow[]>([]);
  const [pricingTable, setPricingTable] = useState<Array<{ provider: string; model: string; inputPer1kUsd: number; outputPer1kUsd: number }>>([]);
  const [tracking, setTracking] = useState<
    Array<{ id: string; label: string; description: string; enabled: boolean }>
  >([]);
  const [visibleKeys, setVisibleKeys] = useState<Record<string, boolean>>({});
  const [copiedProvider, setCopiedProvider] = useState<string | null>(null);
  const [editingProvider, setEditingProvider] = useState<ProviderConfigRow | null>(null);
  const [openMenuProvider, setOpenMenuProvider] = useState<string | null>(null);
  const [autoRefreshInterval, setAutoRefreshInterval] = useState("30s");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const selectedTheme = theme ?? "system";
  const selectedThemeOption =
    themeOptions.find((option) => option.value === selectedTheme) ?? themeOptions[2];

  const pricingPreview = useMemo(() => pricingTable.slice(0, 4), [pricingTable]);
  const apiKeyLookup = useMemo(
    () => Object.fromEntries(apiKeys.map((item) => [item.id, item])),
    [apiKeys],
  );

  const loadSettings = useCallback(async () => {
    const payload = await fetchAdminSettings();
    const mapped = mapAdminSettingsToUi(payload);
    setSettingsPayload(payload);
    setApiKeys(mapped.providerRows);
    setPricingTable(mapped.pricingTable);
    setTracking(mapped.tracking);
    setAutoRefreshInterval(mapped.appearance.autoRefreshInterval);
    if (mapped.appearance.theme) {
      setTheme(mapped.appearance.theme);
    }
  }, [setTheme]);

  useEffect(() => {
    let active = true;

    void (async () => {
      try {
        await loadSettings();
        if (active) {
          setErrorMessage(null);
        }
      } catch (error) {
        if (active) {
          setErrorMessage(
            error instanceof Error ? error.message : "Failed to load admin settings.",
          );
        }
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    })();

    return () => {
      active = false;
    };
  }, [loadSettings]);

  const ensureSecretLoaded = async (credentialId: string) => {
    const current = apiKeyLookup[credentialId];
    if (!current || current.fullKey || !current.configured) {
      return current;
    }

    const secret = await revealCredentialSecret(credentialId);
    const nextRow = {
      ...current,
      fullKey: secret.api_key ?? "",
    };
    setApiKeys((existing) =>
      existing.map((item) => (item.id === credentialId ? nextRow : item)),
    );
    return nextRow;
  };

  const toggleKeyVisibility = async (credentialId: string) => {
    if (!visibleKeys[credentialId]) {
      try {
        await ensureSecretLoaded(credentialId);
      } catch (error) {
        setErrorMessage(
          error instanceof Error ? error.message : "Failed to reveal provider secret.",
        );
        return;
      }
    }

    setVisibleKeys((current) => ({
      ...current,
      [credentialId]: !current[credentialId],
    }));
  };

  const copyApiKey = async (credentialId: string) => {
    const row = await ensureSecretLoaded(credentialId);
    if (!row?.fullKey) {
      return;
    }

    await navigator.clipboard.writeText(row.fullKey);
    setCopiedProvider(credentialId);
    window.setTimeout(() => {
      setCopiedProvider((current) => (current === credentialId ? null : current));
    }, 1500);
  };

  const getDisplayedKeyValue = (credentialId: string, configured: boolean) => {
    if (!configured) {
      return "Not configured";
    }

    const source = apiKeyLookup[credentialId];
    if (!source) {
      return "";
    }

    return visibleKeys[credentialId] ? source.fullKey : source.maskedKey;
  };

  const handleAddProvider = async (draft: ProviderConfigDraft) => {
    const providerId = slugifyProviderId(draft.providerId || draft.provider);
    const providerExists = settingsPayload?.providers.some(
      (provider) => provider.id === providerId,
    );

    try {
      if (!providerExists) {
        await createProvider({
          id: providerId,
          display_name: draft.provider,
          provider_type: draft.providerType,
          base_url: draft.baseUrl,
        });
      }

      await createProviderCredential({
        provider_id: providerId,
        display_name: draft.credentialName,
        source: draft.fullKey ? "database" : "env",
        api_key: draft.fullKey || undefined,
        api_key_env: draft.fullKey ? undefined : draft.envVar || undefined,
        is_default: true,
        enabled: true,
      });

      await loadSettings();
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to add provider configuration.",
      );
    }
  };

  const handleEditProvider = async (draft: ProviderConfigDraft) => {
    if (!editingProvider) {
      return;
    }

    try {
      await updateProvider(editingProvider.providerId, {
        display_name: draft.provider,
        base_url: draft.baseUrl,
      });

      const credentialPatch: Record<string, string | boolean> = {
        display_name: draft.credentialName,
        enabled: true,
      };

      if (
        draft.fullKey.trim() &&
        draft.fullKey.trim() !== editingProvider.fullKey.trim()
      ) {
        credentialPatch.api_key = draft.fullKey.trim();
      } else if (
        editingProvider.source === "env" &&
        draft.envVar.trim() !== editingProvider.envVar.trim()
      ) {
        credentialPatch.api_key_env = draft.envVar.trim();
      }

      await updateProviderCredential(editingProvider.id, credentialPatch);
      await loadSettings();
      setEditingProvider(null);
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to update provider configuration.",
      );
    }
  };

  const saveTracking = async () => {
    try {
      await updateTrackingSettings(formatTrackingPayload(tracking));
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to save tracking settings.",
      );
    }
  };

  const saveAppearance = async () => {
    try {
      await updateAppearanceSettings({
        theme: selectedTheme,
        refresh_interval_seconds: parseRefreshInterval(autoRefreshInterval) || 30,
      });
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to save appearance settings.",
      );
    }
  };

  if (isLoading) {
    return <div className="text-sm text-text-secondary">Loading provider configuration...</div>;
  }

  return (
    <div className="space-y-4">
      {errorMessage ? (
        <div className="rounded-xl border border-accent-red/20 bg-accent-red-bg px-4 py-3 text-sm text-accent-red">
          {errorMessage}
        </div>
      ) : null}
      <section className="grid gap-4 xl:grid-cols-5">
        <SettingsCard
          title="API keys"
          description="Manage API keys for your providers."
          className="relative z-20 xl:col-span-3"
        >
          <div className="overflow-visible rounded-xl border border-border-subtle bg-bg-card">
            {apiKeys.map((apiKey, index) => (
              <div
                key={apiKey.id}
                className={`grid items-center gap-1 px-4 py-3 sm:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)_auto_auto] ${
                  index > 0 ? "border-t border-border-subtle" : ""
                }`}
              >
                <div className="flex min-w-0 items-center gap-3">
                  <ProviderIcon provider={apiKey.provider} size={20} />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-text-primary">
                      {apiKey.credentialName}
                    </p>
                    <p className="truncate text-xs text-text-secondary">
                      {apiKey.provider}
                      {apiKey.envVar ? ` · ${apiKey.envVar}` : ` · ${apiKey.source}`}
                    </p>
                  </div>
                </div>
                <p className="text-sm text-text-secondary">
                  {getDisplayedKeyValue(apiKey.id, apiKey.configured)}
                </p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 rounded-lg border-border-default px-3 text-sm"
                  onClick={() => void toggleKeyVisibility(apiKey.id)}
                >
                  {visibleKeys[apiKey.id] ? <EyeSlashIcon /> : <EyeIcon />}
                </Button>
                <div className="relative z-30">
                  <Popover
                    open={openMenuProvider === apiKey.id}
                    onOpenChange={(open) =>
                      setOpenMenuProvider(open ? apiKey.id : null)
                    }
                  >
                    <PopoverTrigger asChild>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        className="h-8 w-8 rounded-lg text-text-secondary"
                      >
                        <DotsThreeIcon size={18} weight="bold" />
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent align="end" className="w-auto min-w-max">
                      <button
                        type="button"
                        onClick={async () => {
                          setOpenMenuProvider(null);
                          try {
                            const row = await ensureSecretLoaded(apiKey.id);
                            if (row) {
                              setEditingProvider(row);
                            }
                          } catch (error) {
                            setErrorMessage(
                              error instanceof Error
                                ? error.message
                                : "Failed to load credential secret.",
                            );
                          }
                        }}
                        className="flex w-full items-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-left text-sm text-text-primary hover:bg-bg-card-muted"
                      >
                        <PencilSimpleIcon size={14} />
                        Edit provider
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setOpenMenuProvider(null);
                          void copyApiKey(apiKey.id);
                        }}
                        className="flex w-full items-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-left text-sm text-text-primary hover:bg-bg-card-muted"
                      >
                        {copiedProvider === apiKey.id ? (
                          <CheckIcon size={14} />
                        ) : (
                          <CopyIcon size={14} />
                        )}
                        {copiedProvider === apiKey.id ? "Copied API key" : "Copy API key"}
                      </button>
                    </PopoverContent>
                  </Popover>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4">
            <AddProviderModal onAddProvider={(provider) => void handleAddProvider(provider)} />
          </div>
          <EditProviderModal
            open={editingProvider !== null}
            provider={editingProvider}
            onOpenChange={(open) => {
              if (!open) {
                setEditingProvider(null);
              }
            }}
            onEditProvider={(nextProvider) => void handleEditProvider(nextProvider)}
          />
        </SettingsCard>

        <SettingsCard
          title="Logging and tracking"
          description="Control what data is logged and tracked."
          className="xl:col-span-2"
        >
          <div className="space-y-5">
            {tracking.map((item) => (
              <ToggleRow
                key={item.id}
                label={item.label}
                description={item.description}
                enabled={item.enabled}
                onCheckedChange={(checked) =>
                  setTracking((current) =>
                    current.map((entry) =>
                      entry.id === item.id ? { ...entry, enabled: checked } : entry,
                    ),
                  )
                }
              />
            ))}
          </div>

          <div className="mt-6 flex justify-end">
            <Button
              type="button"
              size="lg"
              className="h-10 rounded-lg px-5 text-sm"
              onClick={() => void saveTracking()}
            >
              Save
            </Button>
          </div>
        </SettingsCard>
      </section>

      <SettingsCard
        title="Pricing table"
        description="Estimated pricing used when provider billing data is unavailable."
      >
        <div className="overflow-hidden rounded-xl border border-border-subtle">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="bg-bg-card-muted text-xs text-text-secondary">
                <th className="px-4 py-3 font-medium">Provider</th>
                <th className="px-4 py-3 font-medium">Model</th>
                <th className="px-4 py-3 font-medium">Input / 1M</th>
                <th className="px-4 py-3 font-medium">Output / 1M</th>
              </tr>
            </thead>
            <tbody>
              {pricingPreview.map((entry) => (
                <tr
                  key={`${entry.provider}-${entry.model}`}
                  className="border-t border-border-subtle text-sm text-text-secondary"
                >
                  <td className="px-4 py-3 text-text-primary">{entry.provider}</td>
                  <td className="px-4 py-3">{entry.model}</td>
                  <td className="px-4 py-3">${(entry.inputPer1kUsd * 1000).toFixed(2)}</td>
                  <td className="px-4 py-3">${(entry.outputPer1kUsd * 1000).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SettingsCard>

      <SettingsCard
        title="Appearance & preferences"
        description="Customize the dashboard experience."
      >
        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] md:items-end">
          <div className="space-y-2">
            <p className="text-sm font-medium text-text-primary">Theme</p>
            <Select
              value={selectedTheme}
              onValueChange={(value) => setTheme(value as ThemeOption["value"])}
            >
              <SelectTrigger className="h-11 rounded-lg text-sm text-text-primary">
                <div className="flex items-center gap-2">
                  <selectedThemeOption.icon size={16} className="text-text-secondary" />
                  <SelectValue>{selectedThemeOption.label}</SelectValue>
                </div>
              </SelectTrigger>
              <SelectContent className="rounded-lg p-1">
                {themeOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value} className="rounded-md text-sm">
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium text-text-primary">Auto refresh interval</p>
            <Select value={autoRefreshInterval} onValueChange={setAutoRefreshInterval}>
              <SelectTrigger className="h-11 rounded-lg text-sm text-text-primary">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="rounded-lg p-1">
                {["15s", "30s", "60s", "5m"].map((option) => (
                  <SelectItem key={option} value={option} className="rounded-md text-sm">
                    {option}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex md:justify-end">
            <Button
              type="button"
              size="lg"
              className="h-10 rounded-lg px-5 text-sm"
              onClick={() => void saveAppearance()}
            >
              Save
            </Button>
          </div>
        </div>
      </SettingsCard>
    </div>
  );
}
