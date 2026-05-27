"use client";

import {
  ClockCounterClockwise,
  Cube,
  Coins,
  GearSix,
  Globe,
  House,
} from "@phosphor-icons/react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";

const navItems = [
  { title: "Overview", href: "/overview", icon: House },
  { title: "Requests", href: "/requests", icon: ClockCounterClockwise },
  { title: "Models", href: "/models", icon: Cube },
  { title: "Providers", href: "/providers", icon: Globe },
  { title: "Costs", href: "/costs", icon: Coins },
  { title: "Settings", href: "/settings", icon: GearSix },
];

export function DashboardSidebar() {
  const pathname = usePathname();

  return (
    <Sidebar
      collapsible="none"
      className="shrink-0 border-r border-border-default bg-bg-sidebar text-text-primary lg:sticky lg:top-0 lg:h-screen lg:self-start lg:overflow-hidden"
    >
      <SidebarHeader className="gap-0 border-b border-border-default px-4 py-6">
        <div className="flex items-center gap-1">
          <Image src="/modelport-icon.svg" alt="Local AI Proxy" width={40} height={40} />
          <span className="text-2xl font-semibold tracking-[-0.02em] text-text-primary">
            ModelPort
          </span>
        </div>
      </SidebarHeader>

      <SidebarContent className="px-2 py-4">
        <SidebarMenu>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;

            return (
              <SidebarMenuItem key={item.title}>
                <SidebarMenuButton
                  asChild
                  isActive={isActive}
                  className="h-12 gap-3 rounded-xl px-4 text-[14px] font-semibold text-text-secondary data-[active=true]:bg-bg-hover data-[active=true]:text-text-primary"
                >
                  <Link href={item.href}>
                    <Icon size={20} weight="regular" />
                    <span>{item.title}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            );
          })}
        </SidebarMenu>
      </SidebarContent>

      <SidebarFooter className="mt-auto p-4">
        <div className="card-surface rounded-(--radius-card) p-4">
          <p className="text-[12px] text-text-muted">Proxy status</p>
          <p className="mt-1 flex items-center gap-2 text-[14px] font-semibold text-accent-green">
            <span className="status-dot bg-accent-green" />
            Running
          </p>
          <p className="mt-2 text-[12px] text-text-muted">v1.2.0</p>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
