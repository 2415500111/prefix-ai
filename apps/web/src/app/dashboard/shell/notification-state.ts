import type {
  StaffNotification,
  StaffNotificationFeed,
  StaffNotificationKind,
  StaffNotificationSummary,
} from "@prefix/shared";

import type { SheetTab } from "../coordinator/sheet-tabs";

/** The patient sheet's tab where each kind of item is dealt with. */
const SHEET_TAB: Record<StaffNotificationKind, SheetTab> = {
  PROBLEM: "timeline",
  QUESTION: "overview",
  HELP: "overview",
  MESSAGE: "messages",
  RESCHEDULE: "requests",
};

/** Opens the patient's sheet on the relevant tab, or the list that holds the item. */
export function notificationHref(item: StaffNotification): string {
  if (item.appointment_id) {
    return `/dashboard?appointment=${item.appointment_id}&tab=${SHEET_TAB[item.kind]}`;
  }
  if (item.kind === "RESCHEDULE") return "/dashboard/requests";
  return item.kind === "MESSAGE" ? "/dashboard/tasks" : "/dashboard/inbox";
}

/** True when the server's totals differ from what the bell shows, so it should reload. */
export function hasChanged(
  shown: StaffNotificationSummary | null,
  latest: StaffNotificationSummary,
): boolean {
  return (
    shown === null ||
    shown.latest_id !== latest.latest_id ||
    shown.unread_count !== latest.unread_count ||
    shown.urgent_count !== latest.urgent_count
  );
}

/** Items in ``next`` that were not shown before and still need someone: unread and urgent. */
export function urgentArrivals(
  seen: ReadonlySet<string>,
  next: StaffNotificationFeed,
): StaffNotification[] {
  return next.items.filter(
    (item) => !seen.has(item.id) && item.urgent && !item.read,
  );
}

/** The feed with these items read, as the server will have it once it agrees. */
export function withRead(
  feed: StaffNotificationFeed,
  ids: ReadonlySet<string>,
): StaffNotificationFeed {
  let unread = 0;
  let urgent = 0;
  const items = feed.items.map((item) => {
    if (item.read || !ids.has(item.id)) return item;
    unread += 1;
    if (item.urgent) urgent += 1;
    return { ...item, read: true };
  });
  return {
    ...feed,
    items,
    unread_count: Math.max(0, feed.unread_count - unread),
    urgent_count: Math.max(0, feed.urgent_count - urgent),
  };
}

/** What the bell's button says to a screen reader; it includes the number it shows. */
export function bellLabel(feed: StaffNotificationSummary | null): string {
  if (!feed || feed.unread_count === 0) return "Notifications";
  const urgent = feed.urgent_count > 0 ? `, ${feed.urgent_count} urgent` : "";
  return `Notifications, ${feed.unread_count} unread${urgent}`;
}
