"use client";

// Login state for the whole app. The token is kept in localStorage so a volunteer stays
// logged in between visits; it expires on the backend after 60 minutes.

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useSyncExternalStore, type ReactNode } from "react";

import { api, ApiError } from "./api";
import { clearDraft, clearDraftUnlessOwnedBy } from "./draft";
import type { Role } from "./types";

const STORAGE_KEY = "chv-triage-session";

interface Session {
  token: string;
  role: Role;
  // Display only. Sessions saved before these were added have neither.
  name?: string;
  area?: string | null;
}

interface AuthState {
  session: Session | null;
  /** The account id from the token, used to keep each volunteer's draft separate. */
  userId: string | null;
  ready: boolean;
  login: (phone: string, password: string) => Promise<void>;
  /** The volunteer chose to log out: the session and any unfinished assessment are removed. */
  logout: () => void;
  /** The token expired: the session ends, but the draft is kept for when the same volunteer logs back in. */
  endSession: () => void;
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

/** The account id ("sub") inside the token. Read only to label the draft; the backend checks the token. */
export function userIdFromToken(token: string): string | null {
  try {
    const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const sub = (JSON.parse(atob(payload)) as { sub?: unknown }).sub;
    return sub === undefined || sub === null ? null : String(sub);
  } catch {
    return null;
  }
}

// On the server there is no storage yet, so the session is "not known" rather than empty.
const getServerSnapshot = () => undefined;

export function AuthProvider({ children }: { children: ReactNode }) {
  const snapshot = useSyncExternalStore<Session | null | undefined>(subscribe, getSnapshot, getServerSnapshot);
  const session = snapshot ?? null;
  const ready = snapshot !== undefined;
  const userId = session ? userIdFromToken(session.token) : null;

  const login = useCallback(async (phone: string, password: string) => {
    const result = await api.login(phone, password);
    // A draft left on this phone by someone else must never reach the new volunteer.
    clearDraftUnlessOwnedBy(userIdFromToken(result.access_token));
    write({ token: result.access_token, role: result.role, name: result.name, area: result.area });
  }, []);

  const logout = useCallback(() => {
    clearDraft();
    write(null);
  }, []);

  const endSession = useCallback(() => write(null), []);

  return <AuthContext.Provider value={{ session, userId, ready, login, logout, endSession }}>{children}</AuthContext.Provider>;
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

/** An expired or rejected token logs the volunteer out instead of failing silently. Their
 *  unfinished assessment is kept, and comes back only when the same account logs in again. */
export function useSessionGuard() {
  const { endSession } = useAuth();
  const router = useRouter();
  return useCallback(
    (error: unknown) => {
      if (error instanceof ApiError && error.status === 401) {
        endSession();
        router.replace("/login");
        return true;
      }
      return false;
    },
    [endSession, router],
  );
}
