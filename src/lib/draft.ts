// The assessment in progress, kept on the phone so a dropped connection or a closed tab
// never means asking the patient again. Each draft records which volunteer started it, so
// it is never shown to, or sent under, a different account on a shared phone.

import { AGE_BANDS, type AgeBand, type Answer, type Question, type Sex } from "./types";

const DRAFT_KEY = "chv-triage-draft";

export interface Draft {
  userId: string | null;
  patientRef: string;
  ageBand: AgeBand | null;
  sex: Sex | null;
  answers: Record<string, Answer>;
  step: number;
}

export const emptyDraft = (userId: string | null): Draft =>
  ({ userId, patientRef: "", ageBand: null, sex: null, answers: {}, step: 0 });

function readRaw(): Partial<Draft> | null {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    return raw ? (JSON.parse(raw) as Partial<Draft>) : null;
  } catch {
    return null;
  }
}

/** The saved draft, but only if this volunteer started it. */
export function loadDraft(userId: string | null): Draft {
  const saved = readRaw();
  if (!saved || !userId || saved.userId !== userId) return emptyDraft(userId);
  return { ...emptyDraft(userId), ...saved, userId };
}

const ANSWER_VALUES: readonly string[] = ["yes", "no", "unknown"];

/**
 * Makes a saved draft safe to use with the questions the backend serves now. A draft saved
 * before the question list changed (or edited by hand) could point at a page that no longer
 * exists, or hold answers for codes the backend would reject. Unknown codes and values are
 * dropped, and the step is brought back into range; the volunteer then answers whatever is
 * missing, since Next stays locked until a page is complete.
 */
export function reconcileDraft(draft: Draft, questions: Question[], pageSize: number): Draft {
  const codes = new Set(questions.map((q) => q.code));
  const danger = new Set(questions.filter((q) => q.is_danger_sign).map((q) => q.code));
  const answers: Record<string, Answer> = {};
  for (const [code, value] of Object.entries(draft.answers ?? {})) {
    if (!codes.has(code) || !ANSWER_VALUES.includes(value)) continue;
    if (danger.has(code) && value === "unknown") continue; // danger signs need yes or no
    answers[code] = value;
  }
  const patientRef = typeof draft.patientRef === "string" ? draft.patientRef : "";
  const ageBand = AGE_BANDS.some((b) => b.value === draft.ageBand) ? draft.ageBand : null;
  const sex = draft.sex === "female" || draft.sex === "male" ? draft.sex : null;
  const pages = Math.ceil(questions.length / pageSize);
  let step = Number.isInteger(draft.step) ? Math.min(Math.max(draft.step, 0), pages) : 0;
  if (!patientRef.trim() || !ageBand || !sex) step = 0;
  return { ...draft, patientRef, ageBand, sex, answers, step };
}

export function saveDraft(draft: Draft) {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
  } catch {}
}

export function clearDraft() {
  try {
    localStorage.removeItem(DRAFT_KEY);
  } catch {}
}

/** Removes a draft left by another volunteer (or by a version of the app that did not record one). */
export function clearDraftUnlessOwnedBy(userId: string | null) {
  const saved = readRaw();
  if (saved && (!userId || saved.userId !== userId)) clearDraft();
}
