import { cn } from "cn";
import Link from "next/link";
import type { ReactNode } from "react";

const CHIP =
  "inline-flex h-8 pressable items-center gap-1.5 rounded-full border px-3 text-sm font-medium outline-none focus-visible:ring-3 focus-visible:ring-ring/30";
const ON = "border-urgent bg-urgent-soft text-urgent-foreground";
const OFF = "bg-card text-muted-foreground hover:text-foreground";

/** A filter that is on or off, like "Urgent only". A toggle button in client lists. */
export function FilterChip({
  pressed,
  onPressedChange,
  children,
}: {
  pressed: boolean;
  onPressedChange: (pressed: boolean) => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={() => onPressedChange(!pressed)}
      className={cn(CHIP, pressed ? ON : OFF)}
    >
      {children}
    </button>
  );
}

/** The same chip as a link, for server-rendered pages where the filter lives in the URL. */
export function FilterChipLink({
  active,
  href,
  children,
}: {
  active: boolean;
  href: string;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      scroll={false}
      aria-current={active ? "true" : undefined}
      className={cn(CHIP, active ? ON : OFF)}
    >
      {children}
    </Link>
  );
}
