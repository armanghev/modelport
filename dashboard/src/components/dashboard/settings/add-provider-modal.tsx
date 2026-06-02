"use client";

import { useCallback, useEffect, useState } from "react";

import { XIcon } from "@phosphor-icons/react";

import {
  type ProviderConfigDraft,
  type ProviderConfigRow,
} from "@/lib/admin-api";
import { ProviderIcon } from "@/components/brand/render-provider-icon";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";

interface AddProviderModalProps {
  onAddProvider: (provider: ProviderConfigDraft) => void;
}

interface EditProviderModalProps {
  open: boolean;
  provider: ProviderConfigRow | null;
  onOpenChange: (open: boolean) => void;
  onEditProvider: (provider: ProviderConfigDraft) => void;
}

interface ProviderModalProps {
  mode: "add" | "edit";
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (provider: ProviderConfigDraft) => void;
  initialProvider?: ProviderConfigRow;
}

const PROVIDER_PRESETS = [
  {
    providerId: "openai",
    providerType: "openai_compatible" as const,
    provider: "OpenAI",
    envVar: "OPENAI_API_KEY",
    baseUrl: "https://api.openai.com/v1",
  },
  {
    providerId: "anthropic",
    providerType: "anthropic_compatible" as const,
    provider: "Anthropic",
    envVar: "ANTHROPIC_API_KEY",
    baseUrl: "https://api.anthropic.com",
  },
  {
    providerId: "gemini",
    providerType: "openai_compatible" as const,
    provider: "Gemini",
    envVar: "GEMINI_API_KEY",
    baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai/",
  },
  {
    providerId: "openrouter",
    providerType: "openai_compatible" as const,
    provider: "OpenRouter",
    envVar: "OPENROUTER_API_KEY",
    baseUrl: "https://openrouter.ai/api/v1",
  },
  {
    providerId: "groq",
    providerType: "openai_compatible" as const,
    provider: "Groq",
    envVar: "GROQ_API_KEY",
    baseUrl: "https://api.groq.com/openai/v1",
  },
  {
    providerId: "together",
    providerType: "openai_compatible" as const,
    provider: "Together",
    envVar: "TOGETHER_API_KEY",
    baseUrl: "https://api.together.ai/v1",
  },
] as const;

function getPreset(provider?: ProviderConfigRow) {
  if (!provider) {
    return PROVIDER_PRESETS[0];
  }

  return (
    PROVIDER_PRESETS.find((preset) => preset.providerId === provider.providerId) ??
    PROVIDER_PRESETS.find((preset) => preset.envVar === provider.envVar) ??
    PROVIDER_PRESETS[0]
  );
}

