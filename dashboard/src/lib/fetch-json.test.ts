import { describe, expect, it, vi } from "vitest";

import { fetchJson } from "@/lib/fetch-json";

describe("fetchJson", () => {
  it("uses a relative same-origin URL and includes browser credentials", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        new Response(JSON.stringify({ status: "ok" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await fetchJson<{ status: string }>("/analytics/overview");

    expect(fetchMock).toHaveBeenCalledWith(
      "/analytics/overview",
      expect.objectContaining({
        cache: "no-store",
        credentials: "same-origin",
      }),
    );
    const request = fetchMock.mock.calls[0][1];
    expect(request?.headers).not.toHaveProperty("Authorization");
  });

  it("announces an expired dashboard session after a 401", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        new Response("Unauthorized", {
          status: 401,
        }),
      ),
    );
    const listener = vi.fn();
    window.addEventListener("modelport:unauthorized", listener);

    await expect(fetchJson("/admin/settings")).rejects.toThrow("Unauthorized");

    expect(listener).toHaveBeenCalledOnce();
    window.removeEventListener("modelport:unauthorized", listener);
  });
});
