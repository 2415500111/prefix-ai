"use client";

import { cn } from "cn";
import { LayoutGroup, motion } from "motion/react";
import Link from "next/link";
import { useId } from "react";

import { spring } from "@/lib/motion";

/**
 * An iOS segmented control made of links, so each filter has its own URL. The selected pill
 * slides between segments.
 */
export function SegmentedControl({
  label,
  items,
  value,
  className,
}: {
  label: string;
  items: { value: string; label: string; href: string; count?: number }[];
  value: string;
  className?: string;
}) {
  const id = useId();
  return (
    <nav
      aria-label={label}
      className={cn("inline-flex rounded-xl bg-muted p-1", className)}
    >
      <LayoutGroup id={id}>
        {items.map((item) => {
          const active = item.value === value;
          return (
            <Link
              key={item.value}
              href={item.href}
              aria-current={active ? "page" : undefined}
              scroll={false}
              className={cn(
                "pressable relative flex h-8 items-center gap-1.5 rounded-[10px] px-3 text-sm font-medium outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
                active
                  ? "text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {active ? (
                <motion.span
                  layoutId="segment"
                  className="absolute inset-0 rounded-[10px] bg-card shadow-card"
                  transition={spring.snappy}
                />
              ) : null}
              <span className="relative">{item.label}</span>
              {item.count !== undefined ? (
                <span className="relative text-xs text-muted-foreground tabular-nums">
                  {item.count}
                </span>
              ) : null}
            </Link>
          );
        })}
      </LayoutGroup>
    </nav>
  );
}
