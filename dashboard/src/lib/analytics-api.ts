import type {
  DashboardMockData,
  RequestRow,
} from "@/lib/mock-dashboard-data";
import { dashboardMockData } from "@/lib/mock-dashboard-data";
import { backendUrl as backendBaseUrl } from "@/lib/backend-url";

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
  try {
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
  } catch {
    return getMockFallback<T>(path);
  }
}

function getMockFallback<T>(path: string): T {
  switch (path) {
    case "/analytics/overview":
      return dashboardMockData.overview as T;
    case "/analytics/requests":
      return dashboardMockData.requests as T;
    case "/analytics/models":
      return dashboardMockData.models as T;
    case "/analytics/costs":
      return {
        ...dashboardMockData.costs,
        recentHighCostRequests: dashboardMockData.requests.rows.slice(0, 5),
      } as T;
    default:
      throw new Error(`Backend unavailable and no mock data for ${path}`);
  }
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
