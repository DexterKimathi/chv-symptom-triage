"use client";

// One fetch of the dashboard figures, shared by every admin screen.

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

import { api } from "@/lib/api";
import { useAuth, useSessionGuard } from "@/lib/auth";
import type { Dashboard, DashboardDays } from "@/lib/types";

interface DashboardState {
  /** The last figures received. Kept on screen while newer ones load. */
  data: Dashboard | null;
  error: string | null;
  loading: boolean;
  days: DashboardDays;
  setDays: (days: DashboardDays) => void;
  refresh: () => void;
}

const DashboardContext = createContext<DashboardState | null>(null);

let rememberedDays: DashboardDays = 28;

export function DashboardProvider({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const guard = useSessionGuard();
  const [days, setDaysState] = useState<DashboardDays>(rememberedDays);
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<{ key: string; data: Dashboard | null; error: string | null }>(
    { key: "", data: null, error: null },
  );
  const key = `${days}:${attempt}`;

  useEffect(() => {
    if (!session) return;
    let stale = false; // an older request must not overwrite a newer one
    api.dashboard(session.token, days)
      .then((data) => { if (!stale) setResult({ key, data, error: null }); })
      .catch((e) => {
        if (stale || guard(e)) return;
        setResult((r) => ({ key, data: r.data, error: e instanceof Error ? e.message : "Could not load the figures." }));
      });
    return () => { stale = true; };
  }, [session, guard, days, key]);

  const setDays = useCallback((next: DashboardDays) => { rememberedDays = next; setDaysState(next); }, []);
  const refresh = useCallback(() => setAttempt((n) => n + 1), []);

  const loading = result.key !== key;
  return (
    <DashboardContext.Provider value={{ data: result.data, error: loading ? null : result.error, loading, days, setDays, refresh }}>
      {children}
    </DashboardContext.Provider>
  );
}

export function useDashboard(): DashboardState {
  const context = useContext(DashboardContext);
  if (!context) throw new Error("useDashboard must be used inside DashboardProvider");
  return context;
}
