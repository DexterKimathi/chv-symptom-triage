"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ErrorMessage, Loading, pct, Screen } from "@/components/ui";
import { api } from "@/lib/api";
import { RequireAuth, useAuth, useSessionGuard } from "@/lib/auth";
import type { AssessmentSummary } from "@/lib/types";

function Home() {
  const { session, logout } = useAuth();
  const guard = useSessionGuard();
  const [items, setItems] = useState<AssessmentSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    api.assessments(session.token)
      .then(setItems)
      .catch((e) => { if (!guard(e)) setError(e.message); });
  }, [session, guard]);

  return (
    <Screen>
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Assessments</h1>
        <button onClick={logout} className="min-h-12 px-3 text-base text-slate-600 underline">Log out</button>
      </header>

      <Link href="/assess" className="flex min-h-16 items-center justify-center rounded-xl bg-teal-700 px-5 text-xl font-bold text-white hover:bg-teal-800">
        Start assessment
      </Link>
      {session?.role === "admin" && (
        <Link href="/admin" className="flex min-h-12 items-center justify-center rounded-xl border-2 border-slate-300 bg-white text-lg font-semibold">
          Create volunteer account
        </Link>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold text-slate-700">Recent</h2>
        <ErrorMessage message={error} />
        {!items && !error && <Loading />}
        {items?.length === 0 && (
          <p className="rounded-lg border-2 border-dashed border-slate-300 p-6 text-center text-slate-600">
            No assessments yet. Start one above.
          </p>
        )}
        {items?.map((a) => (
          <Link key={a.id} href={`/history/${a.id}`}
            className={`flex items-center justify-between gap-3 rounded-xl border-2 bg-white p-4 ${a.danger_sign_triggered ? "border-red-400" : "border-slate-200"}`}>
            <div className="flex flex-col">
              <span className="text-lg font-semibold">{a.patient_ref}</span>
              <span className="text-sm text-slate-600">{new Date(a.created_at).toLocaleString()}</span>
            </div>
            <span className={`text-right text-base font-semibold ${a.danger_sign_triggered ? "text-red-700" : "text-slate-800"}`}>
              {a.danger_sign_triggered ? "Urgent referral"
                : a.outcome === "likely_condition" ? `${a.top_condition} · ${pct(a.top_confidence)}`
                : "Refer for assessment"}
            </span>
          </Link>
        ))}
      </section>
    </Screen>
  );
}

export default function HomePage() {
  return <RequireAuth><Home /></RequireAuth>;
}
