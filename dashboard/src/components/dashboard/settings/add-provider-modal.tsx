"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { PlusIcon, TrashIcon, XIcon } from "@phosphor-icons/react";

import { ProviderIcon } from "@/components/brand/render-provider-icon";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";
import type { ApiKeyStatus } from "@/lib/mock-dashboard-data";

interface AddProviderModalProps {
  onAddProvider: (provider: ApiKeyStatus) => void;
}

interface HeaderEntry {
  id: string;
  key: string;
  value: string;
}

const PROVIDER_PRESETS = [
  {
    provider: "OpenAI",
    envVar: "OPENAI_API_KEY",
    maskedKey: "sk-************************",
    fullKey: "sk-proj-Q4mRt8Lp2Xn7Va1Ke9Hs5Wd3Pf6CyZjU",
    baseUrl: "https://api.openai.com/v1",
  },
  {
    provider: "Anthropic",
    envVar: "ANTHROPIC_API_KEY",
    maskedKey: "sk-ant-********************",
    fullKey: "sk-ant-api03-R7mQ2pLx9Nk4Ts8Hv1Wd6Cy5ZjFa",
    baseUrl: "https://api.anthropic.com/v1/",
  },
  {
    provider: "Gemini",
    envVar: "GEMINI_API_KEY",
    maskedKey: "AIza**********************",
    fullKey: "AIzaSyC7mQ2pLv9Nx4Ta8Hr1Wd6Cy5ZjFk3UsB",
    baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai/",
  },
  {
    provider: "OpenRouter",
    envVar: "OPENROUTER_API_KEY",
    maskedKey: "sk-or-********************",
    fullKey: "sk-or-v1-R8mQ3pLx7Nt2Ka9Hv4Wd1Pf6CyZj",
    baseUrl: "https://openrouter.ai/api/v1",
  },
  {
    provider: "Groq",
    envVar: "GROQ_API_KEY",
    maskedKey: "gsk_************************",
    fullKey: "gsk_R4mQt8Lp2Nx7Va1Ke9Hs5Wd3Pf6CyZjU",
    baseUrl: "https://api.groq.com/openai/v1",
  },
  {
    provider: "Together",
    envVar: "TOGETHER_API_KEY",
    maskedKey: "tsk_************************",
    fullKey: "tsk_R7mQ2pLv9Nx4Ta8Hr1Wd6Cy5ZjFk3UsB",
    baseUrl: "https://api.together.ai/v1",
  },
] as const;

