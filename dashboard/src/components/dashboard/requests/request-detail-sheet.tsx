"use client";

import { useMemo, useState } from "react";

import { CodeIcon } from "@phosphor-icons/react";

import { CopyButton } from "@/components/ui/copy-button";
import { RequestIoModal } from "@/components/dashboard/requests/request-io-modal";
import { Button } from "@/components/ui/button";
import {
  extractResponseDisplayText,
  formatPayloadJson,
} from "@/lib/request-io";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import type { RequestRow, RequestStatus } from "@/lib/dashboard-types";
import {
  formatCost,
  formatInteger,
  formatTimestamp,
} from "@/lib/format";

type RequestOutcome = RequestStatus;

interface RequestDetailSheetProps {
  row: RequestRow | null;
  open: boolean;
  isLoading: boolean;
  errorMessage: string | null;
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

function formatDuration(latencyMs: number): string {
  if (latencyMs >= 1000) {
    return `${(latencyMs / 1000).toFixed(2)} s`;
  }

  return `${latencyMs} ms`;
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

function IoResponseBlock({
  tokenLabel,
  payload,
  displayText,
  formattedJson,
  missingLabel,
}: {
  tokenLabel: string;
  payload: string | null;
  displayText: string;
  formattedJson: string;
  missingLabel: string;
}) {
  return (
    <IoResponseBlockContent
      key={payload ?? "missing"}
      tokenLabel={tokenLabel}
      payload={payload}
      displayText={displayText}
      formattedJson={formattedJson}
      missingLabel={missingLabel}
    />
  );
}

function IoResponseBlockContent({
  tokenLabel,
  payload,
  displayText,
  formattedJson,
  missingLabel,
}: {
  tokenLabel: string;
  payload: string | null;
  displayText: string;
  formattedJson: string;
  missingLabel: string;
}) {
  const [showRaw, setShowRaw] = useState(false);

  if (!payload) {
    return (
      <div className="rounded-xl border border-border-subtle bg-bg-card-muted/30 px-4 py-3">
        <p className="text-sm font-medium text-text-primary">Response</p>
        <p className="mt-1 text-sm text-text-muted">{missingLabel}</p>
      </div>
    );
  }

  const copyValue = showRaw ? formattedJson : displayText || formattedJson;
  const bodyContent = showRaw ? (
    <pre className="max-h-72 overflow-auto whitespace-pre-wrap wrap-break-word bg-[#1f2328] p-4 font-mono text-xs leading-relaxed text-[#e6edf3]">
      {formattedJson}
    </pre>
  ) : (
    <pre className="max-h-72 overflow-auto whitespace-pre-wrap wrap-break-word p-4 text-sm leading-relaxed text-text-primary">
      {displayText || "(No text content — view raw for the full response.)"}
    </pre>
  );

  return (
    <div className="overflow-hidden rounded-xl border border-border-subtle">
      <div className="flex items-center justify-between gap-3 border-b border-border-subtle bg-bg-card-muted/50 px-4 py-2.5">
        <div className="min-w-0">
          <p className="text-sm font-medium text-text-primary">Response</p>
          <p className="text-xs text-text-muted">{tokenLabel}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <CopyButton
            value={copyValue}
            label="Copy"
            className="rounded-md border border-border-subtle px-2.5 py-1 text-xs text-text-secondary hover:bg-bg-card-muted hover:text-text-primary"
          />
          <button
            type="button"
            onClick={() => setShowRaw((current) => !current)}
            className={
              showRaw
                ? "inline-flex items-center gap-1.5 rounded-md border border-accent-blue/30 bg-accent-blue-bg px-2.5 py-1 text-xs font-medium text-accent-blue"
                : "inline-flex items-center gap-1.5 rounded-md border border-border-subtle px-2.5 py-1 text-xs text-text-secondary hover:bg-bg-card-muted hover:text-text-primary"
            }
          >
            <CodeIcon size={14} />
            {showRaw ? "Hide raw" : "View raw"}
          </button>
        </div>
      </div>
      {bodyContent}
    </div>
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

  const responseText = useMemo(
    () => extractResponseDisplayText(outputPayload),
    [outputPayload],
  );
  const responseJson = useMemo(
    () => (outputPayload ? formatPayloadJson(outputPayload) : ""),
    [outputPayload],
  );

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
    <div className="space-y-4">
      <div className="flex flex-col gap-4 rounded-xl border border-border-subtle bg-bg-card-muted/40 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <p className="text-sm font-medium text-text-primary">Captured I/O</p>
          <p className="text-sm text-text-secondary">
            {formatInteger(row.inputTokens)} prompt tokens · {formatInteger(row.outputTokens)}{" "}
            completion tokens
          </p>
        </div>
        {inputPayload ? (
          <Button
            type="button"
            size="lg"
            variant="outline"
            className="h-10 shrink-0 rounded-lg px-5 text-sm"
            onClick={onOpenInspector}
          >
            Inspect request messages
          </Button>
        ) : null}
      </div>

      <IoResponseBlock
        tokenLabel={`${formatInteger(row.outputTokens)} completion tokens`}
        payload={outputPayload}
        displayText={responseText}
        formattedJson={responseJson}
        missingLabel="No response body stored for this request."
      />
    </div>
  );
}

export function RequestDetailSheet({
  row,
  open,
  isLoading,
  errorMessage,
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
              {formatTimestamp(row.timestamp, "detail")} · {row.endpoint}
            </SheetDescription>
          ) : null}
        </SheetHeader>

        {isLoading ? (
          <div className="px-5 py-8 text-sm text-text-secondary">
            Loading request details...
          </div>
        ) : errorMessage ? (
          <div className="mx-5 my-5 rounded-xl border border-accent-red/20 bg-accent-red-bg px-4 py-3 text-sm text-accent-red">
            {errorMessage}
          </div>
        ) : row ? (
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
                <DetailMetric label="Estimated cost" value={formatCost(row.costUsd, 4)} />
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
