"use client";

import { useState } from "react";

import { CopyIcon } from "@phosphor-icons/react";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import type { RequestRow, RequestStatus } from "@/lib/mock-dashboard-data";

type RequestOutcome = RequestStatus;
type IoTab = "input" | "output";

interface RequestDetailSheetProps {
  row: RequestRow | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  ioLoggingEnabled: boolean;
  isEnablingIoLogging: boolean;
  ioEnableError: string | null;
  onEnableIoLogging: () => void;
}

const requestOutcomeStyles: Record<RequestOutcome, string> = {
  success: "bg-accent-green-bg text-accent-green",
  error: "bg-accent-red-bg text-accent-red",
  cancelled: "bg-bg-card-muted text-text-muted",
};

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString("en-US", {
    month: "2-digit",
    day: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatDuration(latencyMs: number): string {
  if (latencyMs >= 1000) {
    return `${(latencyMs / 1000).toFixed(2)} s`;
  }

  return `${latencyMs} ms`;
}

function formatCost(value: number): string {
  return `$${value.toFixed(4)}`;
}

function formatInteger(value: number): string {
  return value.toLocaleString("en-US");
}

function CopyIdButton({ value, label }: { value: string; label: string }) {
  return (
    <button
      type="button"
      aria-label={`Copy ${label}`}
      className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-sm text-text-muted hover:bg-bg-card-muted"
      onClick={() => void navigator.clipboard.writeText(value)}
    >
      <CopyIcon size={13} />
    </button>
  );
}

function DetailMetric({
  label,
  value,
  subtext,
}: {
  label: string;
  value: string;
  subtext?: React.ReactNode;
}) {
  return (
    <article className="card-surface-soft p-4">
      <p className="text-xs text-text-secondary">{label}</p>
      <p className="mt-2 text-xl leading-none font-semibold text-text-primary">{value}</p>
      {subtext ? <div className="mt-3 space-y-1 text-sm text-text-secondary">{subtext}</div> : null}
    </article>
  );
}

function formatPayload(value: string): string {
  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch {
    return value;
  }
}

function IoPanelShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-48 flex-col items-center justify-center rounded-xl border border-dashed border-border-subtle bg-bg-card-muted/60 px-6 py-10 text-center">
      {children}
    </div>
  );
}

function IoLoggingDisabledState({
  isEnabling,
  errorMessage,
  onEnable,
}: {
  isEnabling: boolean;
  errorMessage: string | null;
  onEnable: () => void;
}) {
  return (
    <IoPanelShell>
      <p className="text-sm font-medium text-text-primary">I/O logging is off</p>
      <p className="mt-2 max-w-sm text-sm text-text-secondary">
        Request and response bodies are not stored until you enable I/O logging. New requests will
        capture payloads after it is turned on.
      </p>
      <Button
        type="button"
        size="lg"
        className="mt-4 h-10 rounded-lg px-5 text-sm"
        disabled={isEnabling}
        onClick={onEnable}
      >
        {isEnabling ? "Enabling..." : "Enable I/O logging"}
      </Button>
      {errorMessage ? <p className="mt-3 text-sm text-accent-red">{errorMessage}</p> : null}
    </IoPanelShell>
  );
}

function IoNotCapturedState({ tab }: { tab: IoTab }) {
  const label = tab === "input" ? "request body" : "response body";

  return (
    <IoPanelShell>
      <p className="text-sm font-medium text-text-primary">No {label} stored</p>
      <p className="mt-2 max-w-sm text-sm text-text-secondary">
        I/O logging was not enabled when this request was made, so the {label} was not captured.
      </p>
    </IoPanelShell>
  );
}

function IoPayloadPanel({
  label,
  payload,
}: {
  label: string;
  payload: string;
}) {
  const formatted = formatPayload(payload);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium uppercase tracking-wide text-text-secondary">{label}</p>
        <button
          type="button"
          className="inline-flex items-center gap-1.5 rounded-md border border-border-subtle px-2.5 py-1 text-xs text-text-secondary hover:bg-bg-card-muted hover:text-text-primary"
          onClick={() => void navigator.clipboard.writeText(formatted)}
        >
          <CopyIcon size={12} />
          Copy
        </button>
      </div>
      <pre className="max-h-80 overflow-auto rounded-xl border border-border-subtle bg-[#1f2328] p-4 font-mono text-xs leading-relaxed text-[#e6edf3]">
        {formatted}
      </pre>
    </div>
  );
}

