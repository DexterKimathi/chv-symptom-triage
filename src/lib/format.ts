// Display helpers. Dates use day-month order as written in Kenya.

import { AGE_BANDS, type AgeBand, type AssessmentSummary, type Sex } from "./types";

const time = (d: Date) => d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });

function sameDay(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

/** "Today 10:42", "Yesterday" or "2 Oct", for lists. */
export function shortWhen(iso: string): { day: string; time?: string } {
  const d = new Date(iso);
  const now = new Date();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (sameDay(d, now)) return { day: "Today", time: time(d) };
  if (sameDay(d, yesterday)) return { day: "Yesterday" };
  return { day: d.toLocaleDateString("en-GB", { day: "numeric", month: "short" }) };
}

/** "1 Oct 2026, 14:02" */
export function fullWhen(iso: string) {
  const d = new Date(iso);
  return `${d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}, ${time(d)}`;
}

/** "Today 11:20", or the full date for anything older. */
export function whenLabel(iso: string) {
  const d = new Date(iso);
  return sameDay(d, new Date()) ? `Today ${time(d)}` : fullWhen(iso);
}

// When the backend did not send a patient detail, say so. Never guess it.
export const ageLabel = (band?: AgeBand | null) =>
  AGE_BANDS.find((b) => b.value === band)?.label ?? "Age not recorded";

export function sexLabel(sex?: Sex | null) {
  if (sex === "female") return "Female";
  if (sex === "male") return "Male";
  return "Sex not recorded";
}

export const refLabel = (ref?: string | null) => ref?.trim() || "No code";

// The same rule as the backend: a Kenyan mobile number written 07…, 01…, +2547…, 2547…
// (or +2541…, 2541…), with or without spaces and hyphens.
const KENYAN_MOBILE = /^(?:0|\+?254)([17]\d{8})$/;

/** The local form, 0712345678, or null if this is not a Kenyan mobile number. */
export function normalisePhone(phone: string): string | null {
  const match = KENYAN_MOBILE.exec(phone.replace(/[\s-]/g, ""));
  return match ? `0${match[1]}` : null;
}

/** 0711111111 shown as "0711 111 111". Anything else is shown as typed. */
export function phoneLabel(phone: string) {
  const digits = phone.replace(/\D/g, "");
  return digits.length === 10 ? `${digits.slice(0, 4)} ${digits.slice(4, 7)} ${digits.slice(7)}` : phone;
}

/** Rounded percentage. A non-zero chance never shows as 0%, and the model is never shown
 *  as certain: anything that would round to 100% reads ">99%". */
export function percent(probability: number) {
  const rounded = Math.round(probability * 100);
  if (rounded === 0) return "under 1%";
  if (rounded >= 100) return ">99%";
  return `${rounded}%`;
}

/** One-line status for a history row. */
export function summaryLabel(a: AssessmentSummary) {
  if (a.outcome === "urgent_referral") return "Refer urgently now";
  if (a.outcome === "likely_condition") return `Likely: ${a.top_condition}`;
  if (a.outcome === "too_close_to_call") return "Too close to call";
  return "No clear match";
}
