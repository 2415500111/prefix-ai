"use client";

import type {
  StaffNotification,
  StaffNotificationFeed,
  StaffNotificationKind,
} from "@prefix/shared";
import { cn } from "cn";
import {
  CalendarClock,
  LifeBuoy,
  type LucideIcon,
  MessageCircleQuestionMark,
  MessageSquare,
  ShieldAlert,
  Siren,
  TriangleAlert,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import type { MouseEvent } from "react";
import { useState } from "react";

import { UrgentPill } from "@/components/urgency";
import { Button } from "@/components/ui/button";
import { FilterChip } from "@/components/ui/filter-chip";
import { RaisedTime } from "@/components/ui/raised-time";
import { Skeleton } from "@/components/ui/skeleton";
import { exit, spring } from "@/lib/motion";

import { notificationHref } from "./notification-state";

const KIND_ICON: Record<StaffNotificationKind, LucideIcon> = {
  PROBLEM: TriangleAlert,
  QUESTION: MessageCircleQuestionMark,
  HELP: LifeBuoy,
  MESSAGE: MessageSquare,
  RESCHEDULE: CalendarClock,
};

function plainClick(event: MouseEvent): boolean {
  return (
    event.button === 0 &&
    !event.metaKey &&
    !event.ctrlKey &&
    !event.shiftKey &&
    !event.altKey
  );
}

/** One thing a patient raised: who, which procedure, what, and when. */
export function NotificationRow({
  item,
  onOpen,
}: {
  item: StaffNotification;
  onOpen: (item: StaffNotification) => void;
}) {
  const Icon = item.urgent_reasons.includes("red_flag")
    ? ShieldAlert
    : KIND_ICON[item.kind];
  return (
    <Link
      href={notificationHref(item)}
      onClick={(event) => {
        if (!plainClick(event)) return;
        event.preventDefault();
        onOpen(item);
      }}
      data-urgent={item.urgent || undefined}
      className={cn(
        "flex pressable items-start gap-3 rounded-xl border-l-4 py-2.5 pr-2.5 pl-2 outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/30",
        item.urgent ? "border-l-urgent" : "border-l-transparent",
      )}
    >
      <span
        className={cn(
          "grid size-8 shrink-0 place-items-center rounded-full",
          item.urgent
            ? "bg-urgent-soft text-urgent"
            : "bg-muted text-muted-foreground",
        )}
      >
        <Icon className="size-4" aria-hidden />
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="flex items-center gap-2">
          <span
            className={cn(
              "truncate text-sm",
              item.read ? "font-medium" : "font-semibold",
            )}
          >
            {item.patient_name}
          </span>
          {item.urgent ? <UrgentPill /> : null}
          {item.read ? null : (
            <span className="ml-auto size-2 shrink-0 rounded-full bg-primary">
              <span className="sr-only">Unread</span>
            </span>
          )}
        </span>
        {item.procedure_name ? (
          <span className="truncate text-xs text-muted-foreground">
            {item.procedure_name}
          </span>
        ) : null}
        <span className="line-clamp-2 text-sm">{item.summary}</span>
        <RaisedTime iso={item.created_at} timeZone={item.timezone} />
      </span>
    </Link>
  );
}

/**
 * The bell's list, newest first exactly as the API orders it. Urgent items are marked, never
 * moved; "Urgent only" hides the rest. New items slide in at the top.
 */
export function NotificationPanel({
  feed,
  onOpen,
  onMarkAllRead,
}: {
  feed: StaffNotificationFeed | null;
  onOpen: (item: StaffNotification) => void;
  onMarkAllRead: () => void;
}) {
  const [urgentOnly, setUrgentOnly] = useState(false);

  if (feed === null) {
    return (
      <div
        role="status"
        aria-label="Loading notifications"
        className="flex flex-col gap-2 p-1"
      >
        <Skeleton className="h-16" />
        <Skeleton className="h-16" />
        <Skeleton className="h-16" />
      </div>
    );
  }

  const items = urgentOnly
    ? feed.items.filter((item) => item.urgent)
    : feed.items;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2 px-1">
        <FilterChip pressed={urgentOnly} onPressedChange={setUrgentOnly}>
          <Siren className="size-3.5" aria-hidden />
          Urgent only
        </FilterChip>
        <Button
          variant="ghost"
          size="sm"
          className="ml-auto"
          disabled={feed.unread_count === 0}
          onClick={onMarkAllRead}
        >
          Mark all read
        </Button>
      </div>
      {items.length === 0 ? (
        <p className="px-2 py-6 text-center text-sm text-muted-foreground">
          {urgentOnly
            ? "Nothing urgent right now."
            : "Nothing from patients in the last two weeks."}
        </p>
      ) : (
        <ul
          aria-label="Notifications, newest first"
          className="-mx-1 flex max-h-[min(28rem,70dvh)] flex-col gap-0.5 overflow-y-auto px-1"
        >
          <AnimatePresence initial={false}>
            {items.map((item) => (
              <motion.li
                key={item.id}
                layout="position"
                initial={{ opacity: 0, y: -12 }}
                animate={{ opacity: 1, y: 0, transition: spring.gentle }}
                exit={{ opacity: 0, transition: exit }}
              >
                <NotificationRow item={item} onOpen={onOpen} />
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}
    </div>
  );
}
