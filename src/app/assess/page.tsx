"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  BackLink, Body, BottomBar, Button, ChoiceTile, Code, contained, ErrorNotice, Field, FieldError, inputClass,
  Loading, OfflineBanner, ProgressBar, TopBar, TopTitle, type Width,
} from "@/components/ui";
import { api, NetworkError } from "@/lib/api";
import { RequireAuth, useAuth, useSessionGuard } from "@/lib/auth";
import { AGE_BANDS, type AgeBand, type Answer, type Question, type Sex } from "@/lib/types";

const PAGE_SIZE = 5;

// Answers are kept on the phone as they are given, so a dropped connection or a closed
// tab never means asking the patient again. Cleared on a saved result or on Cancel.
const DRAFT_KEY = "chv-triage-draft";

interface Draft {
  patientRef: string;
  ageBand: AgeBand | null;
  sex: Sex | null;
  answers: Record<string, Answer>;
  step: number;
}

const EMPTY: Draft = { patientRef: "", ageBand: null, sex: null, answers: {}, step: 0 };

function loadDraft(): Draft {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    return raw ? { ...EMPTY, ...JSON.parse(raw) } : EMPTY;
  } catch {
    return EMPTY;
  }
}

function clearDraft() {
  try {
    localStorage.removeItem(DRAFT_KEY);
  } catch {}
}

const ANSWERS: { value: Answer; label: string; on: string }[] = [
  { value: "yes", label: "Yes", on: "border-blue bg-blue text-white" },
  { value: "no", label: "No", on: "border-ink bg-ink text-white" },
  { value: "unknown", label: "Not asked", on: "border-edge bg-edge text-white" },
];

