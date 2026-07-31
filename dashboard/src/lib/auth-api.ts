export interface DashboardAuthStatus {
  authEnabled: boolean;
  authenticated: boolean;
}

async function authRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
    credentials: "same-origin",
  });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        detail = payload.detail;
      }
    } catch {
      // Keep the status-based fallback for non-JSON errors.
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function fetchDashboardAuthStatus() {
  return authRequest<DashboardAuthStatus>("/dashboard/auth/status");
}

export function loginDashboard(token: string) {
  return authRequest<void>("/dashboard/auth/login", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export function logoutDashboard() {
  return authRequest<void>("/dashboard/auth/logout", {
    method: "POST",
  });
}