export function AddProviderModal({ onAddProvider }: AddProviderModalProps) {
  const [open, setOpen] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string>(PROVIDER_PRESETS[0].provider);
  const activePreset = useMemo(
    () => PROVIDER_PRESETS.find((preset) => preset.provider === selectedProvider) ?? PROVIDER_PRESETS[0],
    [selectedProvider],
  );
  const [providerName, setProviderName] = useState<string>(activePreset.provider);
  const [envVar, setEnvVar] = useState<string>(activePreset.envVar);
  const [apiKeyValue, setApiKeyValue] = useState<string>("");
  const [baseUrl, setBaseUrl] = useState<string>(activePreset.baseUrl);
  const [headers, setHeaders] = useState<HeaderEntry[]>([]);

  const reset = () => {
    setSelectedProvider(PROVIDER_PRESETS[0].provider);
    setProviderName(PROVIDER_PRESETS[0].provider);
    setEnvVar(PROVIDER_PRESETS[0].envVar);
    setApiKeyValue("");
    setBaseUrl(PROVIDER_PRESETS[0].baseUrl);
    setHeaders([]);
  };

  const handleClose = useCallback(() => {
    setOpen(false);
    reset();
  }, []);

  const handlePresetChange = (provider: string) => {
    const preset = PROVIDER_PRESETS.find((item) => item.provider === provider) ?? PROVIDER_PRESETS[0];
    setSelectedProvider(provider);
    setProviderName(preset.provider);
    setEnvVar(preset.envVar);
    setApiKeyValue("");
    setBaseUrl(preset.baseUrl);
    setHeaders([]);
  };

  const addHeader = () => {
    setHeaders((current) => [
      ...current,
      { id: crypto.randomUUID(), key: "", value: "" },
    ]);
  };

  const updateHeader = (id: string, field: "key" | "value", nextValue: string) => {
    setHeaders((current) =>
      current.map((header) =>
        header.id === id ? { ...header, [field]: nextValue } : header,
      ),
    );
  };

  const removeHeader = (id: string) => {
    setHeaders((current) => current.filter((header) => header.id !== id));
  };

  const handleSubmit = () => {
    const normalizedProvider = providerName.trim() || activePreset.provider;
    const normalizedEnvVar = envVar.trim() || activePreset.envVar;
    const normalizedFullKey = apiKeyValue.trim();
    const isConfigured = normalizedFullKey.length > 0;
    const prefix = normalizedFullKey.includes("-")
      ? `${normalizedFullKey.split("-").slice(0, -1).join("-")}-`
      : normalizedFullKey.slice(0, Math.min(4, normalizedFullKey.length));
    const maskedKey = isConfigured ? `${prefix}${"*".repeat(24)}` : "Not configured";

    onAddProvider({
      provider: normalizedProvider,
      envVar: normalizedEnvVar,
      configured: isConfigured,
      maskedKey,
      fullKey: normalizedFullKey,
      baseUrl: baseUrl.trim(),
      headers: headers
        .map((header) => ({ key: header.key.trim(), value: header.value.trim() }))
        .filter((header) => header.key || header.value),
    });
    handleClose();
  };

  useEffect(() => {
    if (!open) {
      return;
    }

    const previousBodyOverflow = document.body.style.overflow;
    const previousHtmlOverflow = document.documentElement.style.overflow;

    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousBodyOverflow;
      document.documentElement.style.overflow = previousHtmlOverflow;
    };
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        handleClose();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, handleClose]);

  if (!open) {
    return (
      <Button
        type="button"
        variant="outline"
        size="lg"
        className="h-10 rounded-lg border-border-default px-4 text-sm"
        onClick={() => setOpen(true)}
      >
        Add provider
      </Button>
    );
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center overflow-hidden bg-black/20 p-4 backdrop-blur-sm"
      onClick={handleClose}
      role="presentation"
    >
      <div
        className="card-surface max-h-[calc(100vh-6rem)] w-full max-w-5xl overflow-y-auto rounded-2xl border border-border-subtle p-6"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Add provider"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-text-primary">Add provider</h2>
            <p className="mt-1 text-sm text-text-secondary">
              Create a new provider entry and its API key mapping.
            </p>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            className="h-8 w-8 rounded-lg text-text-secondary"
            onClick={handleClose}
          >
            <XIcon size={16} />
          </Button>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
          <div className="space-y-4">
            <div className="space-y-2">
              <p className="text-sm font-medium text-text-primary">Provider preset</p>
              <Select value={selectedProvider} onValueChange={handlePresetChange}>
                <SelectTrigger className="h-11 w-full rounded-lg border-border-default text-sm text-text-primary focus-visible:border-border-default focus-visible:ring-0">
                  <div className="flex items-center gap-2">
                    <ProviderIcon provider={selectedProvider} size={16} />
                    <span className="truncate">{selectedProvider}</span>
                  </div>
                </SelectTrigger>
                <SelectContent position="popper" align="start" className="rounded-lg p-1">
                  {PROVIDER_PRESETS.map((preset) => (
                    <SelectItem
                      key={preset.provider}
                      value={preset.provider}
                      className="rounded-md text-sm"
                    >
                      <ProviderIcon provider={preset.provider} size={16} />
                      <span>{preset.provider}</span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <p className="text-sm font-medium text-text-primary">Provider name</p>
                <Input
                  value={providerName}
                  onChange={(event) => setProviderName(event.target.value)}
                  className="h-11 rounded-lg border-border-default px-3 text-sm"
                />
              </div>
              <div className="space-y-2">
                <p className="text-sm font-medium text-text-primary">Env variable</p>
                <Input
                  value={envVar}
                  onChange={(event) => setEnvVar(event.target.value)}
                  className="h-11 rounded-lg border-border-default px-3 text-sm"
                />
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-sm font-medium text-text-primary">Base URL</p>
              <Input
                value={baseUrl}
                onChange={(event) => setBaseUrl(event.target.value)}
                placeholder="https://api.example.com/v1"
                className="h-11 rounded-lg border-border-default px-3 text-sm"
              />
            </div>

            <div className="space-y-2">
              <p className="text-sm font-medium text-text-primary">API key</p>
              <Input
                value={apiKeyValue}
                onChange={(event) => setApiKeyValue(event.target.value)}
                className="h-11 rounded-lg border-border-default px-3 font-mono text-sm"
              />
            </div>
          </div>

          <div className="rounded-2xl border border-border-subtle bg-bg-card-muted/40 p-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-sm font-medium text-text-primary">Optional headers</h3>
                <p className="mt-1 text-sm text-text-secondary">
                  Add any provider-specific headers that should be sent with requests.
                </p>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-8 rounded-lg border-border-default px-3 text-sm"
                onClick={addHeader}
              >
                <PlusIcon size={14} />
                Add
              </Button>
            </div>

            <div className="mt-4 space-y-3">
              {headers.length === 0 ? (
                <div className="rounded-xl border border-dashed border-border-subtle px-4 py-6 text-sm text-text-secondary">
                  No custom headers added.
                </div>
              ) : (
                headers.map((header) => (
                  <div key={header.id} className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
                    <Input
                      value={header.key}
                      onChange={(event) => updateHeader(header.id, "key", event.target.value)}
                      placeholder="Header name"
                      className="h-10 rounded-lg border-border-default px-3 text-sm"
                    />
                    <Input
                      value={header.value}
                      onChange={(event) => updateHeader(header.id, "value", event.target.value)}
                      placeholder="Header value"
                      className="h-10 rounded-lg border-border-default px-3 text-sm"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      className="h-10 w-10 rounded-lg text-text-secondary"
                      onClick={() => removeHeader(header.id)}
                    >
                      <TrashIcon size={16} />
                    </Button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            size="lg"
            className="h-10 rounded-lg border-border-default px-4 text-sm"
            onClick={handleClose}
          >
            Cancel
          </Button>
          <Button
            type="button"
            size="lg"
            className="h-10 rounded-lg px-4 text-sm"
            onClick={handleSubmit}
          >
            Add provider
          </Button>
        </div>
      </div>
    </div>
  );
}
