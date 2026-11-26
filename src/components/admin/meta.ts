// Names, colours and small helpers shared by the admin screens.

import type { DashboardRecord } from "@/lib/types";

/** Each condition keeps one colour on every chart. The order is checked for colour-blind safety;
 *  every chart also names its series, so colour is never the only clue. */
const CONDITION_META: Record<string, { short: string; color: string }> = {
  malaria: { short: "Malaria", color: "#2a78d6" },
  typhoid: { short: "Typhoid", color: "#eb6834" },
  urti_pneumonia: { short: "Respiratory", color: "#1baf7a" },
  diarrhoeal: { short: "Diarrhoeal", color: "#eda100" },
  uti: { short: "Urinary tract", color: "#e87ba4" },
  unclear: { short: "Unclear", color: "#898781" },
  // Red means one thing in this app: refer urgently.
  urgent: { short: "Urgent referral", color: "#b3261e" },
};

export const shortName = (code: string) => CONDITION_META[code]?.short ?? code.replaceAll("_", " ");
export const colorOf = (code: string) => CONDITION_META[code]?.color ?? "#898781";

export const PERIODS = [
  { days: 7, label: "7 days", previous: "previous 7 days" },
  { days: 28, label: "28 days", previous: "previous 28 days" },
  { days: 84, label: "12 weeks", previous: "previous 12 weeks" },
] as const;

export const periodMeta = (days: number) => PERIODS.find((p) => p.days === days) ?? PERIODS[1];

/** "2026-11-20" as "20 Nov". Read as a calendar date, so no time zone can move it. */
export function dayLabel(isoDate: string, year = false) {
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-GB", { day: "numeric", month: "short", ...(year ? { year: "numeric" } : {}) });
}

export const share = (part: number, whole: number) => (whole ? `${Math.round((part / whole) * 100)}%` : "–");

/** A CSV cell. Text starting like a spreadsheet formula is defused, because names are typed by people. */
function cell(value: string | number) {
  let text = String(value);
  if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}

export function downloadCsv(records: DashboardRecord[], filename: string) {
  const header = ["Date and time (UTC)", "Patient code", "Age group", "Sex", "Volunteer", "Area", "Counted as", "Result shown"];
  const rows = records.map((r) => [r.created_at, r.patient_ref, r.age_band, r.sex, r.volunteer, r.area, shortName(r.category), r.headline]);
  const text = [header, ...rows].map((row) => row.map(cell).join(",")).join("\r\n");
  // The byte-order mark makes Excel read the file as UTF-8.
  const url = URL.createObjectURL(new Blob(["﻿", text], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/* ---------- filters carried between admin screens ---------- */

export interface RecordFilters {
  search: string;
  area: string;
  volunteer: string;
  result: string;
}

export const NO_FILTERS: RecordFilters = { search: "", area: "", volunteer: "", result: "" };

// Kept outside React so they survive opening a record and coming back.
let remembered: RecordFilters = NO_FILTERS;
export const readFilters = () => remembered;
export const rememberFilters = (filters: Partial<RecordFilters>) => {
  remembered = { ...NO_FILTERS, ...filters };
};
