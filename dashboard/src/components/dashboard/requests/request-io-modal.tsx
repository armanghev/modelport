"use client";

import { useEffect, useMemo, useState } from "react";

import {
  CaretLeftIcon,
  CaretRightIcon,
  CodeIcon,
  TerminalWindowIcon,
  XIcon,
} from "@phosphor-icons/react";

import { Button } from "@/components/ui/button";
import { CopyButton } from "@/components/ui/copy-button";
import { Input } from "@/components/ui/input";
import type { RequestRow } from "@/lib/mock-dashboard-data";
import {
  buildIoInspectorData,
  buildMessageInspectorJson,
  buildPromptMessagesJson,
  formatToolCallSummary,
  getRoleAccentClass,
  getRoleBarClass,
  getRoleLabel,
  INSPECTOR_LEGEND_ROLES,
  type ParsedIoMessage,
  type ParsedIoToolCall,
  type RoleTokenSummary,
} from "@/lib/request-io";

interface RequestIoModalProps {
  row: RequestRow | null;
  open: boolean;
  onClose: () => void;
}

type InspectorView = "messages" | "raw";

function formatInteger(value: number): string {
  return value.toLocaleString("en-US");
}

function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

function formatCost(value: number): string {
  return `$${value.toFixed(4)}`;
}

function RoleBadge({
  role,
  label,
}: {
  role: ParsedIoMessage["role"];
  label: string;
}) {
  return (
    <span
      className={`inline-flex items-center justify-center rounded-md px-2 py-1 text-xs font-medium ${getRoleAccentClass(role)}`}
    >
      {label}
    </span>
  );
}

function MessagePreviewCell({ message }: { message: ParsedIoMessage }) {
  const toolCallSummary = formatToolCallSummary(message.toolCalls);

  return (
    <div className="max-w-[220px] space-y-1">
      <p className="truncate text-text-secondary">{message.preview}</p>
      {toolCallSummary ? (
        <p className="flex items-center gap-1 truncate text-xs text-text-muted">
          <TerminalWindowIcon size={12} className="shrink-0" />
          <span className="truncate">{toolCallSummary}</span>
        </p>
      ) : null}
    </div>
  );
}

function ToolCallCard({ toolCall }: { toolCall: ParsedIoToolCall }) {
  return (
    <div className="overflow-hidden rounded-xl border border-border-subtle">
      <div className="flex items-center gap-2 border-b border-border-subtle bg-bg-card-muted px-3 py-2.5">
        <TerminalWindowIcon size={14} className="text-text-muted" />
        <span className="text-sm font-medium text-text-primary">
          {toolCall.name}
        </span>
      </div>
      <div className="bg-[#1f2328]">
        <div className="flex items-center justify-between border-b border-white/10 px-3 py-1.5">
          <span className="text-xs text-text-muted">json</span>
          <CopyButton
            value={toolCall.inputJson}
            label="Copy"
            className="text-xs hover:text-text-primary"
          />
        </div>
        <pre className="overflow-x-auto whitespace-pre-wrap wrap-break-word p-3 font-mono text-xs leading-relaxed text-[#e6edf3]">
          {toolCall.inputJson}
        </pre>
      </div>
    </div>
  );
}

function ToolCallsSection({ toolCalls }: { toolCalls: ParsedIoToolCall[] }) {
  if (toolCalls.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3">
      <p className="text-xs font-semibold tracking-wide text-text-muted uppercase">
        Tool calls ({toolCalls.length})
      </p>
      <div className="space-y-3">
        {toolCalls.map((toolCall) => (
          <ToolCallCard key={toolCall.id} toolCall={toolCall} />
        ))}
      </div>
    </div>
  );
}

function formatCostDisplay(value: number): string {
  if (value < 0.00005) {
    return "$0";
  }
  return formatCost(value);
}

