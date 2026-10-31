"use client";

import type {
  StaffNotification,
  StaffNotificationFeed,
  StaffNotificationSummary,
} from "@prefix/shared";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { toast } from "@/components/ui/toast";

import {
  loadStaffNotifications,
  markAllStaffNotificationsRead,
  markStaffNotificationsRead,
  pollStaffNotifications,
} from "./actions";
import {
  hasChanged,
  notificationHref,
  urgentArrivals,
  withRead,
} from "./notification-state";

/** How often the bell asks whether anything changed. */
export const POLL_MS = 15_000;

export interface StaffNotifications {
  /** Null until the first load (and for roles that cannot see notifications). */
  feed: StaffNotificationFeed | null;
  /** Marks the item read, then opens the patient's sheet on the relevant tab. */
  open: (item: StaffNotification) => void;
  markAllRead: () => void;
}

/**
 * The bell's live feed. Every 15 seconds (and when the tab comes back into view) it asks for
 * the totals, which hold no patient data; only when they change does it reload the feed and
 * refresh the page, so the Inbox, Requests and Overview show the new item too. Urgent items
 * that arrive while the app is open also raise a toast.
 */
export function useStaffNotifications(enabled: boolean): StaffNotifications {
  const router = useRouter();
  const [feed, setFeed] = useState<StaffNotificationFeed | null>(null);
  const shown = useRef<StaffNotificationSummary | null>(null);
  const seen = useRef<Set<string> | null>(null);

  const show = useCallback((next: StaffNotificationFeed): void => {
    shown.current = next;
    setFeed(next);
  }, []);

  const open = useCallback(
    (item: StaffNotification): void => {
      void (async () => {
        if (!item.read) {
          setFeed((current) => {
            if (!current) return current;
            const next = withRead(current, new Set([item.id]));
            shown.current = next;
            return next;
          });
          // Read first, so the page we open no longer flags the patient.
          await markStaffNotificationsRead([item.id]);
        }
        router.push(notificationHref(item), { scroll: false });
      })();
    },
    [router],
  );

  // Shows a freshly loaded feed. With ``announce``, urgent items new since the last load
  // raise a toast; the first load of a page never does.
  const apply = useCallback(
    (next: StaffNotificationFeed | null, announce: boolean): void => {
      if (next === null) return;
      const before = seen.current;
      if (announce && before !== null) {
        for (const item of urgentArrivals(before, next)) {
          toast.error(`Urgent: ${item.patient_name}`, {
            description: [item.summary, item.procedure_name]
              .filter(Boolean)
              .join(" · "),
            sticky: true,
            action: { label: "Open", onClick: () => open(item) },
          });
        }
      }
      seen.current = new Set([
        ...(before ?? []),
        ...next.items.map((item) => item.id),
      ]);
      show(next);
    },
    [open, show],
  );

  useEffect(() => {
    if (!enabled) return;
    let active = true;

    async function check(): Promise<void> {
      if (document.visibilityState !== "visible") return;
      const latest = await pollStaffNotifications();
      if (!active || latest === null || !hasChanged(shown.current, latest)) {
        return;
      }
      const next = await loadStaffNotifications();
      if (!active) return;
      apply(next, true);
      router.refresh();
    }

    void loadStaffNotifications().then((next) => {
      if (active) apply(next, false);
    });
    const timer = window.setInterval(() => void check(), POLL_MS);
    const onVisible = () => void check();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      active = false;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [enabled, apply, router]);

  const markAllRead = useCallback((): void => {
    setFeed((current) => {
      if (!current) return current;
      // The server marks the whole window, which can hold more than the bell lists.
      const next = {
        ...withRead(current, new Set(current.items.map((item) => item.id))),
        unread_count: 0,
        urgent_count: 0,
      };
      shown.current = next;
      return next;
    });
    void markAllStaffNotificationsRead().then((result) => {
      if (result.ok) toast.success(result.message);
      else toast.error(result.message);
    });
  }, []);

  return { feed, open, markAllRead };
}
