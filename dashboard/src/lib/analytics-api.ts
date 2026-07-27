import type { DashboardMockData, RequestRow } from "@/lib/dashboard-types";
import { backendUrl as backendBaseUrl } from "@/lib/backend-url";

export type OverviewAnalyticsPayload = DashboardMockData["overview"];
export type RequestsAnalyticsPayload = DashboardMockData["requests"];
export type CostsAnalyticsPayload = DashboardMockData["costs"] & {
  recentHighCostRequests: RequestRow[];
};

function buildUrl(path: string) {
  return `${backendBaseUrl}${path}`;
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(buildUrl(path), {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function fetchOverviewAnalytics() {
  return fetchJson<OverviewAnalyticsPayload>("/analytics/overview");
}

export async function fetchRequestsAnalytics() {
  return fetchJson<RequestsAnalyticsPayload>("/analytics/requests");
}

export async function fetchCostsAnalytics() {
  return fetchJson<CostsAnalyticsPayload>("/analytics/costs");
}
