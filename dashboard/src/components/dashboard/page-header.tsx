"use client";

import { SignOutIcon } from "@phosphor-icons/react";
import { useLocation } from "react-router";

import { useDashboardAuth } from "@/components/dashboard/dashboard-auth-context";

const pages = {
  overview: { title: "Overview", description: "Usage and routing overview" },
  requests: { title: "Requests", description: "Search and inspect proxy activity" },
  models: { title: "Models", description: "Browse enriched model catalogs, pricing, and usage" },
  providers: { title: "Providers", description: "Monitor provider health and routing" },
  costs: { title: "Costs", description: "Track spending across providers and models" },
  settings: { title: "Settings", description: "Configure clients, defaults, and more" },
} as const;

const DEFAULT_PAGE = pages.overview;

export function PageHeader() {
  const { pathname } = useLocation();
  const { authEnabled, logout } = useDashboardAuth();
  const segments = pathname.split("/").filter(Boolean);
  const currentPage = segments.at(-1) as keyof typeof pages | undefined;
  const currentPageData =
    segments[0] === "models" && segments.length >= 3
      ? { title: "Model details", description: "Pricing, capabilities, and proxy usage" }
      : (currentPage && pages[currentPage]) || DEFAULT_PAGE;

  return (
    <header className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div className="space-y-1">
        <h1 className="text-[1.75rem] font-semibold leading-9 text-fd-foreground">
          {currentPageData.title}
        </h1>
        <p className="text-base text-fd-muted-foreground">
          {currentPageData.description}
        </p>
      </div>
      {authEnabled ? (
        <button
          type="button"
          onClick={() => void logout()}
          className="inline-flex items-center gap-2 rounded-lg border border-border-default px-3 py-2 text-sm text-text-secondary hover:bg-bg-hover hover:text-text-primary"
        >
          <SignOutIcon size={16} />
          Log out
        </button>
      ) : null}
    </header>
  );
}
