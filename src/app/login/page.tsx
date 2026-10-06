"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Button, ErrorNotice, Field, inputClass, PasswordInput, PlusIcon } from "@/components/ui";
import { ApiError, NetworkError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { login, session, ready } = useAuth();
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<"wrong" | "offline" | string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (ready && session) router.replace("/");
  }, [ready, session, router]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(phone.replace(/\s/g, ""), password);
      router.replace("/");
    } catch (e) {
      if (e instanceof NetworkError) setError("offline");
      else if (e instanceof ApiError && (e.status === 401 || e.status === 422)) setError("wrong");
      else setError(e instanceof Error ? e.message : "Could not log in.");
      setBusy(false);
    }
  }

  return (
    <main className="flex flex-1 flex-col gap-6 px-4 pt-10 pb-8">
      <div className="flex flex-col gap-3">
        <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-blue"><PlusIcon size={28} /></span>
        <h1 className="text-headline font-bold">CHV Triage</h1>
        {!error && <p className="text-small text-ink-soft">Symptom checklist and referral support for community health volunteers.</p>}
      </div>

      {error && (
        <ErrorNotice>
          {error === "wrong" ? <><b>Phone number or password is not correct.</b> Check both and try again.</>
            : error === "offline" ? <><b>No internet connection, please try again.</b> Move to a spot with better signal.</>
            : error}
        </ErrorNotice>
      )}

      <form onSubmit={submit} className="flex flex-col gap-5">
        <Field label="Phone number">
          <input className={inputClass(false, true)} type="tel" inputMode="tel" autoComplete="username"
            placeholder="07XX XXX XXX" value={phone} onChange={(e) => setPhone(e.target.value)} required />
        </Field>
        <Field label="Password">
          <PasswordInput value={password} onChange={setPassword} show={showPassword}
            onToggle={() => setShowPassword((s) => !s)} autoComplete="current-password" />
        </Field>
        <Button type="submit" loading={busy}>{busy ? "Logging in…" : "Log in"}</Button>
      </form>

      <p className="text-small text-ink-soft">
        {busy ? "On slow data this can take up to a minute." : "Forgot your password? Ask your supervisor to reset it."}
      </p>
    </main>
  );
}
