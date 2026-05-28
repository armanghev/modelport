import { SunIcon } from "@phosphor-icons/react/dist/ssr";

export function PageHeader({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div className="space-y-1">
        <h1>{title}</h1>
        <p className="text-base text-text-secondary">{description}</p>
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
