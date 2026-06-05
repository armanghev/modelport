'use client';

export function DashboardSidebarFooter() {
  return (
    <div className="p-2 mt-2 border border-border-default rounded-md bg-fd-secondary/50">
      <p className="mb-1 text-xs text-fd-muted-foreground">Proxy status</p>
      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-sm font-medium text-fd-success">
          <span className="inline-block size-2 rounded-full bg-fd-success" />
          Running
        </p>
        <p className="text-xs text-fd-muted-foreground">v1.2.0</p>
      </div>
    </div>
  );
}
