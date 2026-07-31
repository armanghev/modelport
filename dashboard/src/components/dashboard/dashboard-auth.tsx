import {
  type FormEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DashboardAuthContext,
  type DashboardAuthContextValue,
} from "@/components/dashboard/dashboard-auth-context";
import {
  fetchDashboardAuthStatus,
  loginDashboard,
  logoutDashboard,
} from "@/lib/auth-api";

type AuthState = "loading" | "authenticated" | "locked" | "error";

export function DashboardAuthGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>("loading");
  const [authEnabled, setAuthEnabled] = useState(true);
  const [token, setToken] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let active = true;
    void fetchDashboardAuthStatus()
      .then((status) => {
        if (!active) return;
        setAuthEnabled(status.authEnabled);
        setState(status.authenticated ? "authenticated" : "locked");
      })
      .catch((error: unknown) => {
        if (!active) return;
        setErrorMessage(
          error instanceof Error
            ? error.message
            : "Could not reach the ModelPort backend.",
        );
        setState("error");
      });

    const handleUnauthorized = () => {
      if (active) {
        setToken("");
        setErrorMessage(null);
        setState("locked");
      }
    };
    window.addEventListener("modelport:unauthorized", handleUnauthorized);
    return () => {
      active = false;
      window.removeEventListener("modelport:unauthorized", handleUnauthorized);
    };
  }, []);

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      await loginDashboard(token);
      setToken("");
      setState("authenticated");
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Dashboard login failed.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const logout = useCallback(async () => {
    await logoutDashboard();
    setToken("");
    setErrorMessage(null);
    setState("locked");
  }, []);

  const contextValue = useMemo<DashboardAuthContextValue>(
    () => ({ authEnabled, logout }),
    [authEnabled, logout],
  );

  if (state === "loading") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-bg-app text-sm text-text-secondary">
        Loading ModelPort…
      </main>
    );
  }

  if (state === "error") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-bg-app p-6">
        <div className="card-surface max-w-md p-6 text-sm text-accent-red">
          {errorMessage}
        </div>
      </main>
    );
  }

  if (state === "locked") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-bg-app p-6">
        <form
          onSubmit={handleLogin}
          className="card-surface w-full max-w-sm space-y-5 p-6"
        >
          <div className="space-y-1">
            <h1 className="text-2xl font-semibold text-text-primary">
              Unlock ModelPort
            </h1>
            <p className="text-sm text-text-secondary">
              Enter the dashboard token configured on this ModelPort server.
            </p>
          </div>
          <label className="block space-y-2 text-sm text-text-secondary">
            <span>Dashboard token</span>
            <Input
              autoFocus
              required
              type="password"
              autoComplete="current-password"
              value={token}
              onChange={(event) => setToken(event.target.value)}
            />
          </label>
          {errorMessage ? (
            <p className="text-sm text-accent-red">{errorMessage}</p>
          ) : null}
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Unlocking…" : "Unlock dashboard"}
          </Button>
        </form>
      </main>
    );
  }

  return (
    <DashboardAuthContext.Provider value={contextValue}>
      {children}
    </DashboardAuthContext.Provider>
  );
}
