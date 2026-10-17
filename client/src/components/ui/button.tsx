"use client";

import { LoaderCircle } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode, Ref } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const STYLES: Record<Variant, string> = {
  primary:
    "h-12 bg-primary text-on-primary hover:bg-primary-hover active:translate-y-px disabled:bg-sunken disabled:text-muted",
  secondary:
    "h-11 border border-border-strong bg-surface text-ink hover:border-ink-2 active:translate-y-px disabled:text-muted",
  ghost: "h-11 text-primary hover:bg-primary-soft disabled:text-muted",
  danger:
    "h-11 border border-danger bg-surface text-danger hover:bg-danger-soft active:translate-y-px",
};

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  icon?: ReactNode;
  busy?: boolean;
  busyLabel?: string;
  ref?: Ref<HTMLButtonElement>;
};

/**
 * Buttons say what happens ("Confirm and place 6 orders"). While a request runs the button keeps
 * its width, shows a spinner and the action in progress, and ignores clicks (no double submits).
 */
export function Button({
  variant = "secondary",
  icon,
  busy = false,
  busyLabel,
  children,
  className = "",
  disabled,
  onClick,
  ref,
  ...rest
}: Props) {
  return (
    <button
      ref={ref}
      type="button"
      {...rest}
      aria-busy={busy || undefined}
      aria-disabled={disabled || busy || undefined}
      disabled={disabled}
      onClick={busy ? undefined : onClick}
      className={`inline-flex min-w-11 items-center justify-center gap-2 rounded-sm px-5 text-button transition-colors duration-[var(--duration-fast)] disabled:cursor-not-allowed ${STYLES[variant]} ${className}`}
    >
      {busy ? <LoaderCircle aria-hidden className="size-5 animate-spin" /> : icon}
      <span>{busy && busyLabel ? busyLabel : children}</span>
    </button>
  );
}
