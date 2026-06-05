"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { MoonIcon, SunIcon } from "@phosphor-icons/react";
import { useTheme } from "@teispace/next-themes";

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
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const segments = pathname.split("/").filter(Boolean);
  const currentPage = segments.at(-1) as keyof typeof pages | undefined;
  const currentPageData =
    segments[0] === "models" && segments.length >= 3
      ? { title: "Model details", description: "Pricing, capabilities, and proxy usage" }
      : (currentPage && pages[currentPage]) || DEFAULT_PAGE;

  useEffect(() => {
    setMounted(true);
  }, []);

  const activeTheme = mounted ? (theme ?? "system") : "system";

  const themeIcon =
    activeTheme === "dark" ? <MoonIcon size={18} /> : <SunIcon size={18} />;

  const cycleTheme = () => {
    setTheme(activeTheme === "light" ? "dark" : "light");
  };

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
          aria-label={`Theme: ${activeTheme}. Switch theme`}
          onClick={cycleTheme}
        >
          {themeIcon}
        </button>
      </div>
    </header>
  );
}
