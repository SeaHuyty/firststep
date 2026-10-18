"use client";

// Welcome: understand in five seconds what this is, feel that it is safe, and start by doing
// rather than reading (docs/standards/onboarding-ux.md screen 0; research in
// docs/research/ux-psychology.md, "Welcome page").
//  - Sprout asks the real first question right here, with tappable answers. Tapping one starts
//    the session with that answer saved (gradual engagement, Wroblewski; Lemonade's one
//    question at a time). There is no separate "Start" button to read past.
//  - The promises are plain text with no box, so nothing that cannot be clicked looks like a
//    button (NN/g, clickable elements). The demo people are raised cards with a "Try as" link,
//    so they clearly can be (NN/g, cards: a drop shadow signals clickability).
import { ArrowRight, Clock, Eye, Lock, ShieldCheck, Sprout } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useLayoutEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { PROMISES } from "@/lib/copy";
import { prefersReducedMotion } from "@/lib/motion";
import type { CardOf } from "@/lib/types";
import { Avatar, BUBBLE, TypingIndicator } from "./bubble";
import { CHIP } from "./question";

const ICONS = [Sprout, Eye, ShieldCheck];
const PEOPLE = [
  { key: "amina", name: "Amina", line: "21, student, has credit card debt", sees: "Hears “not yet” and gets a savings plan first." },
  { key: "leo", name: "Leo", line: "27, first job, saving for the long run", sees: "Invests, then lives through the March 2020 crash." },
  { key: "mei", name: "Mei", line: "58, near retirement, wants big returns", sees: "Asks for all tech stocks and hears why not." },
];
const GREETING = "Hi, I'm Sprout. I'll help you make a first investing plan. Let's start with an easy one.";

type Chip = { label: string; value: unknown };
type FirstQuestion = Pick<CardOf<"question">, "question_id" | "prompt" | "chips">;

/** The real first question from the server, shown once Sprout has "typed" it (at least a short
 * beat, so the greeting reads as a reply rather than a page that was already there). */
function useFirstQuestion() {
  const [question, setQuestion] = useState<FirstQuestion | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    const beat = new Promise((r) => setTimeout(r, prefersReducedMotion() ? 0 : 700));
    Promise.all([fetch("/api/catalog").then((r) => (r.ok ? r.json() : null)), beat])
      .then(([data]) => {
        if (!live) return;
        const q = (data as { first_question?: FirstQuestion } | null)?.first_question;
        if (q) setQuestion(q);
        else setFailed(true);
      })
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, []);
  return { question, failed };
}

