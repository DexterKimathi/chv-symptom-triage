"use client";

// Login state for the whole app. The token is kept in localStorage so a volunteer stays
// logged in between visits; it expires on the backend after 60 minutes.

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useSyncExternalStore, type ReactNode } from "react";

import { api, ApiError } from "./api";
import type { Role } from "./types";

const STORAGE_KEY = "chv-triage-session";

interface Session {
  token: string;
  role: Role;
}

interface AuthState {
  session: Session | null;
  ready: boolean;
  login: (phone: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

// The session lives in localStorage, read through useSyncExternalStore. If storage is
// blocked, `memory` keeps the session working until the page is closed.
const listeners = new Set<() => void>();
let memory: string | null = null;
let cached: { raw: string | null; session: Session | null } = { raw: null, session: null };

function readRaw(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return memory;
  }
}

function write(session: Session | null) {
  memory = session ? JSON.stringify(session) : null;
  try {
    if (memory) localStorage.setItem(STORAGE_KEY, memory);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {}
  listeners.forEach((notify) => notify());
}

function subscribe(notify: () => void) {
  listeners.add(notify);
  window.addEventListener("storage", notify); // logging out in one tab logs out the others
  return () => {
    listeners.delete(notify);
    window.removeEventListener("storage", notify);
  };
}

function getSnapshot(): Session | null {
  const raw = readRaw();
  if (raw !== cached.raw) {
    let session: Session | null = null;
    try {
      session = raw ? (JSON.parse(raw) as Session) : null;
    } catch {}
    cached = { raw, session };
  }
  return cached.session;
}

// On the server there is no storage yet, so the session is "not known" rather than empty.
const getServerSnapshot = () => undefined;

export function AuthProvider({ children }: { children: ReactNode }) {
  const snapshot = useSyncExternalStore<Session | null | undefined>(subscribe, getSnapshot, getServerSnapshot);
  const session = snapshot ?? null;
  const ready = snapshot !== undefined;

  const login = useCallback(async (phone: string, password: string) => {
    const result = await api.login(phone, password);
    write({ token: result.access_token, role: result.role });
  }, []);

  const logout = useCallback(() => write(null), []);

  return <AuthContext.Provider value={{ session, ready, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}

/** Sends logged-out visitors to /login. Optionally restricts a page to admins. */
export function RequireAuth({ children, adminOnly = false }: { children: ReactNode; adminOnly?: boolean }) {
  const { session, ready } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!ready) return;
    if (!session) router.replace("/login");
    else if (adminOnly && session.role !== "admin") router.replace("/");
  }, [ready, session, adminOnly, router]);

  if (!ready || !session || (adminOnly && session.role !== "admin")) return null;
  return <>{children}</>;
}

/** An expired or rejected token logs the volunteer out instead of failing silently. */
export function useSessionGuard() {
  const { logout } = useAuth();
  const router = useRouter();
  return useCallback(
    (error: unknown) => {
      if (error instanceof ApiError && error.status === 401) {
        logout();
        router.replace("/login");
        return true;
      }
      return false;
    },
    [logout, router],
  );
}
