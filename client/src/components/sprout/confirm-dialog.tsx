"use client";

// Show, then ask (docs/standards/onboarding-ux.md principle 6), with positive friction only here:
// the person ticks that values can fall, and focus starts on Cancel, the least destructive
// choice (WAI-ARIA dialog pattern). The native <dialog> with showModal() traps focus, closes on
// Escape and makes the page behind it inert.
import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { money, moneyCents } from "@/lib/format";
import type { CardOf } from "@/lib/types";

export function ConfirmDialog({
  card,
  open,
  busy,
  onConfirm,
  onClose,
}: {
  card: CardOf<"confirm">;
  open: boolean;
  busy: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const [understood, setUnderstood] = useState(false);
  const titleId = useId();
  const checkId = useId();

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      d.showModal();
      cancelRef.current?.focus();
    } else if (!open && d.open) {
      d.close();
    }
  }, [open]);

  const verb = card.kind === "buy" ? "Buy" : card.kind === "sell" ? "Sell" : "Move";
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClose={onClose}
      className="m-auto w-[min(560px,calc(100vw-32px))] rounded-lg bg-surface p-0 text-ink shadow-dialog"
    >
      <div className="p-6">
        <h2 id={titleId} className="font-display text-display-2">Check before you confirm</h2>
        <p className="mt-2 text-body text-ink-2">This is exactly what will happen in your practice account.</p>
        <ul className="mt-4 divide-y divide-line rounded-md border border-line">
          {card.orders.map((o) => (
            <li key={`${o.side}-${o.product_id}`} className="flex justify-between gap-3 px-4 py-3 text-body">
              <span>
                {o.side === "sell" ? "Sell" : verb} {moneyCents(o.amount_usd)} of {o.name}
              </span>
            </li>
          ))}
        </ul>
        <dl className="mt-4 space-y-1 text-body-sm text-ink-2">
          <div className="flex justify-between"><dt>Total</dt><dd className="tnum text-ink">{moneyCents(card.total_usd)}</dd></div>
          {card.monthly_usd && (
            <div className="flex justify-between"><dt>Then each month</dt><dd className="tnum text-ink">{money(card.monthly_usd)}</dd></div>
          )}
          {card.fee_usd_a_year > 0 && (
            <div className="flex justify-between"><dt>Fund fees</dt><dd className="tnum text-ink">about {moneyCents(card.fee_usd_a_year)} a year</dd></div>
          )}
        </dl>
        <p className="mt-4 rounded-sm bg-sunken p-3 text-body-sm text-ink-2">
          This is a simulation. No real money moves.
        </p>
        <label htmlFor={checkId} className="mt-4 flex min-h-11 cursor-pointer items-start gap-3 text-body">
          <input
            id={checkId}
            type="checkbox"
            checked={understood}
            onChange={(e) => setUnderstood(e.target.checked)}
            className="mt-1 size-5 accent-[var(--color-primary)]"
          />
          I understand the value can go down as well as up.
        </label>
        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Button ref={cancelRef} variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" disabled={!understood} busy={busy} busyLabel="Placing orders…" onClick={onConfirm}>
            {card.button}
          </Button>
        </div>
      </div>
    </dialog>
  );
}
