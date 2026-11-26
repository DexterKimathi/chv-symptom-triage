"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { ConditionBars, TrendChart } from "@/components/admin/charts";
import { periodMeta, rememberFilters, shortName } from "@/components/admin/meta";
import { Card, Empty, ResultTag, StatTile, TableScroll, td, th } from "@/components/admin/parts";
import { DashboardPage } from "@/components/admin/shell";
import { fullWhen } from "@/lib/format";

const RECENT = 8;

export default function OverviewPage() {
  const router = useRouter();
  return (
    <DashboardPage title="Overview">
      {(data) => {
        const against = periodMeta(data.days).previous;
        const codes = data.conditions.map((c) => c.code);
        const { totals, counts, previous_counts: before } = data;
        return (
          <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <StatTile label="Assessments" value={totals.assessments} previous={totals.previous_assessments} against={against} />
              <StatTile label="Urgent referrals" value={counts.urgent} previous={before.urgent} against={against} urgent />
              <StatTile label="Unclear results" value={counts.unclear} previous={before.unclear} against={against} />
              <StatTile label="Volunteers active" value={`${totals.active_volunteers} of ${totals.volunteers}`}
                detail={`Across ${totals.areas} ${totals.areas === 1 ? "area" : "areas"} with assessments`} />
            </div>

            <div className="grid gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
              <TrendChart data={data} />
              <Card title="Areas to watch"
                note={`At least ${data.alert_rule.min_cases} cases and ${data.alert_rule.factor} times the ${against}.`}>
                {data.alerts.length === 0 ? <Empty>No area meets the rule in this period.</Empty> : (
                  <ul className="flex flex-col gap-2">
                    {data.alerts.map((a) => (
                      <li key={`${a.area}-${a.code}`}>
                        <button type="button"
                          onClick={() => { rememberFilters({ area: a.area, result: a.code }); router.push("/admin/assessments"); }}
                          className="flex w-full items-center gap-3 rounded-lg border-2 border-amber bg-amber-tint px-3 py-2.5 text-left text-small hover:bg-white">
                          <span aria-hidden className="text-heading font-bold">▲</span>
                          <span className="flex-1">
                            <b className="block">{a.area}: {shortName(a.code)}</b>
                            {a.count} now, {a.previous} before
                          </span>
                          <span aria-hidden className="text-heading text-ink-soft">›</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="text-[14px] text-ink-soft">A prompt to look closer, not proof of an outbreak. Small numbers can rise by chance.</p>
              </Card>
            </div>

            <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
              <Card title="Likely conditions" note={`This period, with the ${against} beside it.`}>
                <ConditionBars codes={codes} counts={counts} previous={before} />
              </Card>
              <Card title="Latest assessments"
                action={<Link href="/admin/assessments" onClick={() => rememberFilters({})} className="text-small font-bold text-blue">See all</Link>}>
                {data.assessments.length === 0 ? <Empty>No assessments in this period.</Empty> : (
                  <TableScroll>
                    <table className="w-full">
                      <thead><tr><th className={th}>When</th><th className={th}>Volunteer</th><th className={th}>Area</th><th className={th}>Result</th></tr></thead>
                      <tbody>
                        {data.assessments.slice(0, RECENT).map((r) => (
                          <tr key={r.id} className="hover:bg-surface">
                            <td className={`${td} whitespace-nowrap`}>
                              <Link href={`/history/${r.id}`} className="font-bold text-blue">{fullWhen(r.created_at)}</Link>
                            </td>
                            <td className={td}>{r.volunteer}</td>
                            <td className={td}>{r.area}</td>
                            <td className={td}><ResultTag code={r.category} /></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </TableScroll>
                )}
              </Card>
            </div>
          </>
        );
      }}
    </DashboardPage>
  );
}
