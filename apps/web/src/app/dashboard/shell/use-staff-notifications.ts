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
  /** The bell's totals. Null until the first answer (and for roles that cannot see them). */
  summary: StaffNotificationSummary | null;
  /** The list. Null until the bell is opened or something new arrives. */
  feed: StaffNotificationFeed | null;
  /** Fetches the list, e.g. when the bell is opened. */
  loadFeed: () => void;
  /** Marks the item read, then opens the patient's sheet on the relevant tab. */
  open: (item: StaffNotification) => void;
  markAllRead: () => void;
}

/**
 * The bell's live state. Every 15 seconds (and when the tab comes back into view) it asks for
 * the totals, which hold no patient data. The list itself, which names patients, is fetched
 * only when the bell is opened or when something changes. Then urgent arrivals raise a toast
 * and the page refreshes, so the Inbox, Requests and Overview show them too.
 */
export function useStaffNotifications(enabled: boolean): StaffNotifications {
  const router = useRouter();
  const [summary, setSummary] = useState<StaffNotificationSummary | null>(null);
  const [feed, setFeed] = useState<StaffNotificationFeed | null>(null);
  const shown = useRef<StaffNotificationSummary | null>(null);
  const live = useRef(true);

  const show = useCallback((next: StaffNotificationSummary): void => {
    shown.current = next;
    setSummary(next);
  }, []);

  const showFeed = useCallback(
    (next: StaffNotificationFeed | null): void => {
      if (next === null || !live.current) return;
      setFeed(next);
      show(next);
    },
    [show],
  );

  const open = useCallback(
    (item: StaffNotification): void => {
      void (async () => {
        if (!item.read) {
          setFeed((current) =>
            current ? withRead(current, new Set([item.id])) : current,
          );
          const current = shown.current;
          if (current) {
            show({
              ...current,
              unread_count: Math.max(0, current.unread_count - 1),
              urgent_count: Math.max(
                0,
                current.urgent_count - (item.urgent ? 1 : 0),
              ),
            });
          }
          // Read first, so the page we open no longer flags the patient.
          await markStaffNotificationsRead([item.id]);
        }
        router.push(notificationHref(item), { scroll: false });
      })();
    },
    [router, show],
  );

  const loadFeed = useCallback((): void => {
    void loadStaffNotifications().then(showFeed);
  }, [showFeed]);

  useEffect(() => {
    if (!enabled) return;
    live.current = true;

    async function check(): Promise<void> {
      if (document.visibilityState !== "visible") return;
      const latest = await pollStaffNotifications();
      const before = shown.current;
      if (!live.current || latest === null || !hasChanged(before, latest)) {
        return;
      }
      show(latest);
      const next = await loadStaffNotifications();
      if (!live.current || next === null) return;
      // Only what arrived since the last answer is announced, never what was already there.
      if (before !== null && latest.latest_id !== before.latest_id) {
        for (const item of urgentArrivals(before.latest_id, next)) {
          toast.error(`Urgent: ${item.patient_name}`, {
            description: [item.summary, item.procedure_name]
              .filter(Boolean)
              .join(" · "),
            sticky: true,
            action: { label: "Open", onClick: () => open(item) },
          });
        }
      }
      showFeed(next);
      router.refresh();
    }

    void pollStaffNotifications().then((first) => {
      if (live.current && first !== null && shown.current === null) {
        show(first);
      }
    });
    const timer = window.setInterval(() => void check(), POLL_MS);
    const onVisible = () => void check();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      live.current = false;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [enabled, open, router, show, showFeed]);

  const markAllRead = useCallback((): void => {
    setFeed((current) =>
      current
        ? withRead(current, new Set(current.items.map((item) => item.id)))
        : current,
    );
    const current = shown.current;
    // The server marks the whole window, which can hold more than the bell lists.
    if (current) show({ ...current, unread_count: 0, urgent_count: 0 });
    void markAllStaffNotificationsRead().then((result) => {
      if (result.ok) toast.success(result.message);
      else toast.error(result.message);
    });
  }, [show]);

  return { summary, feed, loadFeed, open, markAllRead };
}
