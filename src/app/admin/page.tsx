"use client";

import { useState, type FormEvent } from "react";

import { Button, ErrorMessage, Field, inputClass, Screen } from "@/components/ui";
import { api } from "@/lib/api";
import { RequireAuth, useAuth, useSessionGuard } from "@/lib/auth";
import type { Role, User } from "@/lib/types";

const EMPTY = { name: "", phone: "", password: "", area: "" };

function Admin() {
  const { session } = useAuth();
  const guard = useSessionGuard();
  const [form, setForm] = useState(EMPTY);
  const [role, setRole] = useState<Role>("chv");
  const [created, setCreated] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (key: keyof typeof EMPTY) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!session) return;
    setBusy(true);
    setError(null);
    setCreated(null);
    try {
      const user = await api.createUser(session.token, {
        name: form.name.trim(), phone: form.phone.trim(), password: form.password,
        area: form.area.trim() || undefined, role,
      });
      setCreated(user);
      setForm(EMPTY);
      setRole("chv");
    } catch (e) {
      if (!guard(e)) setError(e instanceof Error ? e.message : "Could not create the account.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen title="New account" back="/">
      {created && (
        <p role="status" className="rounded-lg border-2 border-teal-700 bg-teal-50 p-4 text-base">
          Created <span className="font-semibold">{created.name}</span> ({created.phone}). They can log in now.
        </p>
      )}
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Field label="Full name">
          <input className={inputClass} value={form.name} onChange={set("name")} required autoComplete="off" />
        </Field>
        <Field label="Phone number">
          <input className={inputClass} type="tel" inputMode="tel" value={form.phone} onChange={set("phone")} required autoComplete="off" />
        </Field>
        <Field label="Temporary password">
          <input className={inputClass} type="text" value={form.password} onChange={set("password")} required minLength={8} autoComplete="new-password" />
        </Field>
        <Field label="Area (optional)">
          <input className={inputClass} value={form.area} onChange={set("area")} placeholder="e.g. Kisumu West" />
        </Field>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-base font-medium text-slate-800">Role</legend>
          <div className="grid grid-cols-2 gap-2">
            {(["chv", "admin"] as const).map((r) => (
              <button key={r} type="button" aria-pressed={role === r} onClick={() => setRole(r)}
                className={`min-h-12 rounded-lg border-2 text-base font-semibold ${role === r ? "border-teal-700 bg-teal-700 text-white" : "border-slate-300 bg-white"}`}>
                {r === "chv" ? "Volunteer" : "Admin"}
              </button>
            ))}
          </div>
        </fieldset>
        <ErrorMessage message={error} />
        <Button type="submit" disabled={busy}>{busy ? "Creating…" : "Create account"}</Button>
      </form>
    </Screen>
  );
}

export default function AdminPage() {
  return <RequireAuth adminOnly><Admin /></RequireAuth>;
}
