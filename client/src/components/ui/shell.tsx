// AppShell: the canopy header with the step bar, the disclosure strip, then the page.
// The step bar is the logo turned into navigation (docs/standards/brand.md section 8).
import Link from "next/link";
import type { ReactNode } from "react";
import { DISCLOSURE, STEPS, type Step } from "@/lib/copy";

export function Wordmark() {
  return (
    <Link href="/" className="flex items-center gap-2 rounded-sm" aria-label="FirstStep home">
      {/* eslint-disable-next-line @next/next/no-img-element -- a 28px SVG mark */}
      <img src="/brand/logo-mark-dark.svg" alt="" width={28} height={28} />
      <span className="font-display text-[1.25rem] leading-7 font-semibold text-on-canopy">
        First<span className="text-primary">Step</span>
      </span>
    </Link>
  );
}

export function StepBar({ current }: { current: Step | null }) {
  const at = current ? STEPS.indexOf(current) : -1;
  return (
    <nav aria-label="Your progress">
      <ol className="flex items-end gap-1">
        {STEPS.map((step, i) => {
          const done = i < at;
          const now = i === at;
          return (
            <li key={step} className="flex flex-col items-center gap-1" aria-current={now ? "step" : undefined}>
              <span
                aria-hidden
                className={`block w-8 rounded-t-sm md:w-12 ${done || now ? "bg-primary" : "bg-on-canopy/20"}`}
                style={{ height: 6 + i * 3 }}
              />
              <span
                className={`hidden text-caption md:block ${now ? "font-semibold text-on-canopy" : "text-on-canopy/70"}`}
              >
                {step}
              </span>
              <span className="sr-only">
                {step}
                {done ? " (done)" : now ? " (current step)" : ""}
              </span>
            </li>
          );
        })}
      </ol>
      {current && (
        <p className="mt-1 text-caption text-on-canopy md:hidden">
          Step {at + 1} of {STEPS.length}: {current}
        </p>
      )}
    </nav>
  );
}

export function AppShell({
  step,
  actions,
  children,
}: {
  step: Step | null;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="bg-canopy">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-4 px-4 py-3 md:px-8">
          <Wordmark />
          <div className="flex items-center gap-4">
            <StepBar current={step} />
            {actions}
          </div>
        </div>
        <p className="max-w-none border-t border-on-canopy/15 px-4 py-1.5 text-center text-caption text-on-canopy/85">
          {DISCLOSURE}
        </p>
      </header>
      <main className="mx-auto w-full max-w-[1200px] flex-1 px-4 py-6 md:px-8 md:py-8">{children}</main>
    </div>
  );
}
