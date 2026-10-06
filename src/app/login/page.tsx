"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Button, ErrorMessage, Field, inputClass, Screen } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { login, session, ready } = useAuth();
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (ready && session) router.replace("/");
  }, [ready, session, router]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(phone.trim(), password);
      router.replace("/");
    } catch (e) {
      setError(e instanceof ApiError || e instanceof Error ? e.message : "Could not log in.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen>
      <div className="mt-8 flex flex-col gap-1">
        <h1 className="text-3xl font-bold">CHV Symptom Triage</h1>
        <p className="text-lg text-slate-600">Log in to start an assessment.</p>
      </div>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Field label="Phone number">
          <input className={inputClass} type="tel" inputMode="tel" autoComplete="username"
            value={phone} onChange={(e) => setPhone(e.target.value)} required />
        </Field>
        <Field label="Password">
          <input className={inputClass} type="password" autoComplete="current-password"
            value={password} onChange={(e) => setPassword(e.target.value)} required />
        </Field>
        <ErrorMessage message={error} />
        <Button type="submit" disabled={busy}>{busy ? "Logging in…" : "Log in"}</Button>
      </form>
    </Screen>
  );
}
