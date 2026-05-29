"use client";

import { usePathname } from "next/navigation";
import { SunIcon } from "@phosphor-icons/react/dist/ssr";

const pages = {
  overview: { title: "Overview", description: "Usage and routing overview" },
  requests: { title: "Requests", description: "Search and inspect proxy activity" },
  models: { title: "Models", description: "Manage model aliases and usage" },
  providers: { title: "Providers", description: "Monitor provider health and routing" },
  costs: { title: "Costs", description: "Track spending across providers and models" },
  settings: { title: "Settings", description: "Configure clients, defaults, and more" },
} as const;

const DEFAULT_PAGE = pages.overview;

export function PageHeader() {
  const pathname = usePathname();
  const currentPage = pathname.split("/").filter(Boolean).pop() as keyof typeof pages | undefined;
  const currentPageData = (currentPage && pages[currentPage]) || DEFAULT_PAGE;

  return (
    <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div className="space-y-1">
        <h1>{currentPageData.title}</h1>
        <p className="text-base text-text-secondary">{currentPageData.description}</p>
      </div>

      <div className="flex items-center gap-3 text-sm text-text-secondary">
        {/* TODO: Add proxy status */}
        <div className="flex items-center gap-2">
          <span className="status-dot bg-accent-green" />
          <span>All systems operational</span>
        </div>
        <button
          type="button"
          className="card-surface-soft inline-flex h-9 w-9 items-center justify-center rounded-full"
          aria-label="Toggle theme"
        >
          <SunIcon size={18} />
        </button>
        <button
          type="button"
          className="card-surface-soft inline-flex h-9 w-9 items-center justify-center rounded-full text-sm font-semibold"
          aria-label="Open profile"
        >
          A
        </button>
      </div>
    </header>
  );
}
