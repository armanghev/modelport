"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { XIcon } from "@phosphor-icons/react";

import {
  fetchProviderPresets,
  isValidProviderSlug,
  normalizeProviderSlug,
  sanitizeSlugInput,
  type ProviderConfigDraft,
  type ProviderConfigRow,
  type ProviderPreset,
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

interface ProviderModalProps {
  mode: "add" | "edit";
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (provider: ProviderConfigDraft) => void;
  initialProvider?: ProviderConfigRow;
}

type ProviderProtocol = "openai" | "anthropic";

const CUSTOM_PRESET_ID = "custom";

type ProviderPresetOption = {
  slug: string;
  displayName: string;
  protocol: ProviderProtocol;
  baseUrl: string;
};

function mapPreset(preset: ProviderPreset): ProviderPresetOption {
  return {
    slug: preset.slug,
    displayName: preset.display_name,
    protocol: preset.protocol,
    baseUrl: preset.base_url,
  };
}

function protocolToProviderType(protocol: ProviderProtocol) {
  return protocol === "anthropic" ? "anthropic_compatible" : "openai_compatible";
}

export function ProviderModal({
  mode,
  open,
  onOpenChange,
  onSubmit,
  initialProvider,
}: ProviderModalProps) {
  const isEditMode = mode === "edit";
  const initialProtocol: ProviderProtocol =
    initialProvider?.providerType === "anthropic_compatible" ? "anthropic" : "openai";

  const [presets, setPresets] = useState<ProviderPresetOption[]>([]);
  const [protocol, setProtocol] = useState<ProviderProtocol>(initialProtocol);
  const [selectedPresetId, setSelectedPresetId] = useState(CUSTOM_PRESET_ID);
  const [displayName, setDisplayName] = useState(initialProvider?.provider ?? "");
  const [slug, setSlug] = useState(initialProvider?.slug ?? "");
  const [credentialName, setCredentialName] = useState(
    initialProvider?.credentialName ?? "Default API key",
  );
  const [apiKeyValue, setApiKeyValue] = useState(initialProvider?.fullKey ?? "");
  const [baseUrl, setBaseUrl] = useState(initialProvider?.baseUrl ?? "");
  const [slugError, setSlugError] = useState<string | null>(null);

  const isCustom = selectedPresetId === CUSTOM_PRESET_ID;

  const presetsForProtocol = useMemo(
    () => presets.filter((preset) => preset.protocol === protocol),
    [presets, protocol],
  );

  const handleClose = useCallback(() => {
    onOpenChange(false);
  }, [onOpenChange]);

  const applyPreset = (presetId: string) => {
    if (presetId === CUSTOM_PRESET_ID) {
      setSelectedPresetId(CUSTOM_PRESET_ID);
      setDisplayName("");
      setSlug("");
      setBaseUrl("");
      if (mode === "add") {
        setApiKeyValue("");
        setCredentialName("Default API key");
      }
      return;
    }

    const preset = presets.find((item) => item.slug === presetId);
    if (!preset) {
      return;
    }

    setSelectedPresetId(preset.slug);
    setDisplayName(preset.displayName);
    setSlug(preset.slug);
    setCredentialName(`${preset.displayName} API key`);
    setBaseUrl(preset.baseUrl);
    if (mode === "add") {
      setApiKeyValue("");
    }
  };

  const handleProtocolChange = (nextProtocol: ProviderProtocol) => {
    setProtocol(nextProtocol);
    if (isEditMode) {
      return;
    }

    const firstPreset = presets.find((preset) => preset.protocol === nextProtocol);
    if (firstPreset) {
      applyPreset(firstPreset.slug);
    } else {
      applyPreset(CUSTOM_PRESET_ID);
    }
  };

  const handleSlugChange = (value: string) => {
    setSlug(sanitizeSlugInput(value));
    if (!isEditMode && selectedPresetId !== CUSTOM_PRESET_ID) {
      setSelectedPresetId(CUSTOM_PRESET_ID);
    }
    setSlugError(null);
  };

  const handleSubmit = () => {
    const normalizedSlug = normalizeProviderSlug(slug);
    if (!normalizedSlug || !isValidProviderSlug(normalizedSlug)) {
      setSlugError("Provider ID must use lowercase letters, numbers, and dashes.");
      return;
    }

    if (!baseUrl.trim()) {
      return;
    }

    onSubmit({
      slug: normalizedSlug,
      providerType: protocolToProviderType(protocol),
      provider: displayName.trim() || normalizedSlug,
      credentialName:
        credentialName.trim() ||
        `${displayName.trim() || normalizedSlug} API key`,
      fullKey: apiKeyValue.trim(),
      baseUrl: baseUrl.trim(),
    });
    handleClose();
  };

  useEffect(() => {
    if (!open || isEditMode) {
      return;
    }

    let active = true;

    void fetchProviderPresets()
      .then((items) => {
        if (!active) {
          return;
        }

        const mapped = items.map(mapPreset);
        setPresets(mapped);

        const firstPreset =
          mapped.find((preset) => preset.protocol === "openai") ?? mapped[0];
        if (!firstPreset) {
          setProtocol("openai");
          setSelectedPresetId(CUSTOM_PRESET_ID);
          setDisplayName("");
          setSlug("");
          setBaseUrl("");
          setCredentialName("Default API key");
          setApiKeyValue("");
          return;
        }

        setProtocol(firstPreset.protocol);
        setSelectedPresetId(firstPreset.slug);
        setDisplayName(firstPreset.displayName);
        setSlug(firstPreset.slug);
        setCredentialName(`${firstPreset.displayName} API key`);
        setBaseUrl(firstPreset.baseUrl);
        setApiKeyValue("");
      })
      .catch(() => {
        if (!active) {
          return;
        }
        setPresets([]);
        setSelectedPresetId(CUSTOM_PRESET_ID);
      });

    return () => {
      active = false;
    };
  }, [open, isEditMode]);

  useEffect(() => {
    if (!open || !isEditMode || presets.length > 0 || !initialProvider) {
      return;
    }

    let active = true;

    void fetchProviderPresets()
      .then((items) => {
        if (!active) {
          return;
        }
        setPresets(items.map(mapPreset));
      })
      .catch(() => {
        if (active) {
          setPresets([]);
        }
      });

    return () => {
      active = false;
    };
  }, [open, isEditMode, initialProvider, presets.length]);

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

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center overflow-hidden bg-black/20 p-4 backdrop-blur-sm"
      onClick={handleClose}
      role="presentation"
    >
      <div
        className="card-surface max-h-[calc(100vh-6rem)] w-full max-w-3xl overflow-y-auto rounded-2xl border border-border-subtle p-6"
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
                ? "Update display name, base URL, credential label, or API key."
                : "Create a provider and store its API key in the backend."}
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

        <div className="mt-6 space-y-4">
          {!isEditMode ? (
            <>
              <div className="space-y-2">
                <p className="text-sm font-medium text-text-primary">Protocol</p>
                <Select
                  value={protocol}
                  onValueChange={(value) => handleProtocolChange(value as ProviderProtocol)}
                >
                  <SelectTrigger className="h-11 w-full rounded-lg border-border-default text-sm text-text-primary focus-visible:border-border-default focus-visible:ring-0">
                    <span>{protocol === "anthropic" ? "Anthropic" : "OpenAI"}</span>
                  </SelectTrigger>
                  <SelectContent position="popper" align="start" className="rounded-lg p-1">
                    <SelectItem value="openai" className="rounded-md text-sm">
                      OpenAI
                    </SelectItem>
                    <SelectItem value="anthropic" className="rounded-md text-sm">
                      Anthropic
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <p className="text-sm font-medium text-text-primary">Preset</p>
                <Select value={selectedPresetId} onValueChange={applyPreset}>
                  <SelectTrigger className="h-11 w-full rounded-lg border-border-default text-sm text-text-primary focus-visible:border-border-default focus-visible:ring-0">
                    <div className="flex items-center gap-2">
                      {isCustom ? (
                        <span className="truncate">Custom</span>
                      ) : (
                        <>
                          <ProviderIcon provider={displayName} size={16} />
                          <span className="truncate">{displayName}</span>
                        </>
                      )}
                    </div>
                  </SelectTrigger>
                  <SelectContent position="popper" align="start" className="rounded-lg p-1">
                    {presetsForProtocol.map((preset) => (
                      <SelectItem
                        key={preset.slug}
                        value={preset.slug}
                        className="rounded-md text-sm"
                      >
                        <ProviderIcon provider={preset.displayName} size={16} />
                        <span>{preset.displayName}</span>
                      </SelectItem>
                    ))}
                    <SelectItem value={CUSTOM_PRESET_ID} className="rounded-md text-sm">
                      Custom
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </>
          ) : null}

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <p className="text-sm font-medium text-text-primary">Display name</p>
              <Input
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
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
              <p className="text-sm font-medium text-text-primary">Provider ID</p>
              <Input
                value={slug}
                onChange={(event) => handleSlugChange(event.target.value)}
                disabled={isEditMode}
                placeholder="openai or mock-local"
                className="h-11 rounded-lg border-border-default px-3 font-mono text-sm"
              />
              {slugError ? (
                <p className="text-xs text-accent-red">{slugError}</p>
              ) : (
                <p className="text-xs text-text-muted">
                  Lowercase routing id used by the proxy (letters, numbers, dashes).
                </p>
              )}
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium text-text-primary">Base URL</p>
              <Input
                value={baseUrl}
                onChange={(event) => setBaseUrl(event.target.value)}
                readOnly={!isEditMode && !isCustom}
                placeholder="https://api.example.com/v1"
                className="h-11 rounded-lg border-border-default px-3 text-sm"
              />
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium text-text-primary">API key (optional)</p>
            <Input
              value={apiKeyValue}
              onChange={(event) => setApiKeyValue(event.target.value)}
              className="h-11 rounded-lg border-border-default px-3 font-mono text-sm"
            />
            <p className="text-xs text-text-muted">
              {isEditMode
                ? "Leave blank to keep the current stored key."
                : "Leave blank to add the provider without a credential."}
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

