"use client";

import { DashboardProvider } from "@/components/admin/data";
import { AdminShell } from "@/components/admin/shell";
import { RequireAuth } from "@/lib/auth";

export default function AdminLayout({ children }: LayoutProps<"/admin">) {
  return (
    <RequireAuth adminOnly>
      <DashboardProvider>
        <AdminShell>{children}</AdminShell>
      </DashboardProvider>
    </RequireAuth>
  );
}
