import type { ReactNode } from "react";

import { DashboardSidebar } from "@/components/dashboard/dashboard-sidebar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

export default function DashboardLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <SidebarProvider>
      <div className="min-h-screen bg-bg-app text-text-primary">
        <div className="mx-auto flex min-h-screen max-w-[1680px] flex-col lg:flex-row">
          <DashboardSidebar />
          <SidebarInset className="bg-transparent">
            <main className="flex-1 px-4 py-6 lg:px-10 lg:py-8">
              <div className="mx-auto w-full max-w-(--content-max-width)">{children}</div>
            </main>
          </SidebarInset>
        </div>
      </div>
    </SidebarProvider>
  );
}
