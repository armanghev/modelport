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
      <div className="min-h-screen w-full overflow-x-clip bg-bg-app text-text-primary">
        <div className="flex min-h-screen w-full flex-col lg:flex-row">
          <DashboardSidebar />
          <SidebarInset className="bg-transparent">
            <main className="w-full flex-1 px-4 py-6 lg:px-10 lg:py-8">
              <div className="w-full">{children}</div>
            </main>
          </SidebarInset>
        </div>
      </div>
    </SidebarProvider>
  );
}
