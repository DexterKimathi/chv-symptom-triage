"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Button, ErrorMessage, Field, inputClass, Loading, Screen } from "@/components/ui";
import { api } from "@/lib/api";
import { RequireAuth, useAuth, useSessionGuard } from "@/lib/auth";
import { AGE_BANDS, type AgeBand, type Answer, type Question, type Sex } from "@/lib/types";

const CHOICES: { value: Answer; label: string }[] = [
  { value: "yes", label: "Yes" },
  { value: "no", label: "No" },
  { value: "unknown", label: "Not asked" },
];

const CHOSEN: Record<Answer, string> = {
  yes: "border-teal-700 bg-teal-700 text-white",
  no: "border-slate-700 bg-slate-700 text-white",
  unknown: "border-slate-400 bg-slate-200 text-slate-900",
};

// Plain headings for the backend's question categories.
const GROUP_TITLE: Record<string, string> = {
  constitutional: "Fever and general",
  respiratory: "Cough and breathing",
  gastrointestinal: "Stomach and diarrhoea",
  hydration: "Drinking and fluids",
  urinary: "Passing urine",
  other: "Other",
};

/** Questions grouped by category in display order, danger signs first. */
function toSteps(questions: Question[]) {
  const sorted = [...questions].sort(
    (a, b) => Number(b.is_danger_sign) - Number(a.is_danger_sign) || a.display_order - b.display_order,
  );
  const steps: { title: string; questions: Question[] }[] = [];
  for (const q of sorted) {
    const title = q.is_danger_sign ? "Danger signs" : GROUP_TITLE[q.category] ?? q.category;
    const last = steps.at(-1);
    if (last?.title === title) last.questions.push(q);
    else steps.push({ title, questions: [q] });
  }
  return steps;
}

function Assess() {
  const { session } = useAuth();
  const guard = useSessionGuard();
  const router = useRouter();

  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [patientRef, setPatientRef] = useState("");
  const [ageBand, setAgeBand] = useState<AgeBand | null>(null);
  const [sex, setSex] = useState<Sex | null>(null);
  const [answers, setAnswers] = useState<Record<string, Answer>>({});
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!session) return;
    api.questions(session.token)
      .then(setQuestions)
      .catch((e) => { if (!guard(e)) setError(e.message); });
  }, [session, guard]);

  const steps = useMemo(() => (questions ? toSteps(questions) : []), [questions]);
  const total = steps.length + 1; // patient details, then one step per group
  const dangerYes = questions?.some((q) => q.is_danger_sign && answers[q.code] === "yes");

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [step]);

  if (!questions) {
    return (
      <Screen title="New assessment" back="/">
        <ErrorMessage message={error} />
        {!error && <Loading label="Loading questions…" />}
      </Screen>
    );
  }

  const detailsDone = patientRef.trim() !== "" && ageBand !== null && sex !== null;
  const last = step === total - 1;

  async function submit() {
    if (!session || !ageBand || !sex) return;
    setBusy(true);
    setError(null);
    // Anything left blank is sent as "Not asked", which the model treats as missing.
    const full = Object.fromEntries(questions!.map((q) => [q.code, answers[q.code] ?? "unknown"]));
    try {
      const result = await api.submitAssessment(session.token, {
        patient_ref: patientRef.trim(), age_band: ageBand, sex, answers: full,
      });
      router.push(`/history/${result.id}`);
    } catch (e) {
      if (!guard(e)) setError(e instanceof Error ? e.message : "Could not submit.");
      setBusy(false);
    }
  }

  return (
    <Screen title="New assessment" back="/">
      <div className="flex flex-col gap-2">
        <p className="text-base text-slate-600">Step {step + 1} of {total}</p>
        <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200" aria-hidden>
          <div className="h-full bg-teal-700 transition-all" style={{ width: `${((step + 1) / total) * 100}%` }} />
        </div>
      </div>

      {dangerYes && (
        <p role="alert" className="rounded-xl bg-red-700 p-4 text-lg font-semibold text-white">
          Danger sign reported. Finish quickly and refer urgently.
        </p>
      )}

      {step === 0 ? (
        <section className="flex flex-col gap-5">
          <h2 className="text-xl font-bold">Patient</h2>
          <Field label="Patient code">
            <input className={inputClass} value={patientRef} onChange={(e) => setPatientRef(e.target.value)}
              placeholder="e.g. HH-014-2" maxLength={40} autoComplete="off" />
          </Field>
          <Choice label="Age" options={AGE_BANDS} value={ageBand} onChange={setAgeBand} />
          <Choice label="Sex" options={[{ value: "female", label: "Female" }, { value: "male", label: "Male" }]}
            value={sex} onChange={setSex} />
        </section>
      ) : (
        <section className="flex flex-col gap-4">
          <h2 className={`text-xl font-bold ${steps[step - 1].title === "Danger signs" ? "text-red-700" : ""}`}>
            {steps[step - 1].title}
          </h2>
          {steps[step - 1].questions.map((q) => (
            <fieldset key={q.code} className={`flex flex-col gap-3 rounded-xl border-2 bg-white p-4 ${q.is_danger_sign ? "border-red-300" : "border-slate-200"}`}>
              <legend className="sr-only">{q.text}</legend>
              <p className="text-lg font-medium" aria-hidden>{q.text}</p>
              <div className="grid grid-cols-3 gap-2">
                {CHOICES.map((c) => (
                  <button key={c.value} type="button" aria-pressed={answers[q.code] === c.value}
                    onClick={() => setAnswers((a) => ({ ...a, [q.code]: c.value }))}
                    className={`min-h-12 rounded-lg border-2 text-base font-semibold ${answers[q.code] === c.value ? CHOSEN[c.value] : "border-slate-300 bg-white"}`}>
                    {c.label}
                  </button>
                ))}
              </div>
            </fieldset>
          ))}
        </section>
      )}

      <ErrorMessage message={error} />

      <div className="sticky bottom-0 -mx-4 mt-auto flex gap-3 border-t border-slate-200 bg-slate-50 px-4 py-3">
        {step > 0 && <Button variant="secondary" onClick={() => setStep(step - 1)} disabled={busy}>Back</Button>}
        {last ? (
          <Button onClick={submit} disabled={busy}>{busy ? "Checking…" : "Get result"}</Button>
        ) : (
          <Button onClick={() => setStep(step + 1)} disabled={step === 0 && !detailsDone}>Next</Button>
        )}
      </div>
    </Screen>
  );
}

function Choice<T extends string>({ label, options, value, onChange }: {
  label: string; options: { value: T; label: string }[]; value: T | null; onChange: (v: T) => void;
}) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-2 text-base font-medium text-slate-800">{label}</legend>
      <div className="grid grid-cols-2 gap-2">
        {options.map((o) => (
          <button key={o.value} type="button" aria-pressed={value === o.value} onClick={() => onChange(o.value)}
            className={`min-h-12 rounded-lg border-2 text-base font-semibold ${value === o.value ? "border-teal-700 bg-teal-700 text-white" : "border-slate-300 bg-white"}`}>
            {o.label}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

export default function AssessPage() {
  return <RequireAuth><Assess /></RequireAuth>;
}
