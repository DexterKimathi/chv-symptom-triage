// Small shared building blocks. Styling is deliberately plain until the final design
// is applied: high contrast, large text, tap targets of at least 48px.

import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";

export function Screen({ title, back, children }: { title?: string; back?: string; children: ReactNode }) {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-5 px-4 py-6">
      {(title || back) && (
        <header className="flex items-center gap-3">
          {back && (
            <Link href={back} className="flex h-12 w-12 items-center justify-center rounded-lg border-2 border-slate-300 text-xl" aria-label="Back">
              ←
            </Link>
          )}
          {title && <h1 className="text-2xl font-bold text-slate-900">{title}</h1>}
        </header>
      )}
      {children}
    </main>
  );
}

type Variant = "primary" | "secondary" | "danger";
const variants: Record<Variant, string> = {
  primary: "bg-teal-700 text-white hover:bg-teal-800 disabled:bg-slate-400",
  secondary: "border-2 border-slate-300 bg-white text-slate-900 hover:bg-slate-50 disabled:text-slate-400",
  danger: "bg-red-700 text-white hover:bg-red-800",
};

export function Button({ variant = "primary", className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      {...props}
      className={`min-h-12 w-full rounded-xl px-5 py-3 text-lg font-semibold transition-colors ${variants[variant]} ${className}`}
    />
  );
}

export function ErrorMessage({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-lg border-2 border-red-300 bg-red-50 p-3 text-base text-red-900">
      {message}
    </p>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-10 text-lg text-slate-600" role="status">
      <span className="h-6 w-6 animate-spin rounded-full border-4 border-slate-300 border-t-teal-700" />
      {label}
    </div>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-2 text-base font-medium text-slate-800">
      {label}
      {children}
    </label>
  );
}

export const inputClass =
  "min-h-12 rounded-lg border-2 border-slate-300 px-4 text-lg text-slate-900 focus:border-teal-700 focus:outline-none";

export function pct(probability: number) {
  return `${Math.round(probability * 100)}%`;
}
