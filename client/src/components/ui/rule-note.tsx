"use client";

import { useState } from "react";
import { RuleChip } from "./primitives";

/**
 * The rule behind a decision, one click away: the plain words come first, the rule ID is there
 * for anyone tracing it to rules.yaml and the audit log (progressive disclosure).
 */
export function RuleNote({ ids }: { ids: string[] }) {
  const [open, setOpen] = useState(false);
  if (ids.length === 0) return null;
  return (
    <div className="mt-1">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="min-h-11 rounded-sm text-label text-primary underline decoration-dotted underline-offset-4"
      >
        {open ? "Hide the rule" : "Which rule?"}
      </button>
      {open && (
        <p className="flex flex-wrap items-center gap-2 rounded-sm bg-surface/60 p-2 text-body-sm text-ink-2">
          Checked against {ids.length === 1 ? "rule" : "rules"} {ids.map((id) => <RuleChip key={id} id={id} />)}
          <span>Every check is in the audit log.</span>
        </p>
      )}
    </div>
  );
}
