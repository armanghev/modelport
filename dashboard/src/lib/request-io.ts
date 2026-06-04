import type { RequestRow } from "@/lib/mock-dashboard-data";

export type IoMessageRole = "system" | "user" | "assistant" | "tool" | "unknown";
export type IoMessageSource = "input" | "output";

export interface ParsedIoToolCall {
  id: string;
  name: string;
  input: unknown;
  inputJson: string;
}

export interface ParsedIoMessage {
  id: string;
  index: number;
  source: IoMessageSource;
  role: IoMessageRole;
  roleLabel: string;
  content: string;
  textContent: string;
  toolCalls: ParsedIoToolCall[];
  preview: string;
  raw: unknown;
  estimatedTokens: number;
  calibratedTokens: number;
}

export interface RoleTokenSummary {
  role: IoMessageRole;
  roleLabel: string;
  messageCount: number;
  tokens: number;
  percent: number;
}

export interface IoInspectorData {
  inputMessages: ParsedIoMessage[];
  outputMessages: ParsedIoMessage[];
  allMessages: ParsedIoMessage[];
  inputTotal: number;
  outputTotal: number;
  roleSummaries: RoleTokenSummary[];
  parseWarnings: string[];
  rawInput: string | null;
  rawOutput: string | null;
  hasStructuredMessages: boolean;
}

const ROLE_LABELS: Record<IoMessageRole, string> = {
  system: "System",
  user: "User",
  assistant: "Assistant",
  tool: "Tool",
  unknown: "Unknown",
};

export function estimateTokenCount(text: string): number {
  const normalized = text.trim();
  if (!normalized) {
    return 0;
  }
  return Math.max(1, Math.round(normalized.length / 4));
}

function normalizeRole(value: unknown): IoMessageRole {
  if (typeof value !== "string") {
    return "unknown";
  }
  const lowered = value.toLowerCase();
  if (lowered === "system") return "system";
  if (lowered === "user") return "user";
  if (lowered === "assistant") return "assistant";
  if (lowered === "tool" || lowered === "function") return "tool";
  return "unknown";
}

function truncatePreview(text: string, maxLength = 72): string {
  const singleLine = text.replace(/\s+/g, " ").trim();
  if (singleLine.length <= maxLength) {
    return singleLine;
  }
  return `${singleLine.slice(0, maxLength - 1)}…`;
}

function extractTextFromContent(content: unknown): string {
  if (typeof content === "string") {
    return content;
  }

  if (!Array.isArray(content)) {
    if (content && typeof content === "object") {
      const record = content as Record<string, unknown>;
      if (typeof record.text === "string") {
        return record.text;
      }
    }
    return "";
  }

  const parts: string[] = [];
  for (const block of content) {
    if (typeof block === "string") {
      parts.push(block);
      continue;
    }
    if (!block || typeof block !== "object") {
      continue;
    }
    const record = block as Record<string, unknown>;
    if (record.type === "text" && typeof record.text === "string") {
      parts.push(record.text);
      continue;
    }
    if (record.type === "tool_result" && typeof record.content === "string") {
      parts.push(record.content);
      continue;
    }
    if (record.type === "tool_use" && typeof record.name === "string") {
      parts.push(`[tool_use: ${record.name}]`);
      continue;
    }
    if (typeof record.content === "string") {
      parts.push(record.content);
    }
  }

  return parts.join("\n\n");
}

function formatToolInputJson(input: unknown): string {
  try {
    return JSON.stringify(input ?? {}, null, 2);
  } catch {
    return String(input ?? "");
  }
}

function extractTextOnlyFromRaw(raw: unknown): string {
  if (!raw || typeof raw !== "object") {
    return "";
  }

  const record = raw as Record<string, unknown>;
  const content = record.content;

  if (typeof content === "string") {
    return content;
  }

  if (!Array.isArray(content)) {
    if (content && typeof content === "object") {
      const block = content as Record<string, unknown>;
      if (block.type === "text" && typeof block.text === "string") {
        return block.text;
      }
    }
    return "";
  }

  const parts: string[] = [];
  for (const block of content) {
    if (typeof block === "string") {
      parts.push(block);
      continue;
    }
    if (!block || typeof block !== "object") {
      continue;
    }
    const item = block as Record<string, unknown>;
    if (item.type === "text" && typeof item.text === "string") {
      parts.push(item.text);
    }
  }

  return parts.join("\n\n");
}

