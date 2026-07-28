"use client";

import { useCallback, useEffect, useState } from "react";

import { XIcon } from "@phosphor-icons/react";

import type { PricingEntry } from "@/lib/dashboard-types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

export interface PricingProviderOption {
  id: string;
  label: string;
}

export interface PricingOverrideDraft {
  providerId: string;
  model: string;
  inputPer1mUsd: number;
  outputPer1mUsd: number;
  currency: string;
  enabled: boolean;
}

interface PricingOverrideModalProps {
  mode: "add" | "edit";
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (draft: PricingOverrideDraft) => void;
  providers: PricingProviderOption[];
  initialEntry?: PricingEntry | null;
}

function parseNonNegative(value: string): number | null {
  const parsed = Number.parseFloat(value);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return null;
  }
  return parsed;
}

export function PricingOverrideModal({
  mode,
  open,
  onOpenChange,
  onSubmit,
  providers,
  initialEntry,
}: PricingOverrideModalProps) {
  const isEditMode = mode === "edit";
  const defaultProviderId = initialEntry?.providerId ?? providers[0]?.id ?? "";

  const [providerId, setProviderId] = useState(defaultProviderId);
  const [model, setModel] = useState(initialEntry?.model ?? "");
  const [inputPer1mUsd, setInputPer1mUsd] = useState(
    initialEntry ? String(initialEntry.inputPer1mUsd) : "",
  );
  const [outputPer1mUsd, setOutputPer1mUsd] = useState(
    initialEntry ? String(initialEntry.outputPer1mUsd) : "",
  );
  const [currency, setCurrency] = useState(initialEntry?.currency ?? "USD");
  const [enabled, setEnabled] = useState(initialEntry?.enabled ?? true);
  const [formError, setFormError] = useState<string | null>(null);

  const handleClose = useCallback(() => {
    onOpenChange(false);
  }, [onOpenChange]);

  const handleSubmit = () => {
    if (!providerId) {
      setFormError("Select a provider.");
      return;
    }
    if (!model.trim()) {
      setFormError("Model id is required.");
      return;
    }

    const inputRate = parseNonNegative(inputPer1mUsd);
    const outputRate = parseNonNegative(outputPer1mUsd);
    if (inputRate === null || outputRate === null) {
      setFormError("Input and output prices must be non-negative numbers.");
      return;
    }

    onSubmit({
      providerId,
      model: model.trim(),
      inputPer1mUsd: inputRate,
      outputPer1mUsd: outputRate,
      currency: currency.trim() || "USD",
      enabled,
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

  const selectedProvider =
    providers.find((provider) => provider.id === providerId) ?? providers[0];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center overflow-hidden bg-black/20 p-4 backdrop-blur-sm"
      onClick={handleClose}
      role="presentation"
    >
      <div
        className="card-surface max-h-[calc(100vh-6rem)] w-full max-w-xl overflow-y-auto rounded-2xl border border-border-subtle p-6"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={isEditMode ? "Edit pricing override" : "Add pricing override"}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-text-primary">
              {isEditMode ? "Edit pricing" : "Add pricing"}
            </h2>
            <p className="mt-1 text-sm text-text-secondary">
              {isEditMode
                ? "Update rates used for estimated cost when billing data is unavailable."
                : "Define per-model input and output rates (USD per 1M tokens)."}
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
          <div className="space-y-2">
            <p className="text-sm font-medium text-text-primary">Provider</p>
            <Select value={providerId} onValueChange={setProviderId}>
              <SelectTrigger className="h-11 w-full rounded-lg border-border-default text-sm text-text-primary focus-visible:border-border-default focus-visible:ring-0">
                <SelectValue>
                  {selectedProvider?.label ?? "Select provider"}
                </SelectValue>
              </SelectTrigger>
              <SelectContent position="popper" align="start" className="rounded-lg p-1">
                {providers.map((provider) => (
                  <SelectItem
                    key={provider.id}
                    value={provider.id}
                    className="rounded-md text-sm"
                  >
                    {provider.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium text-text-primary">Model</p>
            <Input
              value={model}
              onChange={(event) => {
                setModel(event.target.value);
                setFormError(null);
              }}
              placeholder="gpt-5 or *"
              className="h-11 rounded-lg border-border-default px-3 font-mono text-sm"
            />
            <p className="text-xs text-text-muted">
              Use <span className="font-mono">*</span> for a provider-wide fallback rate.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <p className="text-sm font-medium text-text-primary">Input / 1M tokens (USD)</p>
              <Input
                type="number"
                min={0}
                step="any"
                value={inputPer1mUsd}
                onChange={(event) => {
                  setInputPer1mUsd(event.target.value);
                  setFormError(null);
                }}
                className="h-11 rounded-lg border-border-default px-3 text-sm"
              />
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium text-text-primary">Output / 1M tokens (USD)</p>
              <Input
                type="number"
                min={0}
                step="any"
                value={outputPer1mUsd}
                onChange={(event) => {
                  setOutputPer1mUsd(event.target.value);
                  setFormError(null);
                }}
                className="h-11 rounded-lg border-border-default px-3 text-sm"
              />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 sm:items-end">
            <div className="space-y-2">
              <p className="text-sm font-medium text-text-primary">Currency</p>
              <Input
                value={currency}
                onChange={(event) => setCurrency(event.target.value.toUpperCase())}
                className="h-11 rounded-lg border-border-default px-3 text-sm"
              />
            </div>
            <div className="flex items-start gap-3 pb-1">
              <Switch
                checked={enabled}
                onCheckedChange={setEnabled}
                className="mt-0.5"
              />
              <div className="space-y-0.5">
                <p className="text-sm font-medium text-text-primary">Enabled</p>
                <p className="text-sm text-text-secondary">
                  Disabled overrides are ignored for cost estimates.
                </p>
              </div>
            </div>
          </div>

          {formError ? <p className="text-sm text-accent-red">{formError}</p> : null}
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
            disabled={providers.length === 0}
          >
            {isEditMode ? "Save changes" : "Add pricing"}
          </Button>
        </div>
      </div>
    </div>
  );
}