function TokenDistributionBar({
  messages,
  totalTokens,
}: {
  messages: ParsedIoMessage[];
  totalTokens: number;
}) {
  if (messages.length === 0 || totalTokens <= 0) {
    return (
      <div className="rounded-md border border-border-subtle bg-bg-card-muted/40 p-1">
        <div className="h-8 rounded-sm bg-bg-card-muted" aria-hidden="true" />
      </div>
    );
  }

  return (
    <div className="rounded-md border border-border-subtle bg-bg-card-muted/40 p-1">
      <div className="flex h-8 overflow-hidden rounded-sm bg-bg-card-muted">
        {messages.map((message) => {
          const width = (message.calibratedTokens / totalTokens) * 100;
          if (width <= 0) {
            return null;
          }
          return (
            <div
              key={message.id}
              className={`h-full min-w-[3px] ${getRoleBarClass(message.role)}`}
              style={{
                width: `${Math.max(width, message.calibratedTokens > 0 ? 0.35 : 0)}%`,
              }}
              title={`${message.roleLabel}: ${formatInteger(message.calibratedTokens)} tokens`}
            />
          );
        })}
      </div>
    </div>
  );
}

function InspectorTokenStats({
  messageCount,
  promptTokens,
  inputTotal,
  costUsd,
  model,
  promptMessages,
  roleSummaries,
}: {
  messageCount: number;
  promptTokens: number;
  totalTokens: number;
  inputTotal: number;
  outputTotal: number;
  costUsd: number;
  model: string;
  promptMessages: ParsedIoMessage[];
  roleSummaries: RoleTokenSummary[];
}) {
  return (
    <div className="flex flex-col border-b border-border-subtle lg:flex-row">
      <div className="min-w-0 flex-1 px-4 py-3">
        <div className="mb-2 flex items-center justify-between gap-4 text-sm">
          <span className="font-medium text-text-primary">
            Tokens per message
          </span>
          <span className="shrink-0 tabular-nums text-text-secondary">
            {formatInteger(messageCount)} of {formatInteger(messageCount)} msgs
            · {formatInteger(promptTokens)} of {formatInteger(promptTokens)}{" "}
            tokens
          </span>
        </div>
        <TokenDistributionBar
          messages={promptMessages}
          totalTokens={promptTokens}
        />
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-secondary">
          {INSPECTOR_LEGEND_ROLES.map((role) => (
            <span key={role} className="inline-flex items-center gap-1.5">
              <span
                className={`h-2 w-2 rounded-full ${getRoleBarClass(role)}`}
              />
              {getRoleLabel(role)}
            </span>
          ))}
        </div>
      </div>

      <div className="border-t border-border-subtle px-4 py-3 lg:w-70 lg:shrink-0 lg:border-t-0 lg:border-l">
        <div className="space-y-2 text-sm">
          <div className="flex items-center justify-between gap-4">
            <span className="text-text-secondary">Cached</span>
            <span className="tabular-nums text-text-primary">0 (0.0%)</span>
          </div>
          <div className="flex items-center justify-between gap-4">
            <span className="text-text-secondary">Prompt</span>
            <span className="tabular-nums text-text-primary">
              {formatInteger(inputTotal)} (100.0%)
            </span>
          </div>
          <div className="flex items-center justify-between gap-4">
            <span className="text-text-secondary">Cost</span>
            <span className="tabular-nums text-text-primary">
              {formatCostDisplay(costUsd)}
            </span>
          </div>
          <div className="border-t border-border-subtle pt-2">
            <div className="flex items-center justify-between gap-2">
              <span className="shrink-0 text-text-secondary">Model</span>
              <span className="flex min-w-0 items-center gap-1.5">
                <span className="truncate font-medium text-text-primary">
                  {model}
                </span>
                <CopyButton
                  value={model}
                  aria-label="Copy model name"
                  className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded hover:bg-bg-card-muted"
                />
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="border-t border-border-subtle px-4 py-3 lg:w-60 lg:shrink-0 lg:border-t-0 lg:border-l">
        <div className="mb-2 grid grid-cols-[minmax(0,1fr)_4.5rem_3rem] gap-2 text-xs text-text-secondary">
          <span>By role</span>
          <span className="text-right">Tokens</span>
          <span className="text-right">%</span>
        </div>
        <div className="space-y-2">
          {roleSummaries.map((summary) => (
            <div
              key={summary.role}
              className="grid grid-cols-[minmax(0,1fr)_4.5rem_3rem] items-center gap-2"
            >
              <RoleBadge role={summary.role} label={summary.roleLabel} />
              <span className="text-right text-sm font-medium tabular-nums text-text-primary">
                {formatInteger(summary.tokens)}
              </span>
              <span className="text-right text-sm tabular-nums text-text-secondary">
                {formatPercent(summary.percent)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function InlineJsonBlock({ json }: { json: string }) {
  return (
    <div className="overflow-hidden rounded-xl border border-border-subtle bg-[#1f2328]">
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-1.5">
        <span className="text-xs text-text-muted">json</span>
      </div>
      <pre className="max-h-[min(420px,50vh)] overflow-auto whitespace-pre-wrap wrap-break-word p-4 font-mono text-xs leading-relaxed text-[#e6edf3]">
        {json}
      </pre>
    </div>
  );
}

function JsonViewerPanel({
  json,
  messageCount,
  tokenCount,
}: {
  json: string;
  messageCount: number;
  tokenCount: number;
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-hidden p-5">
        <div className="flex h-full min-h-[280px] flex-col overflow-hidden rounded-xl border border-border-subtle bg-[#1f2328]">
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-2">
            <span className="text-xs text-text-muted">json</span>
            <CopyButton
              value={json}
              label="Copy"
              className="text-xs hover:text-text-primary"
            />
          </div>
          <pre className="min-h-0 flex-1 overflow-auto whitespace-pre-wrap wrap-break-word p-4 font-mono text-xs leading-relaxed text-[#e6edf3]">
            {json}
          </pre>
        </div>
      </div>
      <div className="flex items-center justify-between border-t border-border-subtle px-5 py-2 text-xs text-text-muted">
        <span className="inline-flex items-center gap-1.5">
          <span
            className="h-1.5 w-1.5 rounded-full bg-accent-green"
            aria-hidden="true"
          />
          Loaded
        </span>
        <span>
          {formatInteger(messageCount)} message{messageCount === 1 ? "" : "s"} ·{" "}
          {formatInteger(tokenCount)} tokens
        </span>
      </div>
    </div>
  );
}

export function RequestIoModal({ row, open, onClose }: RequestIoModalProps) {
  const [view, setView] = useState<InspectorView>("messages");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(
    null,
  );
  const [showMessageRaw, setShowMessageRaw] = useState(false);

  const inspector = useMemo(
    () => (row ? buildIoInspectorData(row) : null),
    [row],
  );

  const promptMessagesJson = useMemo(
    () => (inspector ? buildPromptMessagesJson(inspector.rawInput) : "[]"),
    [inspector],
  );

  const rawJsonMessageCount = useMemo(() => {
    try {
      const parsed: unknown = JSON.parse(promptMessagesJson);
      return Array.isArray(parsed) ? parsed.length : 0;
    } catch {
      return 0;
    }
  }, [promptMessagesJson]);

  const filteredMessages = useMemo(() => {
    if (!inspector) {
      return [];
    }
    const normalized = searchQuery.trim().toLowerCase();
    const promptMessages = inspector.inputMessages;
    if (!normalized) {
      return promptMessages;
    }
    return promptMessages.filter((message) =>
      [
        message.roleLabel,
        message.preview,
        message.textContent,
        ...message.toolCalls.map((call) => call.name),
      ]
        .join(" ")
        .toLowerCase()
        .includes(normalized),
    );
  }, [inspector, searchQuery]);

  const selectedMessage = useMemo(() => {
    if (filteredMessages.length === 0) {
      return null;
    }
    if (selectedMessageId) {
      return (
        filteredMessages.find((message) => message.id === selectedMessageId) ??
        filteredMessages[0]
      );
    }
    return filteredMessages[0];
  }, [filteredMessages, selectedMessageId]);

  const selectedIndex = selectedMessage
    ? filteredMessages.findIndex((message) => message.id === selectedMessage.id)
    : -1;

  const selectedMessageJson = useMemo(
    () => (selectedMessage ? buildMessageInspectorJson(selectedMessage) : ""),
    [selectedMessage],
  );

  useEffect(() => {
    if (!open) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) {
      setView("messages");
      setSearchQuery("");
      setSelectedMessageId(null);
      setShowMessageRaw(false);
    }
  }, [open]);

  useEffect(() => {
    if (filteredMessages.length === 0) {
      setSelectedMessageId(null);
      return;
    }
    if (
      !selectedMessageId ||
      !filteredMessages.some((message) => message.id === selectedMessageId)
    ) {
      setSelectedMessageId(filteredMessages[0]?.id ?? null);
    }
  }, [filteredMessages, selectedMessageId]);

  if (!open || !row || !inspector) {
    return null;
  }

  const promptMessages = inspector.inputMessages;
  const visibleMessages = filteredMessages;
  const messageCount = promptMessages.length;
  const totalTokens = row.totalTokens;
  const promptTokens = inspector.inputTotal;

  const goToMessage = (direction: -1 | 1) => {
    if (selectedIndex < 0 || filteredMessages.length === 0) {
      return;
    }
    const nextIndex =
      (selectedIndex + direction + filteredMessages.length) %
      filteredMessages.length;
    setSelectedMessageId(filteredMessages[nextIndex]?.id ?? null);
  };

  const tokenStats = (
    <InspectorTokenStats
      messageCount={messageCount}
      promptTokens={promptTokens}
      totalTokens={totalTokens}
      inputTotal={inspector.inputTotal}
      outputTotal={inspector.outputTotal}
      costUsd={row.costUsd}
      model={row.model}
      promptMessages={promptMessages}
      roleSummaries={inspector.roleSummaries}
    />
  );

  return (
    <div
      className="fixed inset-0 z-100 flex items-center justify-center overflow-hidden overscroll-none bg-black/35 p-4 backdrop-blur-sm"
      onPointerDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
      role="presentation"
    >
      <div
        className="card-surface flex max-h-[92vh] h-full w-full max-w-full flex-col overflow-hidden"
        onPointerDown={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`I/O details for request ${row.id}`}
      >
        <div className="flex items-start justify-between gap-4 border-b border-border-subtle px-5 py-4">
          <div className="min-w-0 space-y-1">
            <p className="text-sm text-text-secondary">I/O inspector</p>
            <h2 className="truncate text-xl font-semibold text-text-primary">
              Prompt {formatInteger(inspector.inputTotal)} tokens ·{" "}
              {promptMessages.length} message
              {promptMessages.length === 1 ? "" : "s"}
            </h2>
            <p className="text-sm text-text-secondary">
              {row.model} · {row.endpoint} · {formatInteger(totalTokens)} total
              tokens
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="inline-flex rounded-lg border border-border-subtle bg-bg-card-muted p-0.5">
              <button
                type="button"
                onClick={() => setView("messages")}
                className={
                  view === "messages"
                    ? "rounded-md bg-bg-card px-3 py-1.5 text-xs font-medium text-text-primary shadow-sm"
                    : "rounded-md px-3 py-1.5 text-xs text-text-secondary hover:text-text-primary"
                }
              >
                Messages
              </button>
              <button
                type="button"
                onClick={() => setView("raw")}
                className={
                  view === "raw"
                    ? "rounded-md bg-bg-card px-3 py-1.5 text-xs font-medium text-text-primary shadow-sm"
                    : "rounded-md px-3 py-1.5 text-xs text-text-secondary hover:text-text-primary"
                }
              >
                Raw JSON
              </button>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border-subtle text-text-muted hover:bg-bg-card-muted hover:text-text-primary"
              aria-label="Close I/O inspector"
            >
              <XIcon size={16} />
            </button>
          </div>
        </div>

        {inspector.parseWarnings.length > 0 ? (
          <div className="border-b border-border-subtle bg-accent-amber/10 px-5 py-3 text-sm text-accent-amber">
            {inspector.parseWarnings.join(" ")}
          </div>
        ) : null}

        {view === "messages" ? (
          <>
            {tokenStats}

            {!inspector.hasStructuredMessages ? (
              <div className="flex flex-1 flex-col items-center justify-center px-6 py-16 text-center">
                <p className="text-sm font-medium text-text-primary">
                  Could not parse structured messages
                </p>
                <p className="mt-2 max-w-md text-sm text-text-secondary">
                  This request has stored payloads, but they do not match a
                  known chat format. Switch to Raw JSON to inspect the captured
                  bodies.
                </p>
                <Button
                  type="button"
                  variant="outline"
                  className="mt-4 h-10 rounded-lg px-4 text-sm"
                  onClick={() => setView("raw")}
                >
                  View raw JSON
                </Button>
              </div>
            ) : (
              <div className="grid min-h-0 flex-1 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1.4fr)]">
                <div className="flex min-h-0 flex-col border-b border-border-subtle lg:border-r lg:border-b-0">
                  <div className="border-b border-border-subtle px-4 py-3">
                    <Input
                      type="search"
                      placeholder="Search messages..."
                      value={searchQuery}
                      onChange={(event) => setSearchQuery(event.target.value)}
                      className="h-10 rounded-lg border-border-default text-sm"
                    />
                  </div>
                  <div className="min-h-0 flex-1 overflow-auto">
                    <table className="w-full border-collapse text-left text-sm">
                      <thead className="sticky top-0 z-10 bg-bg-card text-xs text-text-secondary">
                        <tr className="border-b border-border-subtle">
                          <th className="px-4 py-2 font-medium">#</th>
                          <th className="px-4 py-2 font-medium">Role</th>
                          <th className="px-4 py-2 font-medium">Preview</th>
                          <th className="px-4 py-2 font-medium text-right">
                            Tokens
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {visibleMessages.map((message) => {
                          const isSelected = selectedMessage?.id === message.id;
                          return (
                            <tr
                              key={message.id}
                              onClick={() => setSelectedMessageId(message.id)}
                              className={
                                isSelected
                                  ? "cursor-pointer border-t border-border-subtle bg-bg-card-muted"
                                  : "cursor-pointer border-t border-border-subtle hover:bg-bg-card-muted/70"
                              }
                            >
                              <td className="px-4 py-3 text-text-muted">
                                {message.index}
                              </td>
                              <td className="px-4 py-3">
                                <RoleBadge
                                  role={message.role}
                                  label={message.roleLabel}
                                />
                              </td>
                              <td className="px-4 py-3">
                                <MessagePreviewCell message={message} />
                              </td>
                              <td className="px-4 py-3 text-right font-medium text-text-primary">
                                {formatInteger(message.calibratedTokens)}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <div className="border-t border-border-subtle px-4 py-2 text-xs text-text-muted">
                    Loaded
                  </div>
                </div>

                <div className="flex min-h-0 flex-col">
                  <div className="flex items-center justify-between gap-3 border-b border-border-subtle px-4 py-3">
                    <div className="flex min-w-0 items-center gap-2">
                      {selectedMessage ? (
                        <RoleBadge
                          role={selectedMessage.role}
                          label={selectedMessage.roleLabel}
                        />
                      ) : null}
                      <span className="truncate text-sm text-text-secondary">
                        {selectedMessage
                          ? `Message ${selectedIndex + 1} of ${filteredMessages.length}`
                          : "No message selected"}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        aria-label="Previous message"
                        disabled={filteredMessages.length <= 1}
                        onClick={() => goToMessage(-1)}
                        className="inline-flex h-6 w-6 items-center justify-center rounded-md border border-border-subtle text-text-muted disabled:opacity-40"
                      >
                        <CaretLeftIcon size={10} />
                      </button>
                      <button
                        type="button"
                        aria-label="Next message"
                        disabled={filteredMessages.length <= 1}
                        onClick={() => goToMessage(1)}
                        className="inline-flex h-6 w-6 items-center justify-center rounded-md border border-border-subtle text-text-muted disabled:opacity-40"
                      >
                        <CaretRightIcon size={10} />
                      </button>
                    </div>
                  </div>
                  <div className="flex items-center justify-between border-b border-border-subtle px-4 py-2 text-xs text-text-muted">
                    <p>Content Preview</p>
                    <div className="flex items-center gap-2">
                      <CopyButton
                        value={
                          showMessageRaw
                            ? selectedMessageJson
                            : (selectedMessage?.textContent ?? "")
                        }
                        label="Copy"
                        disabled={!selectedMessage}
                        className="rounded-md border border-border-subtle px-2.5 py-1 text-xs text-text-secondary hover:bg-bg-card-muted hover:text-text-primary disabled:opacity-40"
                      />
                      <button
                        type="button"
                        disabled={!selectedMessage}
                        className={
                          showMessageRaw
                            ? "inline-flex items-center gap-1.5 rounded-md border border-accent-blue/30 bg-accent-blue-bg px-2.5 py-1 text-xs font-medium text-accent-blue disabled:opacity-40"
                            : "inline-flex items-center gap-1.5 rounded-md border border-border-subtle px-2.5 py-1 text-xs text-text-secondary hover:bg-bg-card-muted hover:text-text-primary disabled:opacity-40"
                        }
                        onClick={() => setShowMessageRaw((current) => !current)}
                      >
                        <CodeIcon size={14} />
                        {showMessageRaw ? "Hide raw" : "View raw"}
                      </button>
                    </div>
                  </div>

                  <div className="min-h-0 flex-1 overflow-auto p-4">
                    {selectedMessage ? (
                      showMessageRaw ? (
                        <InlineJsonBlock json={selectedMessageJson} />
                      ) : (
                        <div className="space-y-4">
                          {selectedMessage.textContent ? (
                            <pre className="whitespace-pre-wrap rounded-xl border border-border-subtle bg-[#1f2328] p-4 font-mono text-xs leading-relaxed text-[#e6edf3]">
                              {selectedMessage.textContent}
                            </pre>
                          ) : selectedMessage.toolCalls.length === 0 ? (
                            <pre className="whitespace-pre-wrap rounded-xl border border-border-subtle bg-[#1f2328] p-4 font-mono text-xs leading-relaxed text-[#e6edf3]">
                              (empty)
                            </pre>
                          ) : null}
                          <ToolCallsSection toolCalls={selectedMessage.toolCalls} />
                        </div>
                      )
                    ) : (
                      <div className="flex h-full items-center justify-center text-sm text-text-secondary">
                        Select a message to preview its content.
                      </div>
                    )}
                  </div>

                  <div className="border-t border-border-subtle px-4 py-2 text-xs text-text-muted">
                    {formatInteger(filteredMessages.length)} message
                    {filteredMessages.length === 1 ? "" : "s"} ·{" "}
                    {formatInteger(
                      filteredMessages.reduce(
                        (sum, message) => sum + message.calibratedTokens,
                        0,
                      ),
                    )}{" "}
                    tokens
                  </div>
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="flex min-h-0 flex-1 flex-col">
            {tokenStats}
            {inspector.rawInput ? (
              <JsonViewerPanel
                json={promptMessagesJson}
                messageCount={rawJsonMessageCount}
                tokenCount={promptTokens}
              />
            ) : (
              <div className="flex flex-1 items-center justify-center px-6 py-16 text-sm text-text-secondary">
                No request body stored for this request.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