function extractToolCallsFromRaw(raw: unknown): ParsedIoToolCall[] {
  if (!raw || typeof raw !== "object") {
    return [];
  }

  const record = raw as Record<string, unknown>;
  const calls: ParsedIoToolCall[] = [];

  const content = record.content;
  if (Array.isArray(content)) {
    for (const block of content) {
      if (!block || typeof block !== "object") {
        continue;
      }
      const item = block as Record<string, unknown>;
      if (item.type !== "tool_use" || typeof item.name !== "string") {
        continue;
      }
      calls.push({
        id: typeof item.id === "string" ? item.id : `tool-${calls.length + 1}`,
        name: item.name,
        input: item.input ?? {},
        inputJson: formatToolInputJson(item.input),
      });
    }
  }

  const toolCalls = record.tool_calls;
  if (Array.isArray(toolCalls)) {
    for (const toolCall of toolCalls) {
      if (!toolCall || typeof toolCall !== "object") {
        continue;
      }
      const item = toolCall as Record<string, unknown>;
      const fn =
        item.function && typeof item.function === "object"
          ? (item.function as Record<string, unknown>)
          : null;
      const name = typeof fn?.name === "string" ? fn.name : "unknown";
      let input: unknown = {};
      if (typeof fn?.arguments === "string") {
        try {
          input = JSON.parse(fn.arguments);
        } catch {
          input = fn.arguments;
        }
      }
      calls.push({
        id: typeof item.id === "string" ? item.id : `tool-${calls.length + 1}`,
        name,
        input,
        inputJson: formatToolInputJson(input),
      });
    }
  }

  return calls;
}

export function formatToolCallSummary(toolCalls: ParsedIoToolCall[]): string | null {
  if (toolCalls.length === 0) {
    return null;
  }
  if (toolCalls.length === 1) {
    return `1 tool call · ${toolCalls[0].name}`;
  }
  return `${toolCalls.length} tool calls · ${toolCalls.map((call) => call.name).join(", ")}`;
}

function extractToolResultContent(block: Record<string, unknown>): string {
  return extractTextFromContent(block.content);
}

function expandInputMessage(
  item: Record<string, unknown>,
): Array<{ role: IoMessageRole; content: string; raw: unknown }> {
  const role = normalizeRole(item.role);
  const content = item.content;

  if (typeof content === "string") {
    return [{ role, content, raw: item }];
  }

  if (!Array.isArray(content)) {
    return [{ role, content: extractTextFromContent(content), raw: item }];
  }

  if (role === "user") {
    const results: Array<{ role: IoMessageRole; content: string; raw: unknown }> = [];
    let textParts: string[] = [];

    const flushUserText = () => {
      if (textParts.length === 0) {
        return;
      }
      results.push({
        role: "user",
        content: textParts.join("\n\n"),
        raw: item,
      });
      textParts = [];
    };

    for (const block of content) {
      if (!block || typeof block !== "object") {
        continue;
      }
      const record = block as Record<string, unknown>;
      if (record.type === "tool_result") {
        flushUserText();
        results.push({
          role: "tool",
          content: extractToolResultContent(record),
          raw: block,
        });
        continue;
      }
      if (record.type === "text" && typeof record.text === "string") {
        textParts.push(record.text);
        continue;
      }
      if (typeof record.content === "string") {
        textParts.push(record.content);
      }
    }

    flushUserText();
    return results.length > 0 ? results : [{ role: "user", content: "", raw: item }];
  }

  return [{ role, content: extractTextFromContent(content), raw: item }];
}

function createMessage(
  source: IoMessageSource,
  index: number,
  role: IoMessageRole,
  content: string,
  raw: unknown,
): ParsedIoMessage {
  const toolCalls = extractToolCallsFromRaw(raw);
  const textContent =
    toolCalls.length > 0 || role === "assistant" ? extractTextOnlyFromRaw(raw) || content : content;
  const estimatedTokens = estimateTokenCount(textContent || content);
  return {
    id: `${source}-${index}`,
    index,
    source,
    role,
    roleLabel: ROLE_LABELS[role],
    content: textContent || content,
    textContent: textContent || content,
    toolCalls,
    preview: truncatePreview(textContent || content || "(empty)"),
    raw,
    estimatedTokens,
    calibratedTokens: estimatedTokens,
  };
}

