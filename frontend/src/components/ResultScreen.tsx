"use client";

// One layout for a fresh result and a saved one, since the backend returns a saved
// assessment exactly as it was first shown. Order on every result: what was found, then
// what to do (the largest, solid block), then supporting detail, then the disclaimer.

import { useEffect, useState } from "react";

import { Alert, BackLink, BottomBar, ButtonLink, Code, contained, Disclaimer, ErrorNotice, Loading, OfflineBanner, TopBar, TopTitle } from "./ui";
import { api, ApiError, NetworkError } from "@/lib/api";
import { useAuth, useSessionGuard } from "@/lib/auth";
import { ageLabel, fullWhen, percent, refLabel, sexLabel, whenLabel } from "@/lib/format";
import type { Answer, Assessment } from "@/lib/types";

/** Each referral level gets one band colour. Red is reserved for urgent referral. */
const REFERRAL: Record<string, { title: string; head: string; body: string }> = {
  refer_same_day: { title: "Refer today", head: "bg-amber text-ink", body: "border-amber bg-amber-tint" },
  refer_routine: { title: "Refer within 1–2 days", head: "bg-blue text-white", body: "border-blue bg-blue-tint" },
  refer_for_assessment: { title: "Refer for assessment", head: "bg-blue text-white", body: "border-blue bg-blue-tint" },
  home_care_and_monitor: { title: "Care at home and watch", head: "bg-green text-white", body: "border-green bg-green-tint" },
};

const NOT_FOUND = "Assessment not found";

/** Assessment ids are whole numbers from 1 up to the database's integer limit. */
const isAssessmentId = (id: string) => /^[1-9]\d{0,9}$/.test(id) && Number(id) <= 2_147_483_647;

const ANSWER_LABEL: Record<Answer, string> = { yes: "Yes", no: "No", unknown: "Not asked" };

async function fetchResult(token: string, id: string) {
  const assessment = await api.assessment(token, id);
  let dangerTexts: string[] = [];
  if (assessment.danger_signs_present.length > 0) {
    // The result stores question codes; show the volunteer the questions they answered.
    const questions = await api.questions(token).catch(() => []);
    const byCode = new Map(questions.map((q) => [q.code, q.text]));
    dangerTexts = assessment.danger_signs_present.map((code) => byCode.get(code) ?? code.replaceAll("_", " "));
  }
  return { assessment, dangerTexts };
}

export function ResultScreen({ id, saved }: { id: string; saved: boolean }) {
  const { session } = useAuth();
  const guard = useSessionGuard();
  const [result, setResult] = useState<Assessment | null>(null);
  const [dangerTexts, setDangerTexts] = useState<string[]>([]);
  const [error, setError] = useState<"offline" | string | null>(null);

  const [attempt, setAttempt] = useState(0);

  // A mistyped or edited link is "not found", not a validation message from the server.
  const validId = isAssessmentId(id);

  useEffect(() => {
    if (!session || !validId) return;
    fetchResult(session.token, id)
      .then(({ assessment, dangerTexts }) => { setDangerTexts(dangerTexts); setResult(assessment); })
      .catch((e) => {
        if (guard(e)) return;
        if (e instanceof NetworkError) setError("offline");
        else if (e instanceof ApiError && (e.status === 404 || e.status === 422)) setError(NOT_FOUND);
        else setError((e as Error).message);
      });
  }, [session, id, validId, guard, attempt]);

  const homeBar = saved
    ? <TopBar left={<BackLink href="/" label="Home" />} right={result && <Code>{refLabel(result.patient_ref)}</Code>} />
    : <TopBar left={<TopTitle>Result</TopTitle>} right={result && <Code>{refLabel(result.patient_ref)}</Code>} />;

  if (!validId) {
    return (
      <>
        {homeBar}
        <main className={`flex flex-1 flex-col px-4 py-5 md:py-8 ${contained("wide")}`}>
          <ErrorNotice>{NOT_FOUND}</ErrorNotice>
        </main>
      </>
    );
  }

  if (!result) {
    return (
      <>
        {homeBar}
        <main className={`flex flex-1 flex-col px-4 py-5 md:py-8 ${contained("wide")}`}>
          {error === "offline" ? <OfflineBanner onRetry={() => { setError(null); setAttempt((n) => n + 1); }} />
            : error ? <ErrorNotice>{error}</ErrorNotice>
            : <Loading label="Loading result…" />}
        </main>
      </>
    );
  }

  const urgent = result.outcome === "urgent_referral";
  const meta = `${ageLabel(result.age_band)} · ${sexLabel(result.sex)} · ${saved ? fullWhen(result.created_at) : whenLabel(result.created_at)}`;

  return (
    <>
      {/* A fresh urgent result opens straight onto the red block, with nothing above it. */}
      {(saved || !urgent) && homeBar}
      {saved && (
        <div className="border-b border-divider bg-surface px-4 py-3 text-small">
          <div className={contained("wide")}>
            <p className="font-bold">Saved record · cannot be changed</p>
            <p className="text-ink-soft">Shown exactly as on {fullWhen(result.created_at)} · model {result.model_version}</p>
          </div>
        </div>
      )}

      {urgent ? (
        <div role="alert" className="bg-red px-4 pt-4 pb-5 text-white md:py-8">
          <div className={`flex flex-col gap-3 ${contained("wide")}`}>
            {!saved && (
              <div className="flex items-start justify-between gap-3 text-small">
                <Code className="whitespace-nowrap">{refLabel(result.patient_ref)}</Code><span className="text-right">{meta}</span>
              </div>
            )}
            {saved && <p className="text-small">{meta}</p>}
            <div className="flex items-start gap-3">
              <Alert size={48} inverse />
              <p className="text-display font-bold">Refer urgently now</p>
            </div>
            <p className="text-body md:max-w-3xl">{result.guidance}</p>
          </div>
        </div>
      ) : null}

      {/* Two columns on a laptop: the finding and what to do on the left, detail on the right.
          On a phone the same blocks stack in the design's order. */}
      <main className="flex-1 px-4 py-5 md:py-8">
        <div className={`flex flex-col gap-5 lg:grid lg:grid-cols-2 lg:items-start lg:gap-x-12 ${contained("wide")}`}>
          <div className="flex flex-col gap-5">
            {urgent ? (
              <section className="flex flex-col gap-3">
                <h2 className="text-label font-bold">{dangerTexts.length > 1 ? "Danger signs found" : "Danger sign found"}</h2>
                {dangerTexts.map((text) => (
                  <div key={text} className="flex items-start gap-3 rounded-xl border-2 border-red bg-red-tint p-3 text-body">
                    <Alert />
                    <p>{text}<br /><b>Yes</b></p>
                  </div>
                ))}
              </section>
            ) : (
              <>
                <p className="text-small text-ink-soft">{meta}</p>
                <Finding result={result} />
                <WhatToDo level={result.referral_level} guidance={result.guidance} />
              </>
            )}
          </div>
          <div className="flex flex-col gap-5">
            {!urgent && result.outcome === "likely_condition" && <LessLikely result={result} />}
            {!urgent && result.explanation.length > 0 && (
              <section>
                <h2 className="text-label font-bold">Based on:</h2>
                {result.explanation.map((e) => (
                  <div key={e.question} className="flex items-start justify-between gap-3 border-b border-divider py-3 text-body">
                    <span>{e.question}</span>
                    <span className={`flex-none rounded-md px-2 py-0.5 text-label font-bold ${e.answer === "yes" ? "bg-blue-tint text-blue" : "bg-surface text-ink"}`}>
                      {ANSWER_LABEL[e.answer]}
                    </span>
                  </div>
                ))}
              </section>
            )}
            <Disclaimer text={result.disclaimer} />
          </div>
        </div>
      </main>

      {!saved && (
        <BottomBar className="md:items-end md:[&>*]:max-w-sm">
          <ButtonLink href="/" variant="secondary">Done, back to home</ButtonLink>
        </BottomBar>
      )}
    </>
  );
}

