"use client";

import Link from "next/link";
import { useState } from "react";

import { downloadCsv, NO_FILTERS, readFilters, rememberFilters, shortName, type RecordFilters } from "@/components/admin/meta";
import { Card, Empty, mainButton, quietButton, ResultTag, selectClass, TableScroll, td, th } from "@/components/admin/parts";
import { DashboardPage } from "@/components/admin/shell";
import { ageLabel, fullWhen, percent, sexLabel } from "@/lib/format";
import type { Dashboard } from "@/lib/types";

const PAGE = 25;

function Records({ data }: { data: Dashboard }) {
  const [filters, setFilters] = useState<RecordFilters>(readFilters);
  const [page, setPage] = useState(0);

  const change = (key: keyof RecordFilters) => (e: { target: { value: string } }) => {
    const next = { ...filters, [key]: e.target.value };
    rememberFilters(next);
    setFilters(next);
    setPage(0);
  };

  const search = filters.search.trim().toLowerCase();
  const matches = data.assessments.filter((r) =>
    (!search || r.patient_ref.toLowerCase().includes(search) || r.volunteer.toLowerCase().includes(search))
    && (!filters.area || r.area.toLowerCase() === filters.area.toLowerCase())
    && (!filters.volunteer || String(r.volunteer_id) === filters.volunteer)
    && (!filters.result || r.category === filters.result));
  const pages = Math.max(1, Math.ceil(matches.length / PAGE));
  const current = Math.min(page, pages - 1);
  const filtered = Object.values(filters).some(Boolean);
  // Everyone who recorded something in this period, which can include an administrator.
  const people = [...new Map(data.assessments.map((r) => [r.volunteer_id, r.volunteer]))].sort((a, b) => a[1].localeCompare(b[1]));
  const areas = data.areas.map((a) => a.area).sort((a, b) => a.localeCompare(b));

  return (
    <Card>
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-small font-bold">Search
          <input className={`${selectClass} w-56 font-normal`} value={filters.search} onChange={change("search")} placeholder="Patient code or volunteer" />
        </label>
        <label className="flex flex-col gap-1 text-small font-bold">Area
          <select className={`${selectClass} font-normal`} value={filters.area} onChange={change("area")}>
            <option value="">All areas</option>
            {areas.map((a) => <option key={a}>{a}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-small font-bold">Volunteer
          <select className={`${selectClass} max-w-56 font-normal`} value={filters.volunteer} onChange={change("volunteer")}>
            <option value="">All volunteers</option>
            {people.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-small font-bold">Result
          <select className={`${selectClass} font-normal`} value={filters.result} onChange={change("result")}>
            <option value="">All results</option>
            {[...data.conditions.map((c) => c.code), "urgent", "unclear"].map((c) => <option key={c} value={c}>{shortName(c)}</option>)}
          </select>
        </label>
        {filtered && <button type="button" className={`${quietButton} !h-12`} onClick={() => { rememberFilters({}); setFilters(NO_FILTERS); setPage(0); }}>Clear</button>}
        <button type="button" className={`${mainButton} ml-auto disabled:bg-track disabled:text-ink-soft`} disabled={matches.length === 0}
          onClick={() => downloadCsv(matches, `assessments_${data.start}_to_${data.end}.csv`)}>Download CSV</button>
      </div>

      <p role="status" className="text-small text-ink-soft">{matches.length} {matches.length === 1 ? "assessment" : "assessments"}{filtered && ` of ${data.assessments.length}`}</p>

      {matches.length === 0 ? <Empty>Nothing matches. Clear a filter or choose a longer period.</Empty> : (
        <TableScroll>
          <table className="w-full">
            <thead>
              <tr>
                {["When", "Patient code", "Patient", "Volunteer", "Area", "Result"].map((h) => <th key={h} className={th}>{h}</th>)}
                <th className={`${th} text-right`}>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {matches.slice(current * PAGE, (current + 1) * PAGE).map((r) => (
                <tr key={r.id} className="hover:bg-surface">
                  <td className={`${td} whitespace-nowrap`}><Link href={`/history/${r.id}`} className="font-bold text-blue underline">{fullWhen(r.created_at)}</Link></td>
                  <td className={`${td} font-mono whitespace-nowrap`}>{r.patient_ref}</td>
                  <td className={`${td} whitespace-nowrap`}>{ageLabel(r.age_band)}, {sexLabel(r.sex).toLowerCase()}</td>
                  <td className={td}>{r.volunteer}</td>
                  <td className={td}>{r.area}</td>
                  <td className={td}><ResultTag code={r.category} /></td>
                  {/* The app names a condition, and so a confidence, only for a likely result. */}
                  <td className={`${td} text-right tabular-nums`}>{r.category === "urgent" || r.category === "unclear" ? "–" : percent(r.top_confidence)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableScroll>
      )}

      {pages > 1 && (
        <div className="flex items-center justify-end gap-3 text-small">
          <button type="button" className={quietButton} disabled={current === 0} onClick={() => setPage(current - 1)}>Previous</button>
          <span>Page {current + 1} of {pages}</span>
          <button type="button" className={quietButton} disabled={current === pages - 1} onClick={() => setPage(current + 1)}>Next</button>
        </div>
      )}
    </Card>
  );
}

export default function AssessmentsPage() {
  return <DashboardPage title="Assessments">{(data) => <Records data={data} />}</DashboardPage>;
}
