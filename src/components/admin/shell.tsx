"use client";

// The admin frame, laid out for a laptop: a navigation column on the left, then the page
// title, the period filter and the figures. On narrower screens the navigation moves to the top.

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { ErrorNotice, Loading } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import type { Dashboard } from "@/lib/types";

import { useDashboard } from "./data";
import { dayLabel, PERIODS, rememberFilters } from "./meta";

const NAV = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/areas", label: "Areas" },
  { href: "/admin/assessments", label: "Assessments" },
  { href: "/admin/volunteers", label: "Volunteers" },
];

const isCurrent = (pathname: string, href: string) =>
  href === "/admin" ? pathname === href : pathname.startsWith(href);

function Sidebar() {
  const pathname = usePathname();
  const { session, logout } = useAuth();
  return (
    <aside className="flex flex-none flex-col gap-3 bg-ink p-3 text-white lg:sticky lg:top-0 lg:h-dvh lg:w-60 lg:gap-6 lg:p-4">
      <div className="flex items-center gap-3 px-1">
        <span aria-hidden className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue text-[26px] leading-none font-bold">+</span>
        <p className="flex flex-col leading-tight">
          <span className="text-label font-bold">CHV Triage</span>
          <span className="text-[14px] text-white/70">Administration</span>
        </p>
      </div>
      <nav aria-label="Admin" className="flex gap-1 overflow-x-auto lg:flex-col">
        {NAV.map((item) => {
          const current = isCurrent(pathname, item.href);
          return (
            <Link key={item.href} href={item.href} aria-current={current ? "page" : undefined}
              onClick={() => rememberFilters({})}
              className={`flex h-11 flex-none items-center rounded-lg px-3 text-small font-bold ${current ? "bg-white text-ink" : "text-white hover:bg-white/10"}`}>
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="flex items-center justify-between gap-3 border-t border-white/20 pt-3 lg:mt-auto lg:flex-col lg:items-stretch">
        <p className="px-1 text-small">
          <span className="block font-bold">{session?.name ?? "Administrator"}</span>
          <span className="text-white/70">Admin</span>
        </p>
        <div className="flex gap-2 lg:flex-col">
          <Link href="/assess" className="flex h-11 items-center justify-center rounded-lg border border-white/40 px-3 text-small font-bold hover:bg-white/10">
            Run an assessment
          </Link>
          <button type="button" onClick={logout} className="h-11 rounded-lg px-3 text-small font-bold hover:bg-white/10">Log out</button>
        </div>
      </div>
    </aside>
  );
}

export function AdminShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-1 flex-col bg-surface lg:flex-row">
      <Sidebar />
      <main className="min-w-0 flex-1 px-4 py-5 lg:px-8 lg:py-7">
        <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-5">{children}</div>
      </main>
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-headline font-bold">{title}</h1>
        {subtitle && <p className="text-small text-ink-soft">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
    </div>
  );
}

function PeriodFilter() {
  const { days, setDays, refresh, loading } = useDashboard();
  return (
    <>
      <div role="group" aria-label="Period" className="flex rounded-[10px] border border-divider bg-white p-1">
        {PERIODS.map((p) => (
          <button key={p.days} type="button" aria-pressed={days === p.days} onClick={() => setDays(p.days)}
            className={`h-10 rounded-lg px-4 text-small font-bold ${days === p.days ? "bg-blue text-white" : "text-ink hover:bg-surface"}`}>
            {p.label}
          </button>
        ))}
      </div>
      <button type="button" onClick={refresh} disabled={loading}
        className="h-12 rounded-[10px] border border-divider bg-white px-4 text-small font-bold text-blue hover:bg-blue-tint disabled:text-ink-soft">
        {loading ? "Loading…" : "Refresh"}
      </button>
    </>
  );
}

/** A screen of figures: title, period filter, the notices that apply to all of them, then the content. */
export function DashboardPage({ title, actions, children }: {
  title: string; actions?: ReactNode; children: (data: Dashboard) => ReactNode;
}) {
  const { data, error, loading, refresh } = useDashboard();
  return (
    <>
      <PageHeader title={title}
        subtitle={data && <>{dayLabel(data.start)} to {dayLabel(data.end, true)}</>}
        actions={<><PeriodFilter />{actions}</>} />
      {error && (
        <ErrorNotice>
          {error} {data && "The figures below are the last ones received. "}
          <button type="button" onClick={refresh} className="font-bold text-blue underline">Try again</button>
        </ErrorNotice>
      )}
      {!data && !error && <Loading label="Loading the figures…" />}
      {data && (
        <div className={`flex flex-col gap-5 ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
          {data.sample_assessments > 0 && (
            <p role="note" className="rounded-xl border-2 border-amber bg-amber-tint px-4 py-3 text-small">
              <b>Includes sample data.</b> {data.sample_assessments} of {data.totals.assessments} assessments in this
              period were made up for demonstration. They are not real patients.
            </p>
          )}
          {children(data)}
          <p className="text-small text-ink-soft">
            Conditions here are what the app suggested to volunteers, not confirmed diagnoses. Areas are the ones saved
            on each volunteer&apos;s account; no device location is collected.
          </p>
        </div>
      )}
    </>
  );
}
