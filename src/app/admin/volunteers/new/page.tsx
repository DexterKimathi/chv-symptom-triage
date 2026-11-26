"use client";

import { useState, type FormEvent } from "react";

import { useDashboard } from "@/components/admin/data";
import { Card } from "@/components/admin/parts";
import { PageHeader } from "@/components/admin/shell";
import { BackLink, Button, ButtonLink, ErrorNotice, Field, inputClass, OfflineBanner, PasswordInput } from "@/components/ui";
import { api, ApiError, NetworkError } from "@/lib/api";
import { useAuth, useSessionGuard } from "@/lib/auth";
import { normalisePhone, phoneLabel } from "@/lib/format";
import type { User } from "@/lib/types";

const EMPTY = { name: "", phone: "", password: "", area: "" };
type Errors = Partial<Record<keyof typeof EMPTY | "form", string>>;

// bcrypt on the backend uses at most 72 bytes; letters such as é take two.
const tooLongForBackend = (password: string) => new TextEncoder().encode(password).length > 72;

const FIELDS = ["name", "phone", "password", "area"] as const;

export default function AddVolunteerPage() {
  const { session } = useAuth();
  const guard = useSessionGuard();
  const { data, refresh } = useDashboard();
  // Areas already in use, offered while typing so one place is not spelled two ways.
  const knownAreas = data?.areas.filter((a) => a.volunteers > 0 && a.area !== "Area not set").map((a) => a.area) ?? [];
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
    else if (form.name.trim().length > 120) out.name = "Use at most 120 characters.";
    if (!normalisePhone(form.phone)) out.phone = "Enter a Kenyan mobile number, such as 0712 345 678 or +254 712 345 678.";
    if (form.password.length < 8) out.password = "Use at least 8 characters.";
    else if (tooLongForBackend(form.password)) out.password = "Too long. Use at most 72 characters (letters like é count as two).";
    if (form.area.trim().length > 120) out.area = "Use at most 120 characters.";
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
        name: form.name.trim(), phone: normalisePhone(form.phone) ?? form.phone, password: form.password,
        area: form.area.trim() || undefined, role: "chv",
      });
      setCreated(user);
      refresh();
    } catch (e) {
      if (guard(e)) return;
      if (e instanceof NetworkError) setOffline(true);
      else if (e instanceof ApiError && e.status === 409) setErrors({ phone: "This phone number is already registered." });
      else if (e instanceof ApiError && e.status === 422 && FIELDS.some((f) => e.fields[f])) {
        // Show each backend message under its own field.
        setErrors(Object.fromEntries(FIELDS.filter((f) => e.fields[f]).map((f) => [f, e.fields[f]])));
      }
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

  const header = <PageHeader title={created ? "Volunteer added" : "Add volunteer"}
    actions={<BackLink href="/admin/volunteers" label="Volunteers" />} />;

  if (created) {
    return (
      <>
        {header}
        <Card className="max-w-xl">
          <div role="status" className="flex items-center gap-3 rounded-xl border-2 border-green bg-green-tint p-4">
            <span aria-hidden className="flex h-10 w-10 items-center justify-center rounded-full bg-green text-heading font-bold text-white">✓</span>
            <p className="text-title font-bold">{created.name} can now log in</p>
          </div>
          <dl className="text-body">
            {[["Name", created.name], ["Phone", phoneLabel(created.phone)], ["Area", created.area ?? "Not set"]].map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-divider py-3">
                <dt className="text-ink-soft">{k}</dt>
                <dd className={`font-bold ${k === "Phone" ? "font-mono" : ""}`}>{v}</dd>
              </div>
            ))}
          </dl>
          <p className="text-body text-ink-soft">They log in with this phone number and the password you set.</p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button onClick={addAnother}>Add another volunteer</Button>
            <ButtonLink href="/admin/volunteers" variant="secondary">Done</ButtonLink>
          </div>
        </Card>
      </>
    );
  }

  return (
    <>
      {header}
      <Card className="max-w-xl">
        <form onSubmit={submit} noValidate className="flex flex-col gap-5">
          {offline && <OfflineBanner />}
          {errors.form && <ErrorNotice>{errors.form}</ErrorNotice>}
          <Field label="Full name" error={errors.name}>
            <input className={inputClass(!!errors.name)} value={form.name} onChange={set("name")} autoComplete="off" />
          </Field>
          <Field label="Phone number" error={errors.phone} help="They log in with this number.">
            <input className={inputClass(!!errors.phone, true)} type="tel" inputMode="tel" placeholder="07XX XXX XXX"
              value={form.phone} onChange={set("phone")} autoComplete="off" />
          </Field>
          <Field label="Password" error={errors.password} help="8 to 72 characters. Share it with them in person.">
            <PasswordInput value={form.password} onChange={(v) => setForm((f) => ({ ...f, password: v }))}
              show={showPassword} onToggle={() => setShowPassword((s) => !s)} invalid={!!errors.password} autoComplete="new-password" />
          </Field>
          <Field label="Area" error={errors.area} help="Where they work. The dashboard groups results by this.">
            <input className={inputClass(!!errors.area)} value={form.area} onChange={set("area")} placeholder="e.g. Kilifi" list="known-areas" />
          </Field>
          <datalist id="known-areas">{knownAreas.map((a) => <option key={a} value={a} />)}</datalist>
          <Button type="submit" loading={busy}>{busy ? "Creating…" : "Create volunteer"}</Button>
        </form>
      </Card>
    </>
  );
}