function IoSection({
  ioLoggingEnabled,
  isEnablingIoLogging,
  ioEnableError,
  onEnableIoLogging,
  inputPayload,
  outputPayload,
}: {
  ioLoggingEnabled: boolean;
  isEnablingIoLogging: boolean;
  ioEnableError: string | null;
  onEnableIoLogging: () => void;
  inputPayload: string | null;
  outputPayload: string | null;
}) {
  const [activeIoTab, setActiveIoTab] = useState<IoTab>("input");
  const showIoTabs = ioLoggingEnabled || Boolean(inputPayload || outputPayload);

  const renderIoContent = () => {
    if (!ioLoggingEnabled) {
      return (
        <IoLoggingDisabledState
          isEnabling={isEnablingIoLogging}
          errorMessage={ioEnableError}
          onEnable={onEnableIoLogging}
        />
      );
    }

    const activePayload = activeIoTab === "input" ? inputPayload : outputPayload;

    if (activePayload) {
      return (
        <IoPayloadPanel
          label={activeIoTab === "input" ? "Request body" : "Response body"}
          payload={activePayload}
        />
      );
    }

    return <IoNotCapturedState tab={activeIoTab} />;
  };

  return (
    <section>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h4 className="text-sm font-semibold text-text-primary">Input / output</h4>
        {showIoTabs ? (
          <div className="inline-flex rounded-lg border border-border-subtle bg-bg-card-muted p-0.5">
            {(["input", "output"] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveIoTab(tab)}
                className={
                  activeIoTab === tab
                    ? "rounded-md bg-bg-card px-3 py-1 text-xs font-medium text-text-primary shadow-sm"
                    : "rounded-md px-3 py-1 text-xs text-text-secondary hover:text-text-primary"
                }
              >
                {tab === "input" ? "Input" : "Output"}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      {renderIoContent()}
    </section>
  );
}

export function RequestDetailSheet({
  row,
  open,
  onOpenChange,
  ioLoggingEnabled,
  isEnablingIoLogging,
  ioEnableError,
  onEnableIoLogging,
}: RequestDetailSheetProps) {
  const outcome: RequestOutcome = row?.status ?? "success";
  const outcomeLabel = outcome.charAt(0).toUpperCase() + outcome.slice(1);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full gap-0 overflow-y-auto border-border-subtle bg-bg-card p-0 sm:max-w-2xl"
      >
        {row ? (
          <>
            <SheetHeader className="border-b border-border-subtle px-5 py-4 text-left">
              <div className="flex flex-wrap items-center gap-3 pr-8">
                <SheetTitle className="text-lg font-semibold text-text-primary">
                  Request details
                </SheetTitle>
                <span
                  className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${requestOutcomeStyles[outcome]}`}
                >
                  <span className="status-dot bg-current" />
                  {outcomeLabel}
                </span>
              </div>
              <SheetDescription className="text-sm text-text-secondary">
                {formatTimestamp(row.timestamp)} · {row.endpoint}
              </SheetDescription>
            </SheetHeader>

            <div className="space-y-6 px-5 py-5">
              <section>
                <h4 className="mb-3 text-sm font-semibold text-text-primary">Metadata</h4>
                <dl className="grid grid-cols-[120px_1fr] gap-y-2 text-sm">
                  <dt className="text-text-secondary">Request ID</dt>
                  <dd className="flex min-w-0 items-start gap-2 font-medium text-text-primary">
                    <span className="font-mono text-xs break-all">{row.id}</span>
                    <CopyIdButton value={row.id} label="gateway ID" />
                  </dd>

                  <dt className="text-text-secondary">Upstream ID</dt>
                  <dd className="flex min-w-0 items-start gap-2 font-medium text-text-primary">
                    {row.upstreamRequestId ? (
                      <>
                        <span className="font-mono text-xs break-all">{row.upstreamRequestId}</span>
                        <CopyIdButton value={row.upstreamRequestId} label="upstream ID" />
                      </>
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </dd>

                  <dt className="text-text-secondary">Client</dt>
                  <dd className="font-medium text-text-primary">{row.client}</dd>

                  <dt className="text-text-secondary">Provider</dt>
                  <dd className="font-medium text-text-primary">{row.provider}</dd>

                  <dt className="text-text-secondary">Model</dt>
                  <dd className="font-medium text-text-primary">{row.model}</dd>

                  <dt className="text-text-secondary">Streaming</dt>
                  <dd className="font-medium text-text-primary">{row.streaming ? "Yes" : "No"}</dd>
                </dl>
              </section>

              <section>
                <h4 className="mb-3 text-sm font-semibold text-text-primary">Metrics</h4>
                <div className="grid gap-3 sm:grid-cols-2">
                  <DetailMetric
                    label="Tokens"
                    value={formatInteger(row.totalTokens)}
                    subtext={
                      <>
                        <p>
                          <span className="font-medium text-text-primary">
                            {formatInteger(row.inputTokens)}
                          </span>{" "}
                          input
                        </p>
                        <p>
                          <span className="font-medium text-text-primary">
                            {formatInteger(row.outputTokens)}
                          </span>{" "}
                          output
                        </p>
                      </>
                    }
                  />
                  <DetailMetric
                    label="Latency"
                    value={formatDuration(row.latencyMs)}
                    subtext={
                      <p>
                        <span className="font-medium text-text-primary">{row.latencyMs} ms</span> total
                      </p>
                    }
                  />
                  <DetailMetric
                    label="Estimated cost"
                    value={formatCost(row.costUsd)}
                  />
                  <DetailMetric label="Status" value={outcomeLabel} />
                </div>
              </section>

              <IoSection
                ioLoggingEnabled={ioLoggingEnabled}
                isEnablingIoLogging={isEnablingIoLogging}
                ioEnableError={ioEnableError}
                onEnableIoLogging={onEnableIoLogging}
                inputPayload={row.io?.input ?? null}
                outputPayload={row.io?.output ?? null}
              />
            </div>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}
