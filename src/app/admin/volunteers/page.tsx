"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { rememberFilters } from "@/components/admin/meta";
import { Card, Empty, mainButton, TableScroll, td, th } from "@/components/admin/parts";
import { DashboardPage } from "@/components/admin/shell";
import { fullWhen, phoneLabel } from "@/lib/format";

export default function VolunteersPage() {
  const router = useRouter();
  return (
    <DashboardPage title="Volunteers" actions={<Link href="/admin/volunteers/new" className={mainButton}>+ Add volunteer</Link>}>
      {(data) => {
        const max = Math.max(1, ...data.volunteers.map((v) => v.assessments));
        const { totals } = data;
        return (
          <Card note={`${totals.volunteers} volunteers. ${totals.active_volunteers} recorded an assessment in this period.`} title="All volunteers">
            {data.volunteers.length === 0 ? <Empty>No volunteers yet.</Empty> : (
              <TableScroll>
                <table className="w-full">
                  <thead>
                    <tr>
                      <th className={th}>Name</th><th className={th}>Phone</th><th className={th}>Area</th>
                      <th className={th}>Assessments this period</th><th className={`${th} text-right`}>Urgent</th>
                      <th className={`${th} text-right`}>All time</th><th className={th}>Last assessment</th><th className={th}>Account</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.volunteers.map((v) => (
                      <tr key={v.id} className="hover:bg-surface">
                        <td className={td}>
                          <button type="button" className="text-left font-bold text-blue underline"
                            onClick={() => { rememberFilters({ volunteer: String(v.id) }); router.push("/admin/assessments"); }}>{v.name}</button>
                        </td>
                        <td className={`${td} font-mono whitespace-nowrap`}>{phoneLabel(v.phone)}</td>
                        <td className={td}>{v.area}</td>
                        <td className={`${td} w-56`}>
                          <span className="flex items-center gap-2">
                            <span aria-hidden className="h-3 rounded-r bg-blue" style={{ width: `${(v.assessments / max) * 8}rem` }} />
                            <b className="tabular-nums">{v.assessments}</b>
                          </span>
                        </td>
                        <td className={`${td} text-right tabular-nums ${v.urgent ? "font-bold text-red" : ""}`}>{v.urgent}</td>
                        <td className={`${td} text-right tabular-nums`}>{v.total_assessments}</td>
                        <td className={`${td} whitespace-nowrap`}>{v.last_assessment_at ? fullWhen(v.last_assessment_at) : "Never"}</td>
                        <td className={td}>{v.is_active ? "Enabled" : "Disabled"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableScroll>
            )}
          </Card>
        );
      }}
    </DashboardPage>
  );
}