function ProviderModal({
  mode,
  open,
  onOpenChange,
  onSubmit,
  initialProvider,
}: ProviderModalProps) {
  const activePreset = getPreset(initialProvider);
  const [selectedProviderId, setSelectedProviderId] = useState<string>(
    activePreset.providerId,
  );
  const [providerType, setProviderType] = useState(activePreset.providerType);
  const [providerName, setProviderName] = useState(
    initialProvider?.provider ?? activePreset.provider,
  );
  const [credentialName, setCredentialName] = useState(
    initialProvider?.credentialName ?? `${activePreset.provider} Default`,
  );
  const [envVar, setEnvVar] = useState(
    initialProvider?.envVar ?? activePreset.envVar,
  );
  const [apiKeyValue, setApiKeyValue] = useState(initialProvider?.fullKey ?? "");
  const [baseUrl, setBaseUrl] = useState(
    initialProvider?.baseUrl ?? activePreset.baseUrl,
  );

  const handleClose = useCallback(() => {
    onOpenChange(false);
  }, [onOpenChange]);

  const handlePresetChange = (providerId: string) => {
    const preset =
      PROVIDER_PRESETS.find((item) => item.providerId === providerId) ??
      PROVIDER_PRESETS[0];
    setSelectedProviderId(providerId);
    setProviderType(preset.providerType);
    setProviderName(preset.provider);
    setCredentialName(`${preset.provider} Default`);
    setEnvVar(preset.envVar);
    setBaseUrl(preset.baseUrl);
    if (mode === "add") {
      setApiKeyValue("");
    }
  };

  const handleSubmit = () => {
    onSubmit({
      providerId: selectedProviderId,
      providerType,
      provider: providerName.trim() || activePreset.provider,
      credentialName:
        credentialName.trim() || `${providerName.trim() || activePreset.provider} Default`,
      envVar: envVar.trim(),
      fullKey: apiKeyValue.trim(),
      baseUrl: baseUrl.trim(),
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
  }, [handleClose, open]);

  if (!open) {
    return null;
  }

  const isEditMode = mode === "edit";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center overflow-hidden bg-black/20 p-4 backdrop-blur-sm"
      onClick={handleClose}
      role="presentation"
    >
      <div
        className="card-surface max-h-[calc(100vh-6rem)] w-full max-w-4xl overflow-y-auto rounded-2xl border border-border-subtle p-6"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={isEditMode ? "Edit provider" : "Add provider"}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-text-primary">
              {isEditMode ? "Edit provider" : "Add provider"}
            </h2>
            <p className="mt-1 text-sm text-text-secondary">
              {isEditMode
                ? "Update the provider configuration and credential mapping."
                : "Create a new provider entry and its default credential."}
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

        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="space-y-4">
            <div className="space-y-2">
              <p className="text-sm font-medium text-text-primary">Provider preset</p>
              <Select
                value={selectedProviderId}
                onValueChange={handlePresetChange}
                disabled={isEditMode}
              >
                <SelectTrigger className="h-11 w-full rounded-lg border-border-default text-sm text-text-primary focus-visible:border-border-default focus-visible:ring-0">
                  <div className="flex items-center gap-2">
                    <ProviderIcon provider={providerName} size={16} />
                    <span className="truncate">{providerName}</span>
                  </div>
                </SelectTrigger>
                <SelectContent position="popper" align="start" className="rounded-lg p-1">
                  {PROVIDER_PRESETS.map((preset) => (
                    <SelectItem
                      key={preset.providerId}
                      value={preset.providerId}
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
                <p className="text-sm font-medium text-text-primary">Credential label</p>
                <Input
                  value={credentialName}
                  onChange={(event) => setCredentialName(event.target.value)}
                  className="h-11 rounded-lg border-border-default px-3 text-sm"
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <p className="text-sm font-medium text-text-primary">Env variable</p>
                <Input
                  value={envVar}
                  onChange={(event) => setEnvVar(event.target.value)}
                  className="h-11 rounded-lg border-border-default px-3 text-sm"
                />
              </div>
              <div className="space-y-2">
                <p className="text-sm font-medium text-text-primary">Provider id</p>
                <Input
                  value={selectedProviderId}
                  disabled
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
            <h3 className="text-sm font-medium text-text-primary">Credential storage</h3>
            <p className="mt-1 text-sm text-text-secondary">
              Entering an API key stores it in the backend using reversible encryption. Leaving it
              blank keeps the credential env-backed using the configured variable name.
            </p>
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
            {isEditMode ? "Save changes" : "Add provider"}
          </Button>
        </div>
      </div>
    </div>
  );
}

export function AddProviderModal({ onAddProvider }: AddProviderModalProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="lg"
        className="h-10 rounded-lg border-border-default px-4 text-sm"
        onClick={() => setOpen(true)}
      >
        Add provider
      </Button>
      <ProviderModal
        key={`add-${open ? "open" : "closed"}`}
        mode="add"
        open={open}
        onOpenChange={setOpen}
        onSubmit={onAddProvider}
      />
    </>
  );
}

export function EditProviderModal({
  open,
  provider,
  onOpenChange,
  onEditProvider,
}: EditProviderModalProps) {
  if (!provider) {
    return null;
  }

  return (
    <ProviderModal
      key={`edit-${provider.id}-${open ? "open" : "closed"}`}
      mode="edit"
      open={open}
      onOpenChange={onOpenChange}
      onSubmit={onEditProvider}
      initialProvider={provider}
    />
  );
}
