"use client";

import { useState, type FormEvent } from "react";

import { BackLink, Body, BottomBar, Button, ButtonLink, ErrorNotice, Field, inputClass, OfflineBanner, PasswordInput, TopBar } from "@/components/ui";
import { api, ApiError, NetworkError } from "@/lib/api";
import { RequireAuth, useAuth, useSessionGuard } from "@/lib/auth";
import { phoneLabel } from "@/lib/format";
import type { User } from "@/lib/types";

const EMPTY = { name: "", phone: "", password: "", area: "" };
type Errors = Partial<Record<keyof typeof EMPTY | "form", string>>;

const AdminBadge = <span className="rounded-md bg-ink px-2 py-1 text-small font-bold text-white">Admin</span>;

function Admin() {
  const { session } = useAuth();
  const guard = useSessionGuard();
  const [form, setForm] = useState(EMPTY);
  const [showPassword, setShowPassword] = useState(true);
  const [errors, setErrors] = useState<Errors>({});
  const [offline, setOffline] = useState(false);
  const [created, setCreated] = useState<User | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (key: keyof typeof EMPTY) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [key]: e.target.value }));

  function validate(): Errors {
    const out: Errors = {};
    if (!form.name.trim()) out.name = "Enter their full name.";
    if (form.phone.replace(/\D/g, "").length < 7) out.phone = "Enter a phone number.";
    if (form.password.length < 8) out.password = "Use at least 8 characters.";
    return out;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!session) return;
    const found = validate();
    setErrors(found);
    setOffline(false);
    if (Object.keys(found).length) return;
    setBusy(true);
    try {
      const user = await api.createUser(session.token, {
        name: form.name.trim(), phone: form.phone.replace(/\s/g, ""), password: form.password,
        area: form.area.trim() || undefined, role: "chv",
      });
      setCreated(user);
    } catch (e) {
      if (guard(e)) return;
      if (e instanceof NetworkError) setOffline(true);
      else if (e instanceof ApiError && e.status === 409) setErrors({ phone: "This phone number is already registered." });
      else setErrors({ form: e instanceof Error ? e.message : "Could not add the volunteer." });
    } finally {
      setBusy(false);
    }
  }

  function addAnother() {
    setCreated(null);
    setForm(EMPTY);
    setErrors({});
  }

  if (created) {
    return (
      <>
        <TopBar left={<BackLink href="/" label="Back" />} right={AdminBadge} width="narrow" />
        <Body width="narrow">
          <div role="status" className="flex flex-col gap-3 rounded-xl border-2 border-green bg-green-tint p-4">
            <span aria-hidden className="flex h-10 w-10 items-center justify-center rounded-full bg-green text-heading font-bold text-white">✓</span>
            <p className="text-title font-bold">Volunteer added</p>
          </div>
          <dl className="text-body">
            {[["Name", created.name], ["Phone", phoneLabel(created.phone)], ["Area", created.area ?? "Not set"]].map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-divider py-3">
                <dt className="text-ink-soft">{k}</dt>
                <dd className={`font-bold ${k === "Phone" ? "font-mono" : ""}`}>{v}</dd>
              </div>
            ))}
          </dl>
          <p className="text-body text-ink-soft">They can log in now with this phone number and the password you set.</p>
        </Body>
        <BottomBar width="narrow" className="md:flex-row md:[&>*]:flex-1">
          <Button onClick={addAnother}>Add another volunteer</Button>
          <ButtonLink href="/" variant="secondary">Done</ButtonLink>
        </BottomBar>
      </>
    );
  }

  return (
    <>
      <TopBar left={<BackLink href="/" label="Back" />} right={AdminBadge} width="narrow" />
      <form onSubmit={submit} noValidate className="flex flex-1 flex-col">
        <Body width="narrow">
          <h1 className="text-title font-bold">Add volunteer</h1>
          {offline && <OfflineBanner />}
          {errors.form && <ErrorNotice>{errors.form}</ErrorNotice>}
          <Field label="Full name" error={errors.name}>
            <input className={inputClass(!!errors.name)} value={form.name} onChange={set("name")} autoComplete="off" />
          </Field>
          <Field label="Phone number" error={errors.phone} help="They log in with this number.">
            <input className={inputClass(!!errors.phone, true)} type="tel" inputMode="tel" placeholder="07XX XXX XXX"
              value={form.phone} onChange={set("phone")} autoComplete="off" />
          </Field>
          <Field label="Password" error={errors.password} help="At least 8 characters. Share it with them in person.">
            <PasswordInput value={form.password} onChange={(v) => setForm((f) => ({ ...f, password: v }))}
              show={showPassword} onToggle={() => setShowPassword((s) => !s)} invalid={!!errors.password} autoComplete="new-password" />
          </Field>
          <Field label="Area">
            <input className={inputClass()} value={form.area} onChange={set("area")} placeholder="e.g. Kilifi North" />
          </Field>
        </Body>
        <BottomBar width="narrow"><Button type="submit" loading={busy}>{busy ? "Creating…" : "Create volunteer"}</Button></BottomBar>
      </form>
    </>
  );
}

export default function AdminPage() {
  return <RequireAuth adminOnly><Admin /></RequireAuth>;
}
