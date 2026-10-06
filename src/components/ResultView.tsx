// One result layout for both a fresh assessment and a past one, since the backend
// returns a past assessment exactly as it was first shown.

import { pct } from "./ui";
import type { Assessment } from "@/lib/types";

const ANSWER_LABEL = { yes: "Yes", no: "No", unknown: "Not asked" } as const;

export function ResultView({ result }: { result: Assessment }) {
  const urgent = result.outcome === "urgent_referral";
  const named = result.outcome === "likely_condition";
  const [first, ...others] = result.top;

  return (
    <div className="flex flex-col gap-4">
      {urgent && (
        <div role="alert" className="rounded-xl bg-red-700 p-5 text-white">
          <p className="text-2xl font-bold">Refer urgently now</p>
          <p className="mt-1 text-base">A danger sign was reported. Send the patient to the nearest health facility immediately.</p>
        </div>
      )}

      {!urgent && (
        <div className={`rounded-xl border-2 p-5 ${named ? "border-teal-700 bg-white" : "border-amber-500 bg-amber-50"}`}>
          <p className="text-sm font-semibold uppercase tracking-wide text-slate-600">
            {named ? "Likely condition" : "Not clear enough to name one condition"}
          </p>
          <p className="mt-1 text-2xl font-bold">{named ? `${first.name} · ${pct(first.probability)}` : result.headline}</p>
        </div>
      )}

      {/* Referral guidance is the most prominent instruction on every result. */}
      <section className="rounded-xl border-2 border-slate-900 bg-white p-5">
        <h2 className="text-lg font-bold">What to do</h2>
        <p className="mt-2 text-lg leading-relaxed">{result.guidance}</p>
      </section>

      <section className="rounded-xl bg-white p-5">
        <h2 className="text-base font-semibold text-slate-700">{named ? "Other possibilities" : "Possible conditions"}</h2>
        <ul className="mt-2 flex flex-col gap-2">
          {(named ? others : result.top).map((c) => (
            <li key={c.code} className="flex justify-between text-base">
              <span>{c.name}</span><span className="text-slate-600">{pct(c.probability)}</span>
            </li>
          ))}
        </ul>
      </section>

      {result.explanation.length > 0 && (
        <section className="rounded-xl bg-white p-5">
          <h2 className="text-base font-semibold text-slate-700">Based on</h2>
          <ul className="mt-2 flex flex-col gap-2">
            {result.explanation.map((e) => (
              <li key={e.question} className="text-base">
                {e.question} <span className="font-semibold">{ANSWER_LABEL[e.answer]}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="rounded-lg bg-slate-100 p-4 text-sm leading-relaxed text-slate-700">{result.disclaimer}</p>
    </div>
  );
}
