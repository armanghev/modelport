"use client";

import { useMemo, useState } from "react";
import { useTheme } from "next-themes";

import {
  CheckIcon,
  CopyIcon,
  DesktopIcon,
  DotsThreeIcon,
  EyeIcon,
  EyeSlashIcon,
  MoonIcon,
  SunDimIcon,
  XIcon,
} from "@phosphor-icons/react";

import { ProviderIcon } from "@/components/brand/render-provider-icon";
import { AddProviderModal } from "@/components/dashboard/settings/add-provider-modal";
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
import { dashboardMockData } from "@/lib/mock-dashboard-data";

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

export default function SettingsPage() {
  const { settings } = dashboardMockData;
  const { theme, setTheme } = useTheme();
  const [apiKeys, setApiKeys] = useState(settings.apiKeys);
  const [visibleKeys, setVisibleKeys] = useState<Record<string, boolean>>({});
  const [copiedProvider, setCopiedProvider] = useState<string | null>(null);
  const [tracking, setTracking] = useState(settings.tracking);
  const [autoRefreshInterval, setAutoRefreshInterval] = useState(
    settings.appearance.autoRefreshInterval,
  );

  const pricingPreview = useMemo(() => settings.pricingTable.slice(0, 4), [settings.pricingTable]);
  const apiKeyLookup = useMemo(
    () => Object.fromEntries(settings.apiKeys.map((item) => [item.provider, item])),
    [settings.apiKeys],
  );
  const selectedTheme = theme ?? "system";
  const selectedThemeOption =
    themeOptions.find((option) => option.value === selectedTheme) ?? themeOptions[2];

  const toggleKeyVisibility = (provider: string) => {
    setVisibleKeys((current) => ({
      ...current,
      [provider]: !current[provider],
    }));
  };

  const toggleProviderConfigured = (provider: string) => {
    setApiKeys((current) =>
      current.map((item) =>
        item.provider === provider
          ? {
              ...item,
              configured: !item.configured,
            }
          : item,
      ),
    );
  };

  const copyEnvVar = async (provider: string, envVar: string) => {
    await navigator.clipboard.writeText(envVar);
    setCopiedProvider(provider);
    window.setTimeout(() => {
      setCopiedProvider((current) => (current === provider ? null : current));
    }, 1500);
  };

  const getDisplayedKeyValue = (provider: string, configured: boolean) => {
    if (!configured) {
      return "Not configured";
    }

    const source = apiKeyLookup[provider];
    if (!source) {
      return "";
    }

    return visibleKeys[provider] ? source.fullKey : source.maskedKey;
  };

  return (
    <div className="space-y-4">
      <section className="grid gap-4 xl:grid-cols-5">
        <SettingsCard
          title="API keys"
          description="Manage API keys for your providers."
          className="relative z-20 xl:col-span-3"
        >
          <div className="overflow-visible rounded-xl border border-border-subtle bg-bg-card">
            {apiKeys.map((apiKey, index) => (
              <div
                key={apiKey.provider}
                className={`grid items-center gap-1 px-4 py-3 sm:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)_auto_auto] ${
                  index > 0 ? "border-t border-border-subtle" : ""
                }`}
              >
                <div className="flex min-w-0 items-center gap-3">
                  <ProviderIcon provider={apiKey.provider} size={20} />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-text-primary">
                      {apiKey.envVar}
                    </p>
                    <p className="truncate text-xs text-text-secondary">{apiKey.provider}</p>
                  </div>
                </div>
                <p className="text-sm text-text-secondary">
                  {getDisplayedKeyValue(apiKey.provider, apiKey.configured)}
                </p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 rounded-lg border-border-default px-3 text-sm"
                  onClick={() => toggleKeyVisibility(apiKey.provider)}
                >
                  {visibleKeys[apiKey.provider] ? <EyeSlashIcon /> : <EyeIcon />}
                </Button>
                <div className="relative z-30">
                  <Popover>
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
                        onClick={() => copyEnvVar(apiKey.provider, apiKey.fullKey)}
                        className="flex w-full items-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-left text-sm text-text-primary hover:bg-bg-card-muted"
                      >
                        {copiedProvider === apiKey.provider ? (
                          <CheckIcon size={14} />
                        ) : (
                          <CopyIcon size={14} />
                        )}
                        {copiedProvider === apiKey.provider ? "Copied env var" : "Copy env var"}
                      </button>
                      <button
                        type="button"
                        onClick={() => toggleProviderConfigured(apiKey.provider)}
                        className="flex w-full items-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-left text-sm text-text-primary hover:bg-bg-card-muted"
                      >
                        <XIcon size={14} />
                        {apiKey.configured ? "Mark unconfigured" : "Mark configured"}
                      </button>
                    </PopoverContent>
                  </Popover>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4">
            <AddProviderModal
              onAddProvider={(provider) => {
                setApiKeys((current) => [...current, provider]);
              }}
            />
          </div>
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
            <Button type="button" size="lg" className="h-10 rounded-lg px-5 text-sm">
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
                {settings.appearance.autoRefreshIntervals.map((option) => (
                  <SelectItem key={option} value={option} className="rounded-md text-sm">
                    {option}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex md:justify-end">
            <Button type="button" size="lg" className="h-10 rounded-lg px-5 text-sm">
              Save
            </Button>
          </div>
        </div>
      </SettingsCard>
    </div>
  );
}
