"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Button, ErrorNotice, Field, inputClass, PasswordInput } from "@/components/ui";
import { ApiError, connectionMessage, NetworkError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { normalisePhone } from "@/lib/format";

import visit from "./visit.webp";

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
      // Accounts are stored as 07…, so +254 7… logs in too, whichever backend version runs.
      await login(normalisePhone(phone) ?? phone.replace(/\s/g, ""), password);
      router.replace("/");
    } catch (e) {
      if (e instanceof NetworkError) setError("offline");
      else if (e instanceof ApiError && (e.status === 401 || e.status === 422)) setError("wrong");
      else setError(e instanceof Error ? e.message : "Could not log in.");
      setBusy(false);
    }
  }

  return (
    // Phone: the form alone. Tablet: the form on a card. Wide landscape screens: the form
    // beside the illustration.
    <div className="flex flex-1 flex-col md:items-center md:justify-center md:bg-canvas md:p-8 wide:grid wide:min-h-dvh wide:grid-cols-[minmax(0,1fr)_auto] wide:items-stretch wide:bg-white wide:p-0">
      <div className="flex flex-1 flex-col md:w-full md:max-w-md md:flex-none wide:max-w-none wide:items-center wide:justify-center wide:p-10">
      <main className="flex flex-1 flex-col gap-6 px-4 pt-10 pb-8 md:w-full md:max-w-md md:flex-none md:rounded-2xl md:bg-white md:p-10 md:shadow-[0_8px_24px_rgba(15,23,32,.10)] wide:rounded-none wide:p-0 wide:shadow-none wide:motion-safe:animate-rise">
        <div className="flex flex-col gap-3">
          <span aria-hidden className="flex h-11 w-11 items-center justify-center rounded-lg bg-blue text-[32px] leading-none font-bold text-white">+</span>
          <h1 className="text-headline font-bold">CHV Triage</h1>
          {!error && <p className="text-small text-ink-soft">Symptom checklist and referral support for community health volunteers.</p>}
        </div>

        {error && (
          <ErrorNotice>
            {error === "wrong" ? <><b>Phone number or password is not correct.</b> Check both and try again.</>
              : error === "offline" ? <><b>{connectionMessage()}</b> Move to a spot with better signal.</>
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
      </div>

      {/* Wide landscape screens only; elsewhere the panel is not displayed, so the lazily
          loaded image is never downloaded. The panel is the full screen height and the
          illustration's own shape (3:4), so the drawing is never cropped whatever the
          screen; the caption sits in its open sky. */}
      <aside aria-hidden className="relative hidden h-dvh aspect-[1086/1448] max-w-[55vw] overflow-hidden bg-[#e1f7fd] wide:sticky wide:top-0 wide:block motion-safe:animate-panel-in">
        <Image src={visit} alt="" fill placeholder="blur" sizes="(orientation: landscape) 50vw, 1px"
          className="object-cover object-bottom motion-safe:animate-drift" />
        <div className="absolute inset-x-0 top-0 px-10 pt-10">
          <p className="text-title font-bold text-blue-dark">Every visit, a clearer next step.</p>
          <p className="mt-2 text-body text-ink-soft">Checks danger signs first, asks only the questions that matter, and refers whenever it is unsure.</p>
        </div>
      </aside>
    </div>
  );
}
