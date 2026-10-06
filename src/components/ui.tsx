// Building blocks from the CHV Triage design system: 56px actions, 48px minimum tap
// targets, 16px minimum text. Colour never carries meaning alone; every state also has a
// word or a symbol.

import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";

/* ---------- page frame ---------- */

export function TopBar({ left, right }: { left: ReactNode; right?: ReactNode }) {
  return (
    <header className="flex h-14 flex-none items-center justify-between border-b border-divider pr-4 pl-1">
      {left}
      {right}
    </header>
  );
}

export function TopTitle({ children }: { children: ReactNode }) {
  return <h1 className="px-3 text-label font-bold">{children}</h1>;
}

export function BackLink({ href, label, onClick }: { href?: string; label: string; onClick?: () => void }) {
  const className = "flex h-12 items-center rounded-lg px-3 text-label font-bold text-blue hover:text-blue-dark";
  if (href) return <Link href={href} className={className} onClick={onClick}>← {label}</Link>;
  return <button type="button" className={className} onClick={onClick}>← {label}</button>;
}

export function Code({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <span className={`font-mono text-label font-bold ${className}`}>{children}</span>;
}

export function Body({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`flex flex-1 flex-col gap-5 px-4 py-5 ${className}`}>{children}</div>;
}

/** Actions pinned to the bottom of the screen, above the phone's own buttons. */
export function BottomBar({ children }: { children: ReactNode }) {
  return (
    <div className="sticky bottom-0 flex flex-none flex-col gap-2 border-t border-divider bg-white px-4 pt-2.5 pb-4">
      {children}
    </div>
  );
}

/* ---------- actions ---------- */

type Variant = "primary" | "secondary";

const base = "flex h-14 w-full items-center justify-center gap-3 rounded-[10px] px-4 text-heading font-bold transition-colors";
const variants: Record<Variant, string> = {
  primary: "bg-blue text-white hover:bg-blue-dark active:bg-blue-dark disabled:bg-track disabled:text-ink-soft",
  secondary: "border-2 border-ink bg-white text-ink hover:bg-surface",
};

export function Button({ variant = "primary", loading = false, className = "", children, disabled, ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  return (
    <button {...props} disabled={disabled || loading}
      className={`${base} ${variants[variant]} ${loading ? "!bg-blue-dark !text-white" : ""} ${className}`}>
      {loading && <Spinner light />}
      {children}
    </button>
  );
}

export function ButtonLink({ href, variant = "primary", children }: { href: string; variant?: Variant; children: ReactNode }) {
  return <Link href={href} className={`${base} ${variants[variant]}`}>{children}</Link>;
}

export function PlusIcon({ size = 40 }: { size?: number }) {
  return (
    <span aria-hidden style={{ width: size, height: size }}
      className="flex flex-none items-center justify-center rounded-full bg-white text-[28px] leading-none font-bold text-blue">
      +
    </span>
  );
}

/* ---------- status ---------- */

export function Spinner({ light = false, size = 20 }: { light?: boolean; size?: number }) {
  return (
    <span aria-hidden style={{ width: size, height: size }}
      className={`inline-block flex-none animate-spin rounded-full border-[3px] ${light ? "border-white/40 border-t-white" : "border-track border-t-blue"}`} />
  );
}

/** Square "!" badge used for urgent rows, danger signs and errors. */
export function Alert({ size = 24, inverse = false }: { size?: number; inverse?: boolean }) {
  return (
    <span aria-hidden style={{ width: size, height: size, fontSize: size * 0.65 }}
      className={`flex flex-none items-center justify-center rounded-md leading-none font-bold ${inverse ? "bg-white text-red" : "bg-red text-white"}`}>
      !
    </span>
  );
}

function RoundBang({ inverse = false }: { inverse?: boolean }) {
  return (
    <span aria-hidden className={`flex h-6 w-6 flex-none items-center justify-center rounded-full text-small font-bold ${inverse ? "bg-white text-ink" : "bg-red text-white"}`}>
      !
    </span>
  );
}

/** A form-level error, e.g. wrong phone number or password. */
export function ErrorNotice({ children }: { children: ReactNode }) {
  if (!children) return null;
  return (
    <div role="alert" className="flex items-start gap-2.5 rounded-[10px] border-2 border-red bg-red-tint p-3 text-small">
      <RoundBang />
      <div>{children}</div>
    </div>
  );
}

/** Connection problems use dark ink, so they are never mistaken for a clinical warning. */
export function OfflineBanner({ detail, onRetry, large = false }: { detail?: string; onRetry?: () => void; large?: boolean }) {
  return (
    <div role="alert" className="flex flex-col gap-3 rounded-xl bg-ink p-4 text-white">
      <div className={large ? "flex flex-col gap-3" : "flex items-start gap-2.5"}>
        <span aria-hidden className={`flex flex-none items-center justify-center rounded-full bg-white font-bold text-ink ${large ? "h-10 w-10 text-heading" : "h-6 w-6 text-small"}`}>!</span>
        <div>
          <p className={large ? "text-headline font-bold" : "text-label font-bold"}>No internet connection, please try again</p>
          {detail && <p className="mt-1 text-small">{detail}</p>}
        </div>
      </div>
      {onRetry && (
        <button type="button" onClick={onRetry} className="h-12 rounded-lg bg-white text-label font-bold text-ink">
          Try again
        </button>
      )}
    </div>
  );
}

export function Loading({ label }: { label: string }) {
  return (
    <div role="status" className="flex flex-1 flex-col items-center justify-center gap-4 py-16 text-center">
      <Spinner size={56} />
      <p className="text-label font-bold">{label}</p>
    </div>
  );
}

export function Disclaimer({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-2.5 rounded-xl bg-surface p-4 text-small">
      <span aria-hidden className="flex h-6 w-6 flex-none items-center justify-center rounded-full border-2 border-ink-soft text-[14px] font-bold text-ink-soft">i</span>
      <p>{text}</p>
    </div>
  );
}

/* ---------- forms ---------- */

export function Field({ label, help, error, children }: { label: string; help?: ReactNode; error?: string | null; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-2">
      <span className="text-label font-bold">{label}</span>
      {children}
      {error ? <FieldError>{error}</FieldError> : help && <span className="text-small text-ink-soft">{help}</span>}
    </label>
  );
}

export function FieldError({ children }: { children: ReactNode }) {
  return (
    <span className="flex items-start gap-2 text-small font-bold text-red">
      <span aria-hidden className="mt-px flex h-5 w-5 flex-none items-center justify-center rounded-full bg-red text-[13px] text-white">!</span>
      {children}
    </span>
  );
}

export function inputClass(invalid = false, mono = false) {
  return `h-14 w-full rounded-[10px] border-2 bg-white px-4 text-body text-ink placeholder:text-edge focus:border-blue focus:outline-none ${invalid ? "border-red" : "border-edge"} ${mono ? "font-mono tracking-wide" : ""}`;
}

/** Password input with a Show / Hide toggle inside the field. */
export function PasswordInput({ value, onChange, show, onToggle, invalid, autoComplete }: {
  value: string; onChange: (v: string) => void; show: boolean; onToggle: () => void; invalid?: boolean; autoComplete: string;
}) {
  return (
    <div className="relative">
      <input className={`${inputClass(invalid, show)} pr-20`} type={show ? "text" : "password"} value={value}
        onChange={(e) => onChange(e.target.value)} autoComplete={autoComplete} />
      <button type="button" onClick={onToggle} aria-label={show ? "Hide password" : "Show password"}
        className="absolute top-1 right-1 h-12 rounded-lg px-3 text-small font-bold text-blue">
        {show ? "Hide" : "Show"}
      </button>
    </div>
  );
}

/** Large selectable tile, for age and sex. */
export function ChoiceTile({ selected, onClick, children }: { selected: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button type="button" aria-pressed={selected} onClick={onClick}
      className={`h-16 rounded-[10px] border-2 text-heading font-bold ${selected ? "border-blue bg-blue text-white" : "border-edge bg-white text-ink"}`}>
      {selected && "✓ "}{children}
    </button>
  );
}

export function ProgressBar({ value }: { value: number }) {
  return (
    <div className="h-3 overflow-hidden rounded-md bg-track" aria-hidden>
      <div className="h-full rounded-md bg-blue transition-[width]" style={{ width: `${Math.max(4, value * 100)}%` }} />
    </div>
  );
}
