import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DashboardAuthGate } from "@/components/dashboard/dashboard-auth";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("DashboardAuthGate", () => {
  it("renders the dashboard immediately when authentication is disabled", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        new Response(
          JSON.stringify({ authEnabled: false, authenticated: true }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      ),
    );

    render(
      <DashboardAuthGate>
        <div>Dashboard content</div>
      </DashboardAuthGate>,
    );

    expect(await screen.findByText("Dashboard content")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Unlock ModelPort" })).toBeNull();
  });

  it("unlocks the requested dashboard after a valid token", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    fetchMock
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ authEnabled: true, authenticated: false }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(
      <DashboardAuthGate>
        <div>Protected dashboard</div>
      </DashboardAuthGate>,
    );

    await user.type(await screen.findByLabelText("Dashboard token"), "secret-token");
    await user.click(screen.getByRole("button", { name: "Unlock dashboard" }));

    expect(await screen.findByText("Protected dashboard")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/dashboard/auth/login",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify({ token: "secret-token" }),
      }),
    );
  });

  it("returns to the unlock screen when an API request reports 401", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        new Response(
          JSON.stringify({ authEnabled: true, authenticated: true }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      ),
    );

    render(
      <DashboardAuthGate>
        <div>Protected dashboard</div>
      </DashboardAuthGate>,
    );
    expect(await screen.findByText("Protected dashboard")).toBeInTheDocument();

    fireEvent(window, new Event("modelport:unauthorized"));

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Unlock ModelPort" }),
      ).toBeInTheDocument();
    });
  });
});
