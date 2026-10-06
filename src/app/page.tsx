"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Alert, ButtonLink, Code, ErrorNotice, OfflineBanner, PlusIcon, Spinner, TopBar, TopTitle } from "@/components/ui";
import { api, NetworkError } from "@/lib/api";
import { RequireAuth, useAuth, useSessionGuard } from "@/lib/auth";
import { shortWhen, summaryLabel } from "@/lib/format";
import type { AssessmentSummary } from "@/lib/types";

const FIRST_PAGE = 5;

function Home() {
  const { session, logout } = useAuth();
  const guard = useSessionGuard();
  const [items, setItems] = useState<AssessmentSummary[] | null>(null);
  const [error, setError] = useState<"offline" | string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!session) return;
    api.assessments(session.token)
      .then((list) => { setItems(list); setError(null); })
      .catch((e) => {
        if (guard(e)) return;
        setError(e instanceof NetworkError ? "offline" : e.message);
      });
  }, [session, guard, attempt]);

  const retry = () => { setError(null); setAttempt((n) => n + 1); };

  const visible = showAll ? items : items?.slice(0, FIRST_PAGE);

  return (
    <>
      <TopBar
        left={<TopTitle>CHV Triage</TopTitle>}
        right={<button onClick={logout} className="h-12 px-1 text-small font-bold text-blue">Log out</button>}
      />
      <main className="flex flex-1 flex-col gap-5 px-4 py-5">
        {error === "offline" && <OfflineBanner detail="Move to a spot with better signal." onRetry={retry} />}

        {session?.name && (
          <div>
            <p className="text-label font-bold">{session.name}</p>
            {session.area && <p className="text-small text-ink-soft">{session.area}</p>}
          </div>
        )}

        <Link href="/assess"
          className="flex min-h-[84px] items-center gap-4 rounded-xl bg-blue px-5 text-[22px] leading-7 font-bold text-white hover:bg-blue-dark">
          <PlusIcon /> Start assessment
        </Link>
        {session?.role === "admin" && <ButtonLink href="/admin" variant="secondary">Add volunteer</ButtonLink>}

        <section className="flex flex-col">
          <h2 className="border-b border-divider pb-2 text-label font-bold">Recent assessments</h2>

          {error && error !== "offline" && <div className="mt-3"><ErrorNotice>{error}</ErrorNotice></div>}

          {error === "offline" && !items && (
            <div className="mt-3 rounded-xl bg-surface p-4 text-center">
              <p className="text-label font-bold">Could not load your assessments</p>
              <p className="text-small text-ink-soft">They are safe. They will show when you are back online.</p>
            </div>
          )}

          {!items && !error && (
            <div role="status">
              <p className="flex items-center gap-2 py-3 text-small text-ink-soft"><Spinner /> Loading your assessments…</p>
              {[0, 1, 2].map((i) => (
                <div key={i} className="flex items-center justify-between border-b border-divider py-4 pl-9" aria-hidden>
                  <div className="flex flex-col gap-2"><span className="h-3.5 w-12 rounded bg-surface" /><span className="h-3.5 w-32 rounded bg-surface" /></div>
                  <span className="h-3.5 w-10 rounded bg-surface" />
                </div>
              ))}
            </div>
          )}

          {items?.length === 0 && (
            <div className="mt-3 rounded-xl bg-surface px-4 py-6 text-center">
              <p className="text-label font-bold">No assessments yet</p>
              <p className="mt-1 text-small text-ink-soft">Tap <b className="text-ink">Start assessment</b> to check your first patient. Your results will appear here.</p>
            </div>
          )}

          {visible?.map((a) => {
            const urgent = a.outcome === "urgent_referral";
            const when = shortWhen(a.created_at);
            return (
              <Link key={a.id} href={`/history/${a.id}`}
                className="flex min-h-16 items-center gap-3 border-b border-divider py-3 hover:bg-surface">
                <span className="w-6 flex-none">{urgent && <Alert />}</span>
                <span className="flex flex-1 flex-col">
                  <Code className="text-small">{a.patient_ref}</Code>
                  <span className={`text-small ${urgent ? "font-bold text-red" : ""}`}>{summaryLabel(a)}</span>
                </span>
                <span className="text-right text-[14px] leading-5 text-ink-soft">
                  {when.day}{when.time && <><br />{when.time}</>}
                </span>
                <span aria-hidden className="text-heading text-ink-soft">›</span>
              </Link>
            );
          })}

          {items && items.length > FIRST_PAGE && !showAll && (
            <button onClick={() => setShowAll(true)} className="h-12 text-small font-bold text-blue">
              Show older assessments
            </button>
          )}
        </section>
      </main>
    </>
  );
}

export default function HomePage() {
  return <RequireAuth><Home /></RequireAuth>;
}