function Assess() {
  const { session } = useAuth();
  const guard = useSessionGuard();
  const router = useRouter();

  // RequireAuth only renders this on the client, so reading storage here is safe.
  const [draft, setDraft] = useState<Draft>(loadDraft);
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [loadError, setLoadError] = useState<"offline" | string | null>(null);
  const [phase, setPhase] = useState<"form" | "checking" | "offline">("form");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [patientErrors, setPatientErrors] = useState<Partial<Record<"ref" | "age" | "sex", string>>>({});

  const { patientRef, ageBand, sex, answers, step } = draft;
  const update = (patch: Partial<Draft>) => setDraft((d) => ({ ...d, ...patch }));

  useEffect(() => {
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
    } catch {}
  }, [draft]);

  const fetchQuestions = useCallback(() => {
    if (!session) return;
    api.questions(session.token)
      .then(setQuestions)
      .catch((e) => { if (!guard(e)) setLoadError(e instanceof NetworkError ? "offline" : e.message); });
  }, [session, guard]);

  useEffect(fetchQuestions, [fetchQuestions]);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [step, phase]);

  const pages = useMemo(() => {
    const sorted = [...(questions ?? [])].sort((a, b) => a.display_order - b.display_order);
    const out: Question[][] = [];
    for (let i = 0; i < sorted.length; i += PAGE_SIZE) out.push(sorted.slice(i, i + PAGE_SIZE));
    return out;
  }, [questions]);

  const totalSteps = pages.length + 1;
  const ref = patientRef.trim();

  function cancel() {
    clearDraft();
    router.push("/");
  }

  function toQuestions() {
    const errors = {
      ref: ref ? undefined : "Enter a patient code",
      age: ageBand ? undefined : "Choose an age group",
      sex: sex ? undefined : "Choose female or male",
    };
    setPatientErrors(errors);
    if (!errors.ref && !errors.age && !errors.sex) update({ step: 1 });
  }

  async function submit() {
    if (!session || !questions || !ageBand || !sex) return;
    setPhase("checking");
    setSubmitError(null);
    try {
      const result = await api.submitAssessment(session.token, { patient_ref: ref, age_band: ageBand, sex, answers });
      clearDraft();
      router.replace(`/result/${result.id}`);
    } catch (e) {
      if (guard(e)) return;
      if (e instanceof NetworkError) setPhase("offline");
      else {
        setSubmitError(e instanceof Error ? e.message : "Could not check the answers.");
        setPhase("form");
      }
    }
  }

  /* ---------- loading the questions ---------- */
  if (!questions) {
    return (
      <>
        <TopBar left={<BackLink href="/" label="Cancel" />} width="medium" />
        <Body width="medium">
          {loadError === "offline" ? <OfflineBanner onRetry={() => { setLoadError(null); fetchQuestions(); }} />
            : loadError ? <ErrorNotice>{loadError}</ErrorNotice>
            : <Loading label="Loading questions…" />}
        </Body>
      </>
    );
  }

  const codeBar = <TopBar left={<TopTitle>New assessment</TopTitle>} right={<Code>{ref}</Code>} width="narrow" />;

  /* ---------- sending ---------- */
  if (phase === "checking") {
    return (
      <>
        {codeBar}
        <Body width="narrow">
          <div role="status" className="flex flex-1 flex-col items-center justify-center gap-4 text-center">
            <span className="h-16 w-16 animate-spin rounded-full border-[6px] border-track border-t-blue" aria-hidden />
            <p className="text-title font-bold">Checking answers…</p>
            <p className="text-body text-ink-soft">This can take up to a minute on slow data. Keep this screen open.</p>
          </div>
        </Body>
      </>
    );
  }

  if (phase === "offline") {
    return (
      <>
        {codeBar}
        <Body width="narrow">
          <OfflineBanner large />
          <div className="flex items-start gap-3 rounded-xl bg-green-tint p-4 text-body">
            <span aria-hidden className="flex h-6 w-6 flex-none items-center justify-center rounded-full bg-green text-small font-bold text-white">✓</span>
            <p>All {questions.length} answers are kept on this phone. You do not need to ask them again.</p>
          </div>
          <p className="text-body text-ink-soft">
            If the patient has a danger sign, do not wait for the result. Refer to the nearest health facility now.
          </p>
        </Body>
        <BottomBar width="narrow" className="md:flex-row-reverse md:[&>*]:flex-1">
          <Button onClick={submit}>Try again</Button>
          <Button variant="secondary" onClick={() => setPhase("form")}>Back to questions</Button>
        </BottomBar>
      </>
    );
  }

  /* ---------- step 1: patient ---------- */
  if (step === 0) {
    return (
      <>
        <TopBar left={<div className="flex items-center"><BackLink label="Cancel" onClick={cancel} /><TopTitle>New assessment</TopTitle></div>} width="narrow" />
        <StepHeader title="Patient" step={1} total={totalSteps} width="narrow" />
        <Body className="gap-6" width="narrow">
          <Field label="Patient code" error={patientErrors.ref && !ref ? patientErrors.ref : null}
            help={<span className="flex items-start gap-2 text-ink"><span aria-hidden className="mt-0.5 flex h-5 w-5 flex-none items-center justify-center rounded-full border-2 border-ink text-[12px] font-bold">!</span><span>Use a code only. <b>Never</b> write the patient&apos;s name or ID number.</span></span>}>
            <input className={`${inputClass(!!patientErrors.ref && !ref, true)} text-heading font-bold`} value={patientRef}
              onChange={(e) => update({ patientRef: e.target.value })} placeholder="P-017" maxLength={40} autoComplete="off" />
          </Field>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-label font-bold">Age (years)</legend>
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              {AGE_BANDS.map((b) => (
                <ChoiceTile key={b.value} selected={ageBand === b.value} onClick={() => update({ ageBand: b.value })}>{b.label}</ChoiceTile>
              ))}
            </div>
            {patientErrors.age && !ageBand && <FieldError>{patientErrors.age}</FieldError>}
          </fieldset>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-label font-bold">Sex</legend>
            <div className="grid grid-cols-2 gap-2">
              <ChoiceTile selected={sex === "female"} onClick={() => update({ sex: "female" })}>Female</ChoiceTile>
              <ChoiceTile selected={sex === "male"} onClick={() => update({ sex: "male" })}>Male</ChoiceTile>
            </div>
            {patientErrors.sex && !sex && <FieldError>{patientErrors.sex}</FieldError>}
          </fieldset>
        </Body>
        <BottomBar width="narrow"><Button onClick={toQuestions}>Next: questions →</Button></BottomBar>
      </>
    );
  }

  /* ---------- steps 2 to 8: five questions each ---------- */
  const page = pages[step - 1];
  const first = (step - 1) * PAGE_SIZE + 1;
  const answered = page.filter((q) => answers[q.code]).length;
  const complete = answered === page.length;
  const last = step === totalSteps - 1;

  // Built from the latest draft, not this render's copy, so quick taps never overwrite each other.
  const setAnswer = (code: string, value: Answer) =>
    setDraft((d) => {
      const next = { ...d.answers };
      if (next[code] === value) delete next[code]; // tap again to clear
      else next[code] = value;
      return { ...d, answers: next };
    });

  return (
    <>
      <TopBar left={<BackLink label={step === 1 ? "Patient" : "Back"} onClick={() => update({ step: step - 1 })} />} right={<Code>{ref}</Code>} width="medium" />
      <StepHeader title={`Questions ${first}–${first + page.length - 1} of ${questions.length}`} step={step + 1} total={totalSteps} width="medium" />
      <main className="flex-1 px-4">
        <div className={contained("medium")}>
          {page.map((q, i) => {
            const value = answers[q.code];
            const warn = q.is_danger_sign && value === "yes";
            return (
              <div key={q.code} role="group" aria-labelledby={`q-${q.code}`} className="border-b border-divider py-5">
                <div className={`flex flex-col gap-3 ${warn ? "rounded-xl border-2 border-red p-3" : ""}`}>
                  {q.is_danger_sign && (
                    <span className="flex items-center gap-2 text-small font-bold text-red">
                      <span aria-hidden className="h-2.5 w-2.5 rounded-full bg-red" />Danger sign
                    </span>
                  )}
                  <p id={`q-${q.code}`} className="flex gap-2 text-question">
                    <b className="min-w-7 text-ink-soft">{first + i}</b>
                    <span>{q.text}</span>
                  </p>
                  <div className="grid grid-cols-[1fr_1fr_1.3fr] gap-2 md:max-w-lg md:pl-9">
                    {ANSWERS.map((a) => (
                      <button key={a.value} type="button" aria-pressed={value === a.value} onClick={() => setAnswer(q.code, a.value)}
                        className={`h-14 rounded-[10px] border-2 px-1 text-label font-bold ${value === a.value ? a.on : "border-edge bg-white text-ink"}`}>
                        {value === a.value && "✓ "}{a.label}
                      </button>
                    ))}
                  </div>
                  {warn && (
                    <div className="flex items-start gap-2.5 rounded-[10px] bg-red-tint p-3 text-small">
                      <span aria-hidden className="flex h-6 w-6 flex-none items-center justify-center rounded-md bg-red font-bold text-white">!</span>
                      <span><b>Danger sign.</b> The result will tell you to refer urgently.</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          {submitError && last && <div className="py-4"><ErrorNotice>{submitError}</ErrorNotice></div>}
        </div>
      </main>
      <BottomBar width="medium">
        <p className="text-center text-small text-ink-soft">
          {complete ? `All ${page.length} answered` : `${answered} of ${page.length} answered · answer all to continue`}
        </p>
        <div className="grid grid-cols-[1fr_2fr] gap-3">
          <Button variant="secondary" onClick={() => update({ step: step - 1 })}>Back</Button>
          {last
            ? <Button onClick={submit} disabled={!complete}>Get result</Button>
            : <Button onClick={() => update({ step: step + 1 })} disabled={!complete}>Next →</Button>}
        </div>
      </BottomBar>
    </>
  );
}

function StepHeader({ title, step, total, width }: { title: string; step: number; total: number; width: Width }) {
  return (
    <div className="flex-none border-b border-divider px-4 py-3">
      <div className={`flex flex-col gap-2 ${contained(width)}`}>
        <div className="flex justify-between text-small">
          <b>{title}</b>
          <span className="text-ink-soft">Step {step} of {total}</span>
        </div>
        <ProgressBar value={step / total} />
      </div>
    </div>
  );
}

export default function AssessPage() {
  return <RequireAuth><Assess /></RequireAuth>;
}