function parseJsonPayload(payload: string | null | undefined): { data: unknown; error?: string } {
  if (!payload) {
    return { data: null };
  }
  try {
    return { data: JSON.parse(payload) };
  } catch {
    return { data: null, error: "Could not parse payload JSON." };
  }
}

function pushMessage(
  messages: ParsedIoMessage[],
  source: IoMessageSource,
  role: IoMessageRole,
  content: string,
  raw: unknown,
) {
  messages.push(createMessage(source, messages.length + 1, role, content, raw));
}

function parseInputPayload(data: unknown): ParsedIoMessage[] {
  const messages: ParsedIoMessage[] = [];
  if (!data || typeof data !== "object") {
    return messages;
  }

  const record = data as Record<string, unknown>;

  if (record.system !== undefined) {
    const systemText =
      typeof record.system === "string"
        ? record.system
        : extractTextFromContent(record.system);
    pushMessage(messages, "input", "system", systemText, record.system);
  }

  const rawMessages = record.messages;
  if (Array.isArray(rawMessages)) {
    for (const item of rawMessages) {
      if (!item || typeof item !== "object") {
        continue;
      }
      const message = item as Record<string, unknown>;
      for (const expanded of expandInputMessage(message)) {
        pushMessage(messages, "input", expanded.role, expanded.content, expanded.raw);
      }
    }
  }

  return messages;
}

function parseOutputPayload(data: unknown): ParsedIoMessage[] {
  const messages: ParsedIoMessage[] = [];
  if (!data || typeof data !== "object") {
    return messages;
  }

  const record = data as Record<string, unknown>;

  if (record.error && typeof record.error === "object") {
    const error = record.error as Record<string, unknown>;
    const message =
      typeof error.message === "string" ? error.message : JSON.stringify(error, null, 2);
    pushMessage(messages, "output", "unknown", message, record.error);
    return messages;
  }

  if (Array.isArray(record.content)) {
    const role = normalizeRole(record.role ?? "assistant");
    const content = extractTextFromContent(record.content);
    pushMessage(messages, "output", role, content, record);
    return messages;
  }

  const choices = record.choices;
  if (Array.isArray(choices)) {
    for (const choice of choices) {
      if (!choice || typeof choice !== "object") {
        continue;
      }
      const choiceRecord = choice as Record<string, unknown>;
      const message = choiceRecord.message;
      if (message && typeof message === "object") {
        const messageRecord = message as Record<string, unknown>;
        const role = normalizeRole(messageRecord.role ?? "assistant");
        const content = extractTextFromContent(messageRecord.content);
        pushMessage(messages, "output", role, content, message);
        continue;
      }
      const delta = choiceRecord.delta;
      if (delta && typeof delta === "object") {
        const deltaRecord = delta as Record<string, unknown>;
        const role = normalizeRole(deltaRecord.role ?? "assistant");
        const content = extractTextFromContent(deltaRecord.content);
        if (content) {
          pushMessage(messages, "output", role, content, delta);
        }
      }
    }
  }

  if (messages.length === 0 && typeof record.content === "string") {
    pushMessage(messages, "output", "assistant", record.content, record);
  }

  return messages;
}

export function calibrateTokens(
  messages: ParsedIoMessage[],
  targetTotal: number,
): ParsedIoMessage[] {
  if (messages.length === 0) {
    return [];
  }

  if (targetTotal <= 0) {
    return messages.map((message) => ({ ...message, calibratedTokens: 0 }));
  }

  const estimatedSum = messages.reduce((sum, message) => sum + message.estimatedTokens, 0);

  if (estimatedSum <= 0) {
    const even = Math.floor(targetTotal / messages.length);
    let remainder = targetTotal - even * messages.length;
    return messages.map((message) => {
      const calibratedTokens = even + (remainder > 0 ? 1 : 0);
      if (remainder > 0) {
        remainder -= 1;
      }
      return { ...message, calibratedTokens };
    });
  }

  let allocated = 0;
  const calibrated = messages.map((message, index) => {
    if (index === messages.length - 1) {
      return {
        ...message,
        calibratedTokens: Math.max(0, targetTotal - allocated),
      };
    }
    const scaled = Math.round((message.estimatedTokens / estimatedSum) * targetTotal);
    const tokens = Math.max(message.estimatedTokens > 0 ? 1 : 0, scaled);
    allocated += tokens;
    return { ...message, calibratedTokens: tokens };
  });

  return calibrated;
}

