import type {
  CostsAnalyticsData,
  OverviewAnalyticsData,
  RequestsAnalyticsData,
} from "@/lib/dashboard-types";
import { fetchJson } from "@/lib/fetch-json";

export type OverviewAnalyticsPayload = OverviewAnalyticsData;
export type RequestsAnalyticsPayload = RequestsAnalyticsData;
export type CostsAnalyticsPayload = CostsAnalyticsData;

export async function fetchOverviewAnalytics() {
  return fetchJson<OverviewAnalyticsPayload>("/analytics/overview");
}

export async function fetchRequestsAnalytics() {
  return fetchJson<RequestsAnalyticsPayload>("/analytics/requests");
}

export async function fetchCostsAnalytics() {
  return fetchJson<CostsAnalyticsPayload>("/analytics/costs");
}
