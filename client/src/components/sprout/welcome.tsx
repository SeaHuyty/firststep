"use client";

// Welcome: understand in five seconds what this is and that it is safe
// (docs/standards/onboarding-ux.md screen 0). One primary action; demo people are secondary.
import { Eye, ShieldCheck, Sprout } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { PROMISES } from "@/lib/copy";

const ICONS = [Sprout, Eye, ShieldCheck];
const PEOPLE = [
  { key: "amina", name: "Amina", line: "21, student, has credit card debt" },
  { key: "leo", name: "Leo", line: "27, first job, saving for the long run" },
  { key: "mei", name: "Mei", line: "58, near retirement, wants big returns" },
];

export function Welcome() {
  const router = useRouter();
  const [starting, setStarting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const start = async (persona?: string) => {
    if (starting) return;
    setStarting(persona ?? "me");
    setError(null);
    try {
      const s = await api.newSession(persona);
      router.push(`/s/${s.id}`);
    } catch (e) {
      setError((e as Error).message);
      setStarting(null);
    }
  };

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="font-display text-display-1 text-ink">Your first investing plan, one step at a time.</h1>
      <p className="mt-3 text-body-lg text-ink-2">
        Sprout is a guide for first-time investors. It checks whether now is a good time, finds
        your risk level, and builds a simple plan you can try in a practice account.
      </p>
      <ul className="mt-8 grid gap-4 sm:grid-cols-3">
        {PROMISES.map((p, i) => {
          const Icon = ICONS[i] ?? Sprout;
          return (
            <li key={p.title} className="rounded-md border border-line bg-surface p-4">
              <Icon aria-hidden className="size-6 text-primary" />
              <p className="mt-2 text-title">{p.title}</p>
              <p className="mt-1 text-body-sm text-ink-2">{p.text}</p>
            </li>
          );
        })}
      </ul>
      <div className="mt-8">
        <Button variant="primary" busy={starting === "me"} busyLabel="Starting…" onClick={() => start()}>
          Start my money check
        </Button>
      </div>
      {error && (
        <div className="mt-4">
          <Notice tone="error" title="We couldn't start">{error}</Notice>
        </div>
      )}
      <section className="mt-10" aria-labelledby="demo-people">
        <h2 id="demo-people" className="text-heading">Or try a demo person</h2>
        <ul className="mt-3 grid gap-3 sm:grid-cols-3">
          {PEOPLE.map((p) => (
            <li key={p.key}>
              <button
                type="button"
                onClick={() => start(p.key)}
                disabled={starting !== null}
                className="flex min-h-11 w-full flex-col items-start rounded-md border border-border-strong bg-surface p-4 text-left hover:bg-sunken disabled:opacity-40"
              >
                <span className="text-title">{starting === p.key ? "Starting…" : p.name}</span>
                <span className="text-body-sm text-ink-2">{p.line}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
