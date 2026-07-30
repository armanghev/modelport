import { createContext, useContext } from "react";

export interface DashboardAuthContextValue {
  authEnabled: boolean;
  logout: () => Promise<void>;
}

export const DashboardAuthContext =
  createContext<DashboardAuthContextValue | null>(null);

export function useDashboardAuth() {
  const context = useContext(DashboardAuthContext);
  if (!context) {
    throw new Error("useDashboardAuth must be used within DashboardAuthGate.");
  }
  return context;
}
