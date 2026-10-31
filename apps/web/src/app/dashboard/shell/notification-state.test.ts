import { describe, expect, it } from "vitest";

import { feed, notification } from "./notification-fixtures";
import {
  bellLabel,
  hasChanged,
  notificationHref,
  urgentArrivals,
  withRead,
} from "./notification-state";

describe("staff notification state", () => {
  it("opens the patient's sheet on the tab where the item is dealt with", () => {
    expect(notificationHref(notification())).toBe(
      "/dashboard?appointment=019a0000-0000-7000-8000-0000000000bb&tab=timeline",
    );
    expect(notificationHref(notification({ kind: "RESCHEDULE" }))).toMatch(
      /&tab=requests$/,
    );
    expect(notificationHref(notification({ kind: "QUESTION" }))).toMatch(
      /&tab=overview$/,
    );
    expect(
      notificationHref(notification({ kind: "MESSAGE", appointment_id: null })),
    ).toBe("/dashboard/tasks");
  });

  it("reloads only when the totals or the newest item change", () => {
    const shown = { latest_id: "a", unread_count: 2, urgent_count: 1 };

    expect(hasChanged(shown, { ...shown })).toBe(false);
    expect(hasChanged(shown, { ...shown, latest_id: "b" })).toBe(true);
    expect(hasChanged(shown, { ...shown, unread_count: 1 })).toBe(true);
    expect(hasChanged(null, shown)).toBe(true);
  });

  it("announces only new, unread, urgent items", () => {
    const old = notification();
    const fresh = notification({ id: "019a0000-0000-7000-8000-000000000002" });
    const calm = notification({
      id: "019a0000-0000-7000-8000-000000000003",
      urgent: false,
      urgent_reasons: [],
    });
    const seenElsewhere = notification({
      id: "019a0000-0000-7000-8000-000000000004",
      read: true,
    });

    expect(
      urgentArrivals(
        new Set([old.id]),
        feed([fresh, calm, seenElsewhere, old]),
      ),
    ).toEqual([fresh]);
  });

  it("marks items read locally and lowers the counts", () => {
    const urgent = notification();
    const calm = notification({
      id: "019a0000-0000-7000-8000-000000000002",
      urgent: false,
      urgent_reasons: [],
    });

    const next = withRead(feed([calm, urgent]), new Set([urgent.id]));

    expect(next.items.map((item) => item.read)).toEqual([false, true]);
    expect([next.unread_count, next.urgent_count]).toEqual([1, 0]);
    expect(next.items.map((item) => item.id)).toEqual([calm.id, urgent.id]);
  });

  it("gives the bell a label that includes the number it shows", () => {
    expect(bellLabel(null)).toBe("Notifications");
    expect(
      bellLabel({ latest_id: "a", unread_count: 3, urgent_count: 1 }),
    ).toBe("Notifications, 3 unread, 1 urgent");
    expect(
      bellLabel({ latest_id: "a", unread_count: 2, urgent_count: 0 }),
    ).toBe("Notifications, 2 unread");
  });
});
