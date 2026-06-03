import type {
  DashboardMockData,
  RequestRow,
} from "@/lib/mock-dashboard-data";

const DEFAULT_BACKEND_URL = "http://127.0.0.1:13243";
const backendBaseUrl =
  process.env.NEXT_PUBLIC_MODELPORT_BACKEND_URL ?? DEFAULT_BACKEND_URL;

export type OverviewAnalyticsPayload = DashboardMockData["overview"];
export type RequestsAnalyticsPayload = DashboardMockData["requests"];
export type ModelsAnalyticsPayload = DashboardMockData["models"];
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

export async function fetchModelsAnalytics() {
  return fetchJson<ModelsAnalyticsPayload>("/analytics/models");
}

export async function fetchCostsAnalytics() {
  return fetchJson<CostsAnalyticsPayload>("/analytics/costs");
}
