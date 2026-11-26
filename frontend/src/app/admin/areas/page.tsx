"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ConditionBars } from "@/components/admin/charts";
import { periodMeta, rememberFilters, share, shortName } from "@/components/admin/meta";
import { Card, Empty, mainButton, quietButton, TableScroll, td, th } from "@/components/admin/parts";
import { DashboardPage } from "@/components/admin/shell";
import type { AreaFigures, Dashboard } from "@/lib/types";

/** One blue, light to dark, for how large a figure is next to the others. Dark cells take white text. */
const SHADES = ["#e8f1fc", "#cde2fb", "#9ec5f4", "#6da7ec", "#256abf", "#184f95"];
function shade(fraction: number) {
  if (fraction <= 0) return undefined;
  const i = Math.min(SHADES.length - 1, Math.floor(fraction * SHADES.length));
  return { background: SHADES[i], color: i >= 4 ? "#ffffff" : undefined };
}

function AreaTable({ data, selected, onSelect }: { data: Dashboard; selected: string; onSelect: (area: string) => void }) {
  const [asShare, setAsShare] = useState(false);
  const codes = data.conditions.map((c) => c.code);
  const measure = (a: AreaFigures, code: string) => (asShare ? (a.assessments ? a.counts[code] / a.assessments : 0) : a.counts[code]);
  const max = Math.max(...data.areas.flatMap((a) => codes.map((c) => measure(a, c))), asShare ? 0.01 : 1);
  const flagged = new Set(data.alerts.map((x) => `${x.area}|${x.code}`));

  return (
    <Card title="Where each result is coming from"
      note={asShare ? "Each condition as a share of that area's assessments. Darker means higher." : "Number of assessments. Darker means more. Choose an area to see its detail."}
      action={
        <div role="group" aria-label="Show as" className="flex gap-2">
          <button type="button" aria-pressed={!asShare} onClick={() => setAsShare(false)} className={`${quietButton} ${!asShare ? "!bg-blue !text-white" : ""}`}>Counts</button>
          <button type="button" aria-pressed={asShare} onClick={() => setAsShare(true)} className={`${quietButton} ${asShare ? "!bg-blue !text-white" : ""}`}>Share of area</button>
        </div>
      }>
      <TableScroll>
        <table className="w-full tabular-nums">
          <thead>
            <tr>
              <th className={th}>Area</th>
              <th className={`${th} text-right`}>Volunteers</th>
              <th className={`${th} text-right`}>Assessments</th>
              {codes.map((c) => <th key={c} className={`${th} text-center`}>{shortName(c)}</th>)}
              <th className={`${th} text-center`}>Urgent</th>
              <th className={`${th} text-center`}>Unclear</th>
            </tr>
          </thead>
          <tbody>
            {data.areas.map((a) => {
              const value = (code: string) => (asShare ? share(a.counts[code], a.assessments) : a.counts[code]);
              return (
                <tr key={a.area} className={a.area === selected ? "bg-blue-tint" : ""}>
                  <th scope="row" className={`${td} text-left`}>
                    <button type="button" aria-pressed={a.area === selected} onClick={() => onSelect(a.area)} className="font-bold whitespace-nowrap text-blue underline">{a.area}</button>
                  </th>
                  <td className={`${td} text-right`}>{a.volunteers}</td>
                  <td className={`${td} text-right`}>{a.assessments}</td>
                  {codes.map((c) => (
                    <td key={c} className="border-b border-white p-0.5 text-center text-small">
                      <span className="flex h-10 min-w-16 items-center justify-center gap-1 rounded" style={shade(measure(a, c) / max)}>
                        {value(c)}
                        {flagged.has(`${a.area}|${c}`) && <span title="Meets the rise rule"><span aria-hidden>▲</span><span className="sr-only">rising</span></span>}
                      </span>
                    </td>
                  ))}
                  <td className={`${td} text-center ${a.counts.urgent ? "font-bold text-red" : ""}`}>
                    {value("urgent")}{flagged.has(`${a.area}|urgent`) && <> <span aria-hidden>▲</span><span className="sr-only">rising</span></>}
                  </td>
                  <td className={`${td} text-center`}>{value("unclear")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </TableScroll>
      <p className="text-[14px] text-ink-soft">▲ at least {data.alert_rule.min_cases} cases and {data.alert_rule.factor} times the {periodMeta(data.days).previous}.</p>
    </Card>
  );
}

function AreaDetail({ data, area }: { data: Dashboard; area: AreaFigures }) {
  const router = useRouter();
  const codes = data.conditions.map((c) => c.code);
  const people = data.volunteers.filter((v) => v.area.toLowerCase() === area.area.toLowerCase());
  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      <Card title={`${area.area}: likely conditions`}
        note={`${area.assessments} assessments, ${area.previous_assessments} in the ${periodMeta(data.days).previous}.`}
        action={<button type="button" className={mainButton}
          onClick={() => { rememberFilters({ area: area.area }); router.push("/admin/assessments"); }}>View assessments</button>}>
        <ConditionBars codes={codes} counts={area.counts} previous={area.previous_counts} />
      </Card>
      <Card title={`Volunteers in ${area.area}`}>
        {people.length === 0 ? <Empty>No volunteer account has this area.</Empty> : (
          <TableScroll>
            <table className="w-full">
              <thead><tr><th className={th}>Name</th><th className={`${th} text-right`}>Assessments</th><th className={`${th} text-right`}>Urgent</th></tr></thead>
              <tbody>
                {people.map((v) => (
                  <tr key={v.id}><td className={td}>{v.name}</td><td className={`${td} text-right`}>{v.assessments}</td><td className={`${td} text-right`}>{v.urgent}</td></tr>
                ))}
              </tbody>
            </table>
          </TableScroll>
        )}
      </Card>
    </div>
  );
}

export default function AreasPage() {
  const [chosen, setChosen] = useState("");
  return (
    <DashboardPage title="Areas">
      {(data) => {
        if (data.areas.length === 0) return <Empty>No areas yet. Add a volunteer with an area to see it here.</Empty>;
        // The busiest area until one is chosen.
        const area = data.areas.find((a) => a.area === chosen) ?? data.areas[0];
        return (
          <>
            <AreaTable data={data} selected={area.area} onSelect={setChosen} />
            <AreaDetail data={data} area={area} />
          </>
        );
      }}
    </DashboardPage>
  );
}