function buildRoleSummaries(messages: ParsedIoMessage[]): RoleTokenSummary[] {
  const totals = new Map<IoMessageRole, { count: number; tokens: number }>();
  let grandTotal = 0;

  for (const message of messages) {
    const current = totals.get(message.role) ?? { count: 0, tokens: 0 };
    current.count += 1;
    current.tokens += message.calibratedTokens;
    totals.set(message.role, current);
    grandTotal += message.calibratedTokens;
  }

  return Array.from(totals.entries())
    .map(([role, value]) => ({
      role,
      roleLabel: ROLE_LABELS[role],
      messageCount: value.count,
      tokens: value.tokens,
      percent: grandTotal > 0 ? (value.tokens / grandTotal) * 100 : 0,
    }))
    .sort((left, right) => right.tokens - left.tokens);
}

export function buildIoInspectorData(row: RequestRow): IoInspectorData {
  const rawInput = row.io?.input ?? null;
  const rawOutput = row.io?.output ?? null;
  const parseWarnings: string[] = [];

  const parsedInput = parseJsonPayload(rawInput);
  const parsedOutput = parseJsonPayload(rawOutput);

  if (parsedInput.error) {
    parseWarnings.push(parsedInput.error);
  }
  if (parsedOutput.error) {
    parseWarnings.push(parsedOutput.error);
  }

  const inputMessages = calibrateTokens(
    parseInputPayload(parsedInput.data),
    row.inputTokens,
  );
  const outputMessages = calibrateTokens(
    parseOutputPayload(parsedOutput.data),
    row.outputTokens,
  );

  const allMessages = [...inputMessages, ...outputMessages];

  return {
    inputMessages,
    outputMessages,
    allMessages,
    inputTotal: row.inputTokens,
    outputTotal: row.outputTokens,
    roleSummaries: buildRoleSummaries(inputMessages),
    parseWarnings,
    rawInput,
    rawOutput,
    hasStructuredMessages: inputMessages.length > 0,
  };
}

function stripRedundantUpstreamFromPayload(data: unknown): unknown {
  if (data == null || typeof data !== "object") {
    return data;
  }

  if (Array.isArray(data)) {
    return data.map((item) => stripRedundantUpstreamFromPayload(item));
  }

  const record = { ...(data as Record<string, unknown>) };
  const error = record.error;
  if (error && typeof error === "object" && !Array.isArray(error)) {
    const { upstream: _upstream, code: _code, ...rest } = error as Record<
      string,
      unknown
    >;
    record.error = rest;
  }
  return record;
}

export function formatPayloadJson(payload: string | null): string {
  if (!payload) {
    return "";
  }
  try {
    const parsed = stripRedundantUpstreamFromPayload(JSON.parse(payload));
    return JSON.stringify(parsed, null, 2);
  } catch {
    return payload;
  }
}

const LEGACY_UPSTREAM_PREFIX = /^Upstream provider request failed:\s*/i;

function extractNestedUpstreamError(data: unknown): Record<string, unknown> | null {
  if (!data || typeof data !== "object") {
    return null;
  }

  if (Array.isArray(data)) {
    for (const item of data) {
      const nested = extractNestedUpstreamError(item);
      if (nested) {
        return nested;
      }
    }
    return null;
  }

  const record = data as Record<string, unknown>;
  const error = record.error;
  if (error && typeof error === "object" && !Array.isArray(error)) {
    return error as Record<string, unknown>;
  }

  return null;
}

function formatGatewayErrorDisplay(error: Record<string, unknown>): string {
  const lines: string[] = [];
  const message = error.message;

  if (typeof message === "string" && message.trim()) {
    if (LEGACY_UPSTREAM_PREFIX.test(message)) {
      const embedded = extractNestedUpstreamError(
        parseJsonPayload(message.replace(LEGACY_UPSTREAM_PREFIX, "").trim()).data,
      );
      const embeddedMessage = embedded?.message;
      lines.push(
        typeof embeddedMessage === "string" && embeddedMessage.trim()
          ? embeddedMessage.trim()
          : message.trim(),
      );
    } else {
      lines.push(message.trim());
    }
  }

  const meta: string[] = [];
  if (error.status_code != null) {
    meta.push(`Gateway HTTP ${error.status_code}`);
  }
  if (error.upstream_status_code != null) {
    meta.push(`Upstream HTTP ${error.upstream_status_code}`);
  }
  if (typeof error.status === "string" && error.status.trim()) {
    meta.push(error.status.trim());
  }

  if (meta.length > 0) {
    lines.push(meta.join(" · "));
  }

  return lines.join("\n\n");
}

