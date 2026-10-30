"use client";

import type { Badges } from "@prefix/shared";
import { cn } from "cn";
import { RotateCcw, Stethoscope } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { ActionButton } from "@/components/action-runner";
import { AnimatedNumber } from "@/components/ui/animated";

import { resetDemo } from "../demo/actions";
import { isActive, NAV_GROUPS } from "./nav";

/** The macOS-style sidebar. Also used inside the mobile navigation sheet. */
export function SidebarNav({
  badges,
  canResetDemo,
  onNavigate,
}: {
  badges: Badges;
  canResetDemo: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="flex flex-col gap-5">
      {NAV_GROUPS.map((group) => (
        <div key={group.label} className="flex flex-col gap-0.5">
          <p className="px-3 pb-1 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
            {group.label}
          </p>
          {group.items.map((item) => {
            const active = isActive(pathname, item.href);
            const count = item.badge ? badges[item.badge] : 0;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex h-9 pressable items-center gap-2.5 rounded-lg px-3 text-sm font-medium outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
                  active
                    ? "bg-primary-soft text-primary-soft-foreground"
                    : "text-foreground/80 hover:bg-muted hover:text-foreground",
                )}
              >
                <Icon
                  className="size-[18px] shrink-0"
                  strokeWidth={1.75}
                  aria-hidden
                />
                <span className="flex-1">{item.label}</span>
                {count > 0 ? (
                  <span
                    className={cn(
                      "min-w-6 rounded-full px-1.5 text-center text-xs font-semibold",
                      item.badge === "open_escalations"
                        ? "bg-urgent text-white dark:text-[#1a0606]"
                        : "bg-primary text-primary-foreground",
                    )}
                  >
                    <AnimatedNumber value={count} />
                    <span className="sr-only"> {item.badgeLabel}</span>
                  </span>
                ) : null}
              </Link>
            );
          })}
          {group.label === "Admin" && canResetDemo ? (
            <ActionButton
              variant="ghost"
              className="h-9 justify-start gap-2.5 px-3 font-medium text-foreground/80"
              action={async () => resetDemo()}
              confirm={{
                title: "Reset the demo hospital?",
                description:
                  "Every made-up patient, booking and answer is rebuilt from scratch. Protocols and staff accounts stay.",
                confirmLabel: "Reset demo",
                tone: "danger",
              }}
            >
              <RotateCcw
                className="size-[18px]"
                strokeWidth={1.75}
                aria-hidden
              />
              Reset demo
            </ActionButton>
          ) : null}
        </div>
      ))}
    </nav>
  );
}

export function Sidebar({
  badges,
  canResetDemo,
}: {
  badges: Badges;
  canResetDemo: boolean;
}) {
  return (
    <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 flex-col gap-6 overflow-y-auto border-r bg-sidebar px-3 py-5 md:flex">
      <Brand />
      <SidebarNav badges={badges} canResetDemo={canResetDemo} />
    </aside>
  );
}

export function Brand() {
  return (
    <Link
      href="/dashboard"
      className="flex items-center gap-2 px-3 text-[15px] font-semibold tracking-tight"
    >
      <span className="grid size-7 place-items-center rounded-lg bg-primary text-primary-foreground">
        <Stethoscope className="size-4" aria-hidden />
      </span>
      Prefix AI
    </Link>
  );
}
