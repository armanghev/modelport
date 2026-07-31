export function buildBackendUrl(path: string) {
  return path;
}

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(buildBackendUrl(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
    credentials: "same-origin",
  });

  if (!response.ok) {
    const detail = await response.text();
    if (response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new Event("modelport:unauthorized"));
    }
    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
