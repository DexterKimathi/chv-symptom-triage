"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  BackLink, Body, BottomBar, Button, ChoiceTile, Code, contained, ErrorNotice, Field, FieldError, inputClass,
  Loading, OfflineBanner, ProgressBar, Spinner, TopBar, TopTitle, type Width,
} from "@/components/ui";
import { api, NetworkError } from "@/lib/api";
import { RequireAuth, useAuth, useSessionGuard } from "@/lib/auth";
import { clearDraft, loadDraft, reconcileDraft, saveDraft, type Draft } from "@/lib/draft";
import { AGE_BANDS, type Answer, type Question } from "@/lib/types";

const PAGE_SIZE = 5;

const ANSWERS: { value: Answer; label: string; on: string }[] = [
  { value: "yes", label: "Yes", on: "border-blue bg-blue text-white" },
  { value: "no", label: "No", on: "border-ink bg-ink text-white" },
  { value: "unknown", label: "Not asked", on: "border-edge bg-edge text-white" },
];
// A danger sign must be checked on every patient, so those questions have no "Not asked".
// The backend rejects "unknown" for them too.
const DANGER_ANSWERS = ANSWERS.filter((a) => a.value !== "unknown");

function Assess() {
  const { session, userId } = useAuth();
  const guard = useSessionGuard();
  const router = useRouter();

  // RequireAuth only renders this on the client, so reading storage here is safe.
  // Only this volunteer's own draft is restored.
  const [draft, setDraft] = useState<Draft>(() => loadDraft(userId));
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [loadError, setLoadError] = useState<"offline" | string | null>(null);
  const [phase, setPhase] = useState<"form" | "checking" | "offline">("form");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [patientErrors, setPatientErrors] = useState<Partial<Record<"ref" | "age" | "sex", string>>>({});
  const [thinking, setThinking] = useState(false);
  const [nextError, setNextError] = useState<"offline" | string | null>(null);

  const { patientRef, ageBand, sex, answers, step, mode, trail } = draft;
  const adaptive = mode === "adaptive";
  const update = (patch: Partial<Draft>) => setDraft((d) => ({ ...d, ...patch }));

  useEffect(() => saveDraft(draft), [draft]);

  const fetchQuestions = useCallback(() => {
    if (!session) return;
    api.questions(session.token)
      .then((list) => {
        setDraft((d) => reconcileDraft(d, list, PAGE_SIZE));
        setQuestions(list);
      })
      .catch((e) => { if (!guard(e)) setLoadError(e instanceof NetworkError ? "offline" : e.message); });
  }, [session, guard]);

  useEffect(fetchQuestions, [fetchQuestions]);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [step, phase]);

  const pages = useMemo(() => {
    // Danger signs come first, as in IMCI: check them before anything else, so an urgent
    // case can be sent from the first page. The rest follow in the backend's display order.
    const sorted = [...(questions ?? [])].sort(
      (a, b) => Number(b.is_danger_sign) - Number(a.is_danger_sign) || a.display_order - b.display_order,
    );
    const out: Question[][] = [];
    for (let i = 0; i < sorted.length; i += PAGE_SIZE) out.push(sorted.slice(i, i + PAGE_SIZE));
    return out;
  }, [questions]);

  const totalSteps = pages.length + 1;
  const ref = patientRef.trim();
  const dangerQuestions = (questions ?? []).filter((q) => q.is_danger_sign);
  // Every danger sign answered yes or no, with at least one yes: the result is urgent
  // whatever the other answers are.
  const dangerChecked =
    dangerQuestions.some((q) => answers[q.code] === "yes") &&
    dangerQuestions.every((q) => answers[q.code] === "yes" || answers[q.code] === "no");

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

  // Every question not asked goes as "Not asked": after the adaptive questions stop, or when a
  // volunteer with a danger sign sends straight away. The danger signs themselves are always
  // answered by then.
  async function submit(given: Record<string, Answer> = answers) {
    if (!session || !questions || !ageBand || !sex) return;
    setPhase("checking");
    setSubmitError(null);
    const sent = Object.fromEntries(questions.map((q) => [q.code, given[q.code] ?? "unknown"]));
    try {
      const result = await api.submitAssessment(session.token, { patient_ref: ref, age_band: ageBand, sex, answers: sent });
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

  // Adaptive questioning: ask the backend for the most informative next question, or send
  // the assessment when it says the answers are enough.
  async function askNext(current: Record<string, Answer>, trailNow: string[]) {
    if (!session || !ageBand || !sex) return;
    setThinking(true);
    setNextError(null);
    try {
      const r = await api.nextQuestion(session.token, { age_band: ageBand, sex, answers: current });
      if (r.done || !r.next_question) {
        setThinking(false);
        await submit(current);
        return;
      }
      const code = r.next_question;
      setDraft((d) => ({ ...d, answers: current, trail: [...trailNow, code], step: 2 }));
    } catch (e) {
      if (!guard(e)) setNextError(e instanceof NetworkError ? "offline" : (e as Error).message);
    } finally {
      setThinking(false);
    }
  }

  function answerAdaptive(code: string, value: Answer) {
    // Questions after this one were chosen from the old answer, so they are dropped.
    const idx = trail.indexOf(code);
    const trailNow = trail.slice(0, idx + 1);
    const current = { ...answers, [code]: value };
    for (const later of trail.slice(idx + 1)) delete current[later];
    setDraft((d) => ({ ...d, answers: current, trail: trailNow }));
    void askNext(current, trailNow);
  }

  function backAdaptive() {
    const rest = trail.slice(0, -1);
    const current = { ...answers };
    delete current[trail[trail.length - 1]];
    setNextError(null);
    setDraft((d) => ({ ...d, answers: current, trail: rest, step: rest.length ? 2 : 1 }));
  }

  const useFullChecklist = () => {
    setNextError(null);
    update({ mode: "full", step: 1 });
  };

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
            <p>All {Object.keys(answers).length} answers given so far are kept on this phone. You do not need to ask them again.</p>
          </div>
          <p className="text-body text-ink-soft">
            If the patient has a danger sign, do not wait for the result. Refer to the nearest health facility now.
          </p>
        </Body>
        <BottomBar width="narrow" className="md:flex-row-reverse md:[&>*]:flex-1">
          <Button onClick={() => submit()}>Try again</Button>
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

  // Built from the latest draft, not this render's copy, so quick taps never overwrite each other.
  const setAnswer = (code: string, value: Answer) =>
    setDraft((d) => {
      const next = { ...d.answers };
      if (next[code] === value) delete next[code]; // tap again to clear
      else next[code] = value;
      return { ...d, answers: next };
    });

  const card = (q: Question, number: number, onAnswer: (code: string, v: Answer) => void, disabled = false) => {
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
            <b className="min-w-7 text-ink-soft">{number}</b>
            <span>{q.text}</span>
          </p>
          <div className={`grid gap-2 md:max-w-lg md:pl-9 ${q.is_danger_sign ? "grid-cols-2" : "grid-cols-[1fr_1fr_1.3fr]"}`}>
            {(q.is_danger_sign ? DANGER_ANSWERS : ANSWERS).map((a) => (
              <button key={a.value} type="button" aria-pressed={value === a.value} disabled={disabled}
                onClick={() => onAnswer(q.code, a.value)}
                className={`h-14 rounded-[10px] border-2 px-1 text-label font-bold disabled:opacity-60 ${value === a.value ? a.on : "border-edge bg-white text-ink"}`}>
                {value === a.value && "✓ "}{a.label}
              </button>
            ))}
          </div>
          {q.is_danger_sign && !value && (
            <p className="text-small text-ink-soft md:pl-9">Yes or No is needed. Look at the patient or ask the caregiver.</p>
          )}
          {warn && (
            <div className="flex flex-col gap-3 rounded-[10px] bg-red-tint p-3 text-small">
              <div className="flex items-start gap-2.5">
                <span aria-hidden className="flex h-6 w-6 flex-none items-center justify-center rounded-md bg-red font-bold text-white">!</span>
                <span>
                  <b>Danger sign.</b>{" "}
                  {dangerChecked
                    ? "Refer urgently. You can get the result now without the other questions."
                    : "The result will tell you to refer urgently. Answer the other danger signs to get it now."}
                </span>
              </div>
              {dangerChecked && (
                <button type="button" onClick={() => submit()}
                  className="h-12 rounded-[10px] bg-red text-label font-bold text-white hover:brightness-110">
                  Get urgent result now
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    );
  };

  const nextProblem = nextError && (
    <div className="flex flex-col gap-3 py-4">
      {nextError === "offline"
        ? <OfflineBanner detail="Your answers are kept on this phone." onRetry={() => void askNext(answers, trail)} />
        : <ErrorNotice>{nextError}</ErrorNotice>}
      <Button variant="secondary" onClick={useFullChecklist}>Answer all 35 questions instead</Button>
    </div>
  );

  /* ---------- adaptive: the three danger signs ---------- */
  if (adaptive && step === 1) {
    const dangerDone = dangerQuestions.every((q) => answers[q.code] === "yes" || answers[q.code] === "no");
    return (
      <>
        <TopBar left={<BackLink label="Patient" onClick={() => update({ step: 0 })} />} right={<Code>{ref}</Code>} width="medium" />
        <AdaptiveHeader title="Danger signs first" detail="Questions 1–3" width="medium" />
        <main className="flex-1 px-4">
          <div className={contained("medium")}>
            {dangerQuestions.map((q, i) => card(q, i + 1, setAnswer, thinking))}
            {nextProblem}
            {submitError && <div className="py-4"><ErrorNotice>{submitError}</ErrorNotice></div>}
          </div>
        </main>
        <BottomBar width="medium">
          <p className="text-center text-small text-ink-soft">
            {dangerDone ? "After these, the app asks only the questions it needs." : "Answer all three danger signs to continue"}
          </p>
          <div className="grid grid-cols-[1fr_2fr] gap-3">
            <Button variant="secondary" onClick={() => update({ step: 0 })}>Back</Button>
            <Button onClick={() => void askNext(answers, [])} disabled={!dangerDone} loading={thinking}>Next →</Button>
          </div>
        </BottomBar>
      </>
    );
  }

  /* ---------- adaptive: one question at a time, chosen by the model ---------- */
  if (adaptive && step === 2 && trail.length) {
    const code = trail[trail.length - 1];
    const q = questions.find((x) => x.code === code);
    if (q) {
      const number = dangerQuestions.length + trail.length;
      return (
        <>
          <TopBar left={<BackLink label="Back" onClick={backAdaptive} />} right={<Code>{ref}</Code>} width="medium" />
          <AdaptiveHeader title={`Question ${number}`} detail="Chosen from the answers so far" width="medium" />
          <main className="flex-1 px-4">
            <div className={contained("medium")}>
              {card(q, number, answerAdaptive, thinking)}
              <p className="py-4 text-small text-ink-soft">
                The app asks the question that tells it most about this patient, and stops as soon as it has
                enough to give a result. Most patients need about half of the 35 questions.
              </p>
              {nextProblem}
            </div>
          </main>
          <BottomBar width="medium">
            {thinking
              ? <p role="status" className="flex h-14 items-center justify-center gap-3 text-label text-ink-soft"><Spinner /> Choosing the next question…</p>
              : <Button variant="secondary" onClick={useFullChecklist}>Answer all 35 questions instead</Button>}
          </BottomBar>
        </>
      );
    }
  }

  /* ---------- steps 2 to 8: five questions each ---------- */
  const page = pages[step - 1];
  if (!page) {
    // Only possible if the backend sent no questions; never index past the last page.
    return (
      <>
        <TopBar left={<BackLink href="/" label="Cancel" />} width="medium" />
        <Body width="medium"><ErrorNotice>No questions were loaded. Please try again later.</ErrorNotice></Body>
      </>
    );
  }
  const first = (step - 1) * PAGE_SIZE + 1;
  const isAnswered = (q: Question) =>
    q.is_danger_sign ? answers[q.code] === "yes" || answers[q.code] === "no" : !!answers[q.code];
  const answered = page.filter(isAnswered).length;
  const complete = answered === page.length;
  const last = step === totalSteps - 1;

  return (
    <>
      <TopBar left={<BackLink label={step === 1 ? "Patient" : "Back"} onClick={() => update({ step: step - 1 })} />} right={<Code>{ref}</Code>} width="medium" />
      <StepHeader title={`Questions ${first}–${first + page.length - 1} of ${questions.length}`} step={step + 1} total={totalSteps} width="medium" />
      <main className="flex-1 px-4">
        <div className={contained("medium")}>
          {page.map((q, i) => card(q, first + i, setAnswer))}
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
            ? <Button onClick={() => submit()} disabled={!complete}>Get result</Button>
            : <Button onClick={() => update({ step: step + 1 })} disabled={!complete}>Next →</Button>}
        </div>
      </BottomBar>
    </>
  );
}

function AdaptiveHeader({ title, detail, width }: { title: string; detail: string; width: Width }) {
  return (
    <div className="flex-none border-b border-divider px-4 py-3">
      <div className={`flex justify-between text-small ${contained(width)}`}>
        <b>{title}</b>
        <span className="text-ink-soft">{detail}</span>
      </div>
    </div>
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