/** Plain-text completion content for dashboard display (OpenAI, Anthropic, errors). */
export function extractResponseDisplayText(payload: string | null): string {
  if (!payload) {
    return "";
  }

  const parsed = parseJsonPayload(payload);
  if (parsed.error) {
    return "";
  }

  if (parsed.data && typeof parsed.data === "object") {
    const record = parsed.data as Record<string, unknown>;
    if (record.error && typeof record.error === "object" && !Array.isArray(record.error)) {
      return formatGatewayErrorDisplay(record.error as Record<string, unknown>);
    }
  }

  const messages = parseOutputPayload(parsed.data);
  const parts = messages
    .map((message) => message.textContent.trim())
    .filter((text) => text.length > 0);

  if (parts.length > 0) {
    return parts.join("\n\n");
  }

  if (parsed.data && typeof parsed.data === "object") {
    const record = parsed.data as Record<string, unknown>;
    if (typeof record.content === "string" && record.content.trim()) {
      return record.content.trim();
    }
  }

  return "";
}

export function buildPromptMessagesJson(rawInput: string | null): string {
  if (!rawInput) {
    return "[]";
  }

  try {
    const data = JSON.parse(rawInput) as Record<string, unknown>;
    const messages: unknown[] = [];

    if (data.system !== undefined) {
      messages.push({
        role: "system",
        content: data.system,
      });
    }

    if (Array.isArray(data.messages)) {
      messages.push(...data.messages);
    }

    if (messages.length === 0 && Array.isArray(data)) {
      return JSON.stringify(data, null, 2);
    }

    return JSON.stringify(messages, null, 2);
  } catch {
    return formatPayloadJson(rawInput);
  }
}

export function buildMessageInspectorJson(message: ParsedIoMessage): string {
  const { raw, role, toolCalls, textContent, content } = message;

  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    const record = raw as Record<string, unknown>;

    if (role === "assistant" && toolCalls.length > 0 && !Array.isArray(record.tool_calls)) {
      return JSON.stringify(
        {
          role: "assistant",
          content: textContent || null,
          tool_calls: toolCalls.map((call) => ({
            id: call.id,
            type: "function",
            function: {
              name: call.name,
              arguments:
                typeof call.input === "string"
                  ? call.input
                  : JSON.stringify(call.input ?? {}),
            },
          })),
        },
        null,
        2,
      );
    }

    return JSON.stringify(raw, null, 2);
  }

  if (typeof raw === "string") {
    return JSON.stringify({ role, content: raw }, null, 2);
  }

  return JSON.stringify(
    {
      role,
      content: textContent || content || null,
    },
    null,
    2,
  );
}

export function getRoleAccentClass(role: IoMessageRole): string {
  switch (role) {
    case "system":
      return "bg-violet-500/15 text-violet-400 dark:text-violet-300";
    case "user":
      return "bg-accent-green-bg text-accent-green";
    case "assistant":
      return "bg-accent-blue-bg text-accent-blue";
    case "tool":
      return "bg-accent-amber/10 text-accent-amber";
    default:
      return "bg-bg-card-muted text-text-muted";
  }
}

export function getRoleBarClass(role: IoMessageRole): string {
  switch (role) {
    case "system":
      return "bg-violet-500 dark:bg-violet-400";
    case "user":
      return "bg-accent-green";
    case "assistant":
      return "bg-accent-blue";
    case "tool":
      return "bg-accent-amber";
    default:
      return "bg-border-default";
  }
}

const LEGEND_ROLE_ORDER: IoMessageRole[] = ["system", "user", "assistant", "tool"];

export const INSPECTOR_LEGEND_ROLES = LEGEND_ROLE_ORDER;

export function getRoleLabel(role: IoMessageRole): string {
  return ROLE_LABELS[role];
}
