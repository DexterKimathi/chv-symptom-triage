// Cards, figures and table pieces for the admin screens.

import type { ReactNode } from "react";

import { colorOf, shortName } from "./meta";

export function Card({ title, note, action, children, className = "" }: {
  title?: string; note?: ReactNode; action?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`flex min-w-0 flex-col gap-4 rounded-xl border border-divider bg-white p-5 ${className}`}>
      {title && (
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-label font-bold">{title}</h2>
            {note && <p className="text-small text-ink-soft">{note}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

/** One headline number, with its change from the period before when there is one. */
export function StatTile({ label, value, previous, against, detail, urgent = false }: {
  label: string; value: number | string; previous?: number; against?: string; detail?: ReactNode; urgent?: boolean;
}) {
  const change = typeof value === "number" && previous !== undefined ? value - previous : null;
  return (
    <div className={`flex flex-col gap-1 rounded-xl border bg-white p-5 ${urgent ? "border-red border-l-8" : "border-divider"}`}>
      <p className="text-small font-bold text-ink-soft">{label}</p>
      <p className={`text-[40px] leading-[48px] font-bold ${urgent ? "text-red" : ""}`}>{value}</p>
      <p className="text-small text-ink-soft">
        {change === null ? detail
          : change === 0 ? `Same as the ${against}`
          : `${change > 0 ? "▲" : "▼"} ${Math.abs(change)} ${change > 0 ? "more" : "fewer"} than the ${against}`}
      </p>
    </div>
  );
}

/** A coloured mark beside the name; the text itself stays in ink. */
export function ResultTag({ code }: { code: string }) {
  const urgent = code === "urgent";
  return (
    <span className={`inline-flex items-center gap-2 whitespace-nowrap ${urgent ? "font-bold text-red" : ""}`}>
      {urgent
        ? <span aria-hidden className="flex h-4 w-4 items-center justify-center rounded bg-red text-[12px] leading-none font-bold text-white">!</span>
        : <span aria-hidden className="h-3 w-3 rounded-sm" style={{ background: colorOf(code) }} />}
      {shortName(code)}
    </span>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="rounded-lg bg-surface px-4 py-6 text-center text-small text-ink-soft">{children}</p>;
}

export const th = "border-b border-divider px-3 py-2 text-left text-[14px] font-bold whitespace-nowrap text-ink-soft";
export const td = "border-b border-divider px-3 py-2.5 text-small";

export function TableScroll({ children }: { children: ReactNode }) {
  return <div className="overflow-x-auto">{children}</div>;
}

export const selectClass = "h-12 rounded-[10px] border-2 border-edge bg-white px-3 text-small text-ink focus:border-blue focus:outline-none";
export const quietButton = "h-10 rounded-lg border border-divider bg-white px-3 text-small font-bold text-blue hover:bg-blue-tint disabled:text-ink-soft";
export const mainButton = "flex h-12 items-center rounded-[10px] bg-blue px-4 text-small font-bold text-white hover:bg-blue-dark";
