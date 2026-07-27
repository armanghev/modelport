const TIMESTAMP_STYLES = {
  default: {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  },
  table: {
    month: "2-digit",
    day: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  },
  detail: {
    month: "2-digit",
    day: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  },
  provider: {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  },
  catalog: {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  },
} as const satisfies Record<string, Intl.DateTimeFormatOptions>;

export function formatInteger(value: number): string {
  return value.toLocaleString("en-US");
}

export function formatCost(value: number, minimumFractionDigits = 2): string {
  if (minimumFractionDigits === 4) {
    return `$${value.toFixed(4)}`;
  }

  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits,
    maximumFractionDigits: minimumFractionDigits,
  });
}

export function formatTimestamp(
  value: string,
  style: keyof typeof TIMESTAMP_STYLES = "default",
): string {
  return new Date(value).toLocaleString("en-US", TIMESTAMP_STYLES[style]);
}

export function formatOptionalTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "Not synced";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "Unknown";
  }

  return formatTimestamp(value, "catalog");
}

export function buildPageButtons(currentPage: number, totalPages: number): number[] {
  const buttons = new Set<number>([
    1,
    totalPages,
    currentPage - 1,
    currentPage,
    currentPage + 1,
  ]);

  return Array.from(buttons)
    .filter((page) => page >= 1 && page <= totalPages)
    .sort((a, b) => a - b);
}