function Finding({ result }: { result: Assessment }) {
  const [first, second] = result.top;

  if (result.outcome === "likely_condition") {
    return (
      <section className="flex flex-col gap-3">
        <h1 className="text-headline font-bold">Likely: {first.name}</h1>
        <div className="flex flex-col gap-2">
          <div className="flex items-end justify-between">
            <span className="text-small text-ink-soft">Confidence</span>
            <b className="text-heading">{percent(first.probability)}</b>
          </div>
          <div className="h-3 overflow-hidden rounded-md bg-track" aria-hidden>
            <div className="h-full rounded-md bg-ink" style={{ width: `${Math.min(99, Math.round(first.probability * 100))}%` }} />
          </div>
        </div>
      </section>
    );
  }

  if (result.outcome === "too_close_to_call" && second) {
    // Listed A to Z so the order does not suggest one is more likely.
    const pair = [first, second].sort((a, b) => a.name.localeCompare(b.name));
    return (
      <section className="flex flex-col gap-3">
        <h1 className="text-headline font-bold">Too close to call</h1>
        <p className="text-body">Could be either of these:</p>
        <div className="flex items-center gap-2">
          <span className="flex min-h-20 flex-1 items-center justify-center rounded-xl border-2 border-ink p-3 text-center text-heading font-bold">{pair[0].name}</span>
          <span className="text-small text-ink-soft">or</span>
          <span className="flex min-h-20 flex-1 items-center justify-center rounded-xl border-2 border-ink p-3 text-center text-heading font-bold">{pair[1].name}</span>
        </div>
        <p className="text-small text-ink-soft">Neither is more likely. Listed A to Z. A test at the facility is needed to tell them apart.</p>
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-2">
      <h1 className="text-headline font-bold">No clear match</h1>
      <p className="text-body">Symptoms do not clearly match one condition.</p>
    </section>
  );
}

function WhatToDo({ level, guidance }: { level: string; guidance: string }) {
  const style = REFERRAL[level] ?? REFERRAL.refer_for_assessment;
  return (
    <section className={`overflow-hidden rounded-xl border-2 ${style.body}`}>
      <div className={`px-4 py-3 ${style.head}`}>
        <p className="text-small font-bold">What to do</p>
        <h2 className="text-headline font-bold">{style.title}</h2>
      </div>
      <p className="px-4 py-3 text-body">{guidance}</p>
    </section>
  );
}

function LessLikely({ result }: { result: Assessment }) {
  const others = result.top.slice(1);
  if (others.length === 0) return null;
  return (
    <section>
      <h2 className="text-label font-bold">Less likely</h2>
      {others.map((c) => (
        <div key={c.code} className="flex justify-between border-b border-divider py-3 text-body">
          <span>{c.name}</span>
          <span className="text-ink-soft">{percent(c.probability)}</span>
        </div>
      ))}
    </section>
  );
}
