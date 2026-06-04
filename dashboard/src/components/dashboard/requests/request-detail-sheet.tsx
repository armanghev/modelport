"use client";

import { useState } from "react";

import { CopyButton } from "@/components/ui/copy-button";
import { RequestIoModal } from "@/components/dashboard/requests/request-io-modal";
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
    <CopyButton
      value={value}
      aria-label={`Copy ${label}`}
      iconSize={13}
      className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-sm hover:bg-bg-card-muted"
    />
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

function IoPanelShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-36 flex-col items-center justify-center rounded-xl border border-dashed border-border-subtle bg-bg-card-muted/60 px-6 py-8 text-center">
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

function IoNotCapturedState() {
  return (
    <IoPanelShell>
      <p className="text-sm font-medium text-text-primary">No I/O payloads stored</p>
      <p className="mt-2 max-w-sm text-sm text-text-secondary">
        I/O logging was not enabled when this request was made, so request and response bodies were
        not captured.
      </p>
    </IoPanelShell>
  );
}

function IoSection({
  row,
  ioLoggingEnabled,
  isEnablingIoLogging,
  ioEnableError,
  onEnableIoLogging,
  onOpenInspector,
}: {
  row: RequestRow;
  ioLoggingEnabled: boolean;
  isEnablingIoLogging: boolean;
  ioEnableError: string | null;
  onEnableIoLogging: () => void;
  onOpenInspector: () => void;
}) {
  const inputPayload = row.io?.input ?? null;
  const outputPayload = row.io?.output ?? null;
  const hasIoPayload = Boolean(inputPayload || outputPayload);

  if (!ioLoggingEnabled) {
    return (
      <IoLoggingDisabledState
        isEnabling={isEnablingIoLogging}
        errorMessage={ioEnableError}
        onEnable={onEnableIoLogging}
      />
    );
  }

  if (!hasIoPayload) {
    return <IoNotCapturedState />;
  }

  return (
    <div className="rounded-xl border border-border-subtle bg-bg-card-muted/40 p-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <p className="text-sm font-medium text-text-primary">Captured I/O available</p>
          <p className="text-sm text-text-secondary">
            {formatInteger(row.inputTokens)} prompt tokens · {formatInteger(row.outputTokens)}{" "}
            completion tokens
          </p>
          <p className="text-xs text-text-muted">
            {inputPayload ? "Request body stored" : "Request body missing"} ·{" "}
            {outputPayload ? "Response body stored" : "Response body missing"}
          </p>
        </div>
        <Button
          type="button"
          size="lg"
          className="h-10 shrink-0 rounded-lg px-5 text-sm"
          onClick={onOpenInspector}
        >
          View I/O details
        </Button>
      </div>
    </div>
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
  const [ioModalOpen, setIoModalOpen] = useState(false);
  const outcome: RequestOutcome = row?.status ?? "success";
  const outcomeLabel = outcome.charAt(0).toUpperCase() + outcome.slice(1);

  const handleSheetOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      setIoModalOpen(false);
    }
    onOpenChange(nextOpen);
  };

  return (
    <Sheet open={open} onOpenChange={handleSheetOpenChange}>
      <SheetContent
        side="right"
        className="w-full gap-0 overflow-y-auto border-border-subtle bg-bg-card p-0 sm:max-w-2xl"
      >
        <SheetHeader className="border-b border-border-subtle px-5 py-4 text-left">
          <div className="flex flex-wrap items-center gap-3 pr-8">
            <SheetTitle className="text-lg font-semibold text-text-primary">
              Request details
            </SheetTitle>
            {row ? (
              <span
                className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${requestOutcomeStyles[outcome]}`}
              >
                <span className="status-dot bg-current" />
                {outcomeLabel}
              </span>
            ) : null}
          </div>
          {row ? (
            <SheetDescription className="text-sm text-text-secondary">
              {formatTimestamp(row.timestamp)} · {row.endpoint}
            </SheetDescription>
          ) : null}
        </SheetHeader>

        {row ? (
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
                <DetailMetric label="Estimated cost" value={formatCost(row.costUsd)} />
                <DetailMetric label="Status" value={outcomeLabel} />
              </div>
            </section>

            <section>
              <h4 className="mb-3 text-sm font-semibold text-text-primary">Input / output</h4>
              <IoSection
                row={row}
                ioLoggingEnabled={ioLoggingEnabled}
                isEnablingIoLogging={isEnablingIoLogging}
                ioEnableError={ioEnableError}
                onEnableIoLogging={onEnableIoLogging}
                onOpenInspector={() => setIoModalOpen(true)}
              />
            </section>
          </div>
        ) : null}

        <RequestIoModal row={row} open={ioModalOpen} onClose={() => setIoModalOpen(false)} />
      </SheetContent>
    </Sheet>
  );
}
