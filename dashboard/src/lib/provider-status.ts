import type { ProviderStatus } from "@/lib/dashboard-types";

export function formatProviderStatus(status: ProviderStatus): string {
  if (status === "operational") {
    return "Healthy";
  }

  if (status === "degraded") {
    return "Degraded";
  }

  return "Offline";
}
