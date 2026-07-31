import { afterEach, describe, expect, it, vi } from "vitest";

import {
  fetchRequestDetail,
  fetchRequestsAnalytics,
} from "@/lib/analytics-api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("requests analytics API", () => {
  it("encodes server-side filters, sorting, and pagination", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          totals: {},
          filters: {},
          rows: [],
          pagination: {},
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await fetchRequestsAnalytics({
      page: 2,
      pageSize: 5,
      search: "claude code",
      provider: "OpenAI",
      timeRange: "24h",
      sort: "costUsd",
      direction: "desc",
    });

    expect(fetchMock.mock.calls[0][0]).toBe(
      "/analytics/requests?page=2&page_size=5&search=claude+code&provider=OpenAI&time_range=24h&sort=costUsd&direction=desc",
    );
  });

  it("fetches request I/O from the detail endpoint", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ id: "req_123" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await fetchRequestDetail("req_123");

    expect(fetchMock.mock.calls[0][0]).toBe("/analytics/requests/req_123");
  });
});
