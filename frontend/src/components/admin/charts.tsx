"use client";

// The dashboard's two charts, drawn with plain elements: no chart library to download.

import { useState } from "react";

import type { Dashboard } from "@/lib/types";

import { colorOf, dayLabel, shortName } from "./meta";
import { Card, quietButton, TableScroll, td, th } from "./parts";

/** A round number at or above `max`, split into four equal steps. */
function scale(max: number) {
  const raw = Math.max(max, 4) / 4;
  const power = 10 ** Math.floor(Math.log10(raw));
  const step = ([1, 2, 2.5, 5, 10].map((m) => m * power).find((s) => s >= raw && Number.isInteger(s)) ?? Math.ceil(raw));
  return { top: step * 4, ticks: [4, 3, 2, 1, 0].map((i) => i * step) };
}

const PLOT = 240; // px

/** Likely conditions in each day or week, stacked. */
export function TrendChart({ data }: { data: Dashboard }) {
  const [table, setTable] = useState(false);
  const [active, setActive] = useState<number | null>(null);
  const codes = data.conditions.map((c) => c.code);
  const totals = data.trend.map((b) => codes.reduce((sum, code) => sum + b.counts[code], 0));
  const { top, ticks } = scale(Math.max(...totals));
  const daily = data.days <= 7;
  const range = (i: number) => {
    const b = data.trend[i];
    return daily ? dayLabel(b.start) : `${dayLabel(b.start)} to ${dayLabel(b.end)}`;
  };

  return (
    <Card title="Likely conditions over time"
      note={`${daily ? "Each day" : "Each week"}. Urgent and unclear results are counted separately.`}
      action={<button type="button" className={quietButton} aria-pressed={table} onClick={() => setTable((t) => !t)}>{table ? "Show chart" : "Show table"}</button>}>
      <ul className="flex flex-wrap gap-x-5 gap-y-1 text-small">
        {codes.map((code) => (
          <li key={code} className="flex items-center gap-2">
            <span aria-hidden className="h-3 w-3 rounded-sm" style={{ background: colorOf(code) }} />{shortName(code)}
          </li>
        ))}
      </ul>

      {table ? (
        <TableScroll>
          <table className="w-full tabular-nums">
            <thead><tr><th className={th}>{daily ? "Day" : "Week"}</th>{codes.map((c) => <th key={c} className={`${th} text-right`}>{shortName(c)}</th>)}</tr></thead>
            <tbody>
              {data.trend.map((b, i) => (
                <tr key={b.start}><td className={`${td} whitespace-nowrap`}>{range(i)}</td>{codes.map((c) => <td key={c} className={`${td} text-right`}>{b.counts[c]}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </TableScroll>
      ) : (
        <div className="flex gap-3">
          <div aria-hidden className="flex flex-col justify-between text-right text-[14px] leading-none text-ink-soft tabular-nums" style={{ height: PLOT }}>
            {ticks.map((t) => <span key={t} className="h-0 -translate-y-1.5">{t}</span>)}
          </div>
          <div className="min-w-0 flex-1">
            <div className="relative" style={{ height: PLOT }}>
              {ticks.map((t) => <div key={t} aria-hidden className="absolute inset-x-0 border-t border-divider" style={{ top: PLOT - (t / top) * PLOT }} />)}
              <div className="absolute inset-0 flex items-stretch">
                {data.trend.map((b, i) => (
                  <button key={b.start} type="button" onMouseEnter={() => setActive(i)} onMouseLeave={() => setActive(null)}
                    onFocus={() => setActive(i)} onBlur={() => setActive(null)}
                    aria-label={`${range(i)}: ${codes.map((c) => `${shortName(c)} ${b.counts[c]}`).join(", ")}`}
                    className={`relative flex min-w-0 flex-1 flex-col items-center justify-end rounded-sm ${active === i ? "bg-surface" : ""}`}>
                    <span className="flex w-full max-w-6 flex-col-reverse gap-0.5 overflow-hidden rounded-t">
                      {codes.filter((c) => b.counts[c] > 0).map((c) => (
                        <span key={c} className="block w-full" style={{ height: Math.max(2, (b.counts[c] / top) * PLOT - 2), background: colorOf(c) }} />
                      ))}
                    </span>
                  </button>
                ))}
              </div>
              {active !== null && (
                <div role="tooltip" className="pointer-events-none absolute top-0 z-10 w-52 rounded-lg border border-divider bg-white p-3 text-small shadow-lg"
                  style={active < data.trend.length / 2
                    ? { left: `${((active + 1) / data.trend.length) * 100}%` }
                    : { right: `${((data.trend.length - active) / data.trend.length) * 100}%` }}>
                  <p className="mb-1 font-bold">{range(active)}</p>
                  {codes.map((c) => (
                    <p key={c} className="flex items-center gap-2">
                      <span aria-hidden className="h-2.5 w-2.5 rounded-sm" style={{ background: colorOf(c) }} />
                      <span className="flex-1">{shortName(c)}</span><b className="tabular-nums">{data.trend[active].counts[c]}</b>
                    </p>
                  ))}
                </div>
              )}
            </div>
            <div aria-hidden className="mt-2 flex text-[14px] text-ink-soft">
              {data.trend.map((b, i) => (
                // Every other label when there are many, so they never run into each other.
                <span key={b.start} className="min-w-0 flex-1 text-center whitespace-nowrap">
                  {data.trend.length <= 7 || (data.trend.length - 1 - i) % 2 === 0 ? dayLabel(b.start) : ""}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}

/** One horizontal bar per condition, with the number at its end and the earlier figure beside it. */
export function ConditionBars({ codes, counts, previous }: {
  codes: string[]; counts: Record<string, number>; previous: Record<string, number>;
}) {
  const max = Math.max(1, ...codes.map((c) => counts[c]));
  const ordered = [...codes].sort((a, b) => counts[b] - counts[a]);
  return (
    <ul className="flex flex-col gap-3">
      {ordered.map((code) => (
        <li key={code} className="grid grid-cols-[7.5rem_minmax(0,1fr)_4.5rem] items-center gap-3 text-small">
          <span>{shortName(code)}</span>
          <span className="flex items-center gap-2">
            <span aria-hidden className="h-4 flex-none rounded-r" style={{ width: `calc((100% - 3rem) * ${counts[code] / max})`, background: colorOf(code) }} />
            <b className="tabular-nums">{counts[code]}</b>
          </span>
          <span className="text-right text-[14px] text-ink-soft tabular-nums">was {previous[code]}</span>
        </li>
      ))}
    </ul>
  );
}
