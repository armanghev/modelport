import { backendUrl as backendBaseUrl } from "@/lib/backend-url";

export function buildBackendUrl(path: string) {
  return `${backendBaseUrl}${path}`;
}

function dashboardAuthHeaders(): HeadersInit {
  const token = process.env.NEXT_PUBLIC_MODELPORT_DASHBOARD_TOKEN;
  if (!token) {
    throw new Error("Set NEXT_PUBLIC_MODELPORT_DASHBOARD_TOKEN in dashboard/.env");
  }
  return {
    Authorization: `Bearer ${token}`,
  };
}

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(buildBackendUrl(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...dashboardAuthHeaders(),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