export function Welcome() {
  const router = useRouter();
  const { question, failed } = useFirstQuestion();
  const [starting, setStarting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Next keeps this page alive (hidden) after we navigate away, so Back would show it still
  // "starting" with every button disabled. Reset when it is hidden
  // (node_modules/next/dist/docs/01-app/02-guides/preserving-ui-state.md).
  useLayoutEffect(
    () => () => {
      setStarting(null);
      setError(null);
    },
    [],
  );

  const start = async (key: string, persona?: string, first?: Chip) => {
    if (starting) return;
    setStarting(key);
    setError(null);
    try {
      const s = await api.newSession(persona);
      if (first && question) {
        await api.act(s.id, {
          tool: "answer_question",
          args: { question_id: question.question_id, value: first.value },
          label: first.label,
        });
      }
      router.push(`/s/${s.id}`);
    } catch (e) {
      setError((e as Error).message);
      setStarting(null);
    }
  };

  return (
    <div className="mx-auto max-w-5xl">
      <div className="grid items-start gap-8 lg:grid-cols-[1fr_minmax(0,26rem)] lg:gap-12">
        <div className="lg:pt-6">
          <h1 className="font-display text-display-1 text-ink">Your first investing plan, one step at a time.</h1>
          <p className="mt-4 text-body-lg text-ink-2">
            Sprout is a guide for first-time investors. It checks whether now is a good time, finds your
            risk level, and builds a simple plan you can try with practice money.
          </p>
          <ul className="mt-8 hidden space-y-5 lg:block">
            <Promises />
          </ul>
        </div>

        <section
          aria-labelledby="first-question"
          className="rounded-lg border border-line bg-surface p-5 sm:p-6"
        >
          <h2 id="first-question" className="text-overline text-primary uppercase">
            Start your money check
          </h2>
          <div className="mt-4 space-y-3" aria-live="polite">
            {!question && !failed && <TypingIndicator />}
            {question && (
              <div className="flex gap-3 animate-rise">
                <Avatar />
                <div className="min-w-0 flex-1 space-y-3">
                  <p className={BUBBLE}>{GREETING}</p>
                  <p className={`${BUBBLE} font-semibold`}>{question.prompt}</p>
                </div>
              </div>
            )}
          </div>
          {question && (
            <div className="mt-4 flex flex-wrap gap-2 animate-rise" role="group" aria-label={question.prompt} style={{ animationDelay: "120ms" }}>
              {question.chips.map((chip) => (
                <ChipButton
                  key={chip.label}
                  chip={chip}
                  busy={starting === chip.label}
                  disabled={starting !== null}
                  onClick={() => start(chip.label, undefined, chip)}
                />
              ))}
            </div>
          )}
          {failed && (
            <Button variant="primary" busy={starting === "me"} busyLabel="Starting…" onClick={() => start("me")}>
              Start my money check
            </Button>
          )}
          <p className="mt-5 flex flex-wrap gap-x-4 gap-y-1 text-caption text-muted">
            <span className="inline-flex items-center gap-1">
              <Clock aria-hidden className="size-3.5" /> About 5 minutes
            </span>
            <span className="inline-flex items-center gap-1">
              <Lock aria-hidden className="size-3.5" /> No sign-up, practice money only
            </span>
          </p>
          {error && (
            <div className="mt-4">
              <Notice tone="error" title="We couldn't start">{error}</Notice>
            </div>
          )}
        </section>

        <ul className="space-y-5 lg:hidden">
          <Promises />
        </ul>
      </div>

      <section className="mt-12" aria-labelledby="demo-people">
        <h2 id="demo-people" className="text-heading">Or see how it goes for someone else</h2>
        <p className="mt-1 text-body-sm text-ink-2">Sprout marks their answers, so you can click through in a minute.</p>
        <ul className="mt-4 grid gap-4 sm:grid-cols-3">
          {PEOPLE.map((p) => (
            <li key={p.key}>
              <button
                type="button"
                onClick={() => start(p.key, p.key)}
                disabled={starting !== null}
                className="group flex h-full w-full flex-col rounded-md border border-line bg-surface p-4 text-left shadow-card transition-[box-shadow,border-color,translate] duration-[var(--duration-base)] ease-[var(--ease-standard)] hover:-translate-y-0.5 hover:border-primary hover:shadow-card-hover active:translate-y-0 disabled:opacity-50 disabled:hover:translate-y-0"
              >
                <span className="flex items-center gap-3">
                  <span aria-hidden className="grid size-10 place-items-center rounded-full bg-primary-soft font-display text-title text-primary">
                    {p.name[0]}
                  </span>
                  <span>
                    <span className="block text-title text-ink">{p.name}</span>
                    <span className="block text-body-sm text-ink-2">{p.line}</span>
                  </span>
                </span>
                <span className="mt-3 block flex-1 text-body-sm text-ink-2">{p.sees}</span>
                <span className="mt-4 inline-flex items-center gap-1 text-label text-primary">
                  {starting === p.key ? "Starting…" : `Try as ${p.name}`}
                  <ArrowRight aria-hidden className="size-4 transition-transform group-hover:translate-x-0.5" />
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function Promises() {
  return PROMISES.map((p, i) => {
    const Icon = ICONS[i] ?? Sprout;
    return (
      <li key={p.title} className="flex gap-3">
        <Icon aria-hidden className="mt-0.5 size-5 shrink-0 text-primary" />
        <p>
          <span className="block text-title text-ink">{p.title}</span>
          <span className="block text-body-sm text-ink-2">{p.text}</span>
        </p>
      </li>
    );
  });
}

function ChipButton({ chip, busy, disabled, onClick }: { chip: Chip; busy: boolean; disabled: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-busy={busy || undefined}
      className={`${CHIP} aria-busy:bg-primary aria-busy:text-on-primary aria-busy:opacity-100`}
    >
      {chip.label}
    </button>
  );
}
