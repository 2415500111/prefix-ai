import type { StaffNotification, StaffNotificationFeed } from "@prefix/shared";

/** Test data for the bell: one urgent, unread problem report unless overridden. */
export function notification(
  overrides: Partial<StaffNotification> = {},
): StaffNotification {
  return {
    id: "019a0000-0000-7000-8000-000000000001",
    kind: "PROBLEM",
    summary: "Cannot complete: Clear liquids",
    patient_id: "019a0000-0000-7000-8000-0000000000aa",
    patient_name: "Neha Sharma",
    appointment_id: "019a0000-0000-7000-8000-0000000000bb",
    procedure_name: "Colonoscopy",
    scheduled_at: "2026-10-31T04:30:00Z",
    timezone: "Asia/Kolkata",
    created_at: "2026-10-30T07:32:00Z",
    urgent: true,
    urgent_reasons: ["critical_step"],
    open: true,
    read: false,
    ...overrides,
  };
}

export function feed(items: StaffNotification[]): StaffNotificationFeed {
  return {
    items,
    latest_id: items[0]?.id ?? null,
    unread_count: items.filter((item) => !item.read).length,
    urgent_count: items.filter((item) => item.urgent && !item.read).length,
  };
}
