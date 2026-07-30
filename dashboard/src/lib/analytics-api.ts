import type {
  CostsAnalyticsData,
  OverviewAnalyticsData,
  RequestsAnalyticsData,
} from "@/lib/dashboard-types";
import { fetchJson } from "@/lib/fetch-json";

export type OverviewAnalyticsPayload = OverviewAnalyticsData;
export type RequestsAnalyticsPayload = RequestsAnalyticsData;
export type CostsAnalyticsPayload = CostsAnalyticsData;

export type RequestSortKey =
  | "timestamp"
  | "client"
  | "provider"
  | "model"
  | "totalTokens"
  | "latencyMs"
  | "costUsd"
  | "status";

export interface RequestsAnalyticsQuery {
  page?: number;
  pageSize?: number;
  search?: string;
  client?: string;
  provider?: string;
  model?: string;
  status?: string;
  endpoint?: string;
  timeRange?: "1h" | "6h" | "24h" | "7d" | "all";
  sort?: RequestSortKey;
  direction?: "asc" | "desc";
}

export async function fetchOverviewAnalytics() {
  return fetchJson<OverviewAnalyticsPayload>("/analytics/overview");
}

export async function fetchRequestsAnalytics(
  query: RequestsAnalyticsQuery = {},
) {
  const searchParams = new URLSearchParams();
  if (query.page !== undefined) searchParams.set("page", String(query.page));
  if (query.pageSize !== undefined) {
    searchParams.set("page_size", String(query.pageSize));
  }
  if (query.search) searchParams.set("search", query.search);
  if (query.client) searchParams.set("client", query.client);
  if (query.provider) searchParams.set("provider", query.provider);
  if (query.model) searchParams.set("model", query.model);
  if (query.status) searchParams.set("status", query.status);
  if (query.endpoint) searchParams.set("endpoint", query.endpoint);
  if (query.timeRange) searchParams.set("time_range", query.timeRange);
  if (query.sort) searchParams.set("sort", query.sort);
  if (query.direction) searchParams.set("direction", query.direction);
  const suffix = searchParams.size > 0 ? `?${searchParams.toString()}` : "";
  return fetchJson<RequestsAnalyticsPayload>(`/analytics/requests${suffix}`);
}

export async function fetchRequestDetail(requestId: string) {
  return fetchJson<RequestsAnalyticsPayload["rows"][number]>(
    `/analytics/requests/${encodeURIComponent(requestId)}`,
  );
}

export async function fetchCostsAnalytics() {
  return fetchJson<CostsAnalyticsPayload>("/analytics/costs");
}
