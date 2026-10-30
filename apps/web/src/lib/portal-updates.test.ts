import type { PortalNotification } from "@prefix/shared";
import { describe, expect, it } from "vitest";

import { mostUrgentUnread, updateLink, updateText } from "./portal-updates";

const NOW = Date.parse("2026-11-10T06:30:00Z");

function update(overrides: Partial<PortalNotification>): PortalNotification {
  return {
    key: `step-due:${crypto.randomUUID()}`,
    kind: "step_now",
    urgency: "normal",
    created_at: "2026-11-10T05:00:00Z",
    read: false,
    appointment_id: "0b0c3f1e-8f6a-4c55-9a43-6f0b8f9c1d2e",
    procedure_name: "Colonoscopy",
    timezone: "Asia/Kolkata",
    event_id: "11111111-1111-4111-8111-111111111111",
    step_title: "Clear liquids only",
    step_done: false,
    due_at: "2026-11-10T12:30:00Z",
    scheduled_at: null,
    request_status: null,
    message: null,
    ...overrides,
  };
}

describe("update text", () => {
  it("writes each kind from a fixed template, in English and Hindi", () => {
    expect(updateText(update({}), "en", NOW).title).toBe(
      "Do this now: Clear liquids only",
    );
    expect(updateText(update({}), "hi", NOW).title).toBe(
      "अभी करें: Clear liquids only",
    );
    expect(updateText(update({ step_done: true }), "en", NOW).title).toBe(
      "Done: Clear liquids only",
    );
    expect(updateText(update({ kind: "step_soon" }), "en", NOW).body).toMatch(
      /^In 6 hours · /,
    );
  });

  it("uses the care team's own words for a message", () => {
    const text = updateText(
      update({ kind: "care_team_message", message: "Bring your medicines." }),
      "hi",
      NOW,
    );

    expect(text).toEqual({
      title: "आपकी देखभाल टीम का संदेश",
      body: "Bring your medicines.",
    });
  });

  it("follows a reschedule request from pending to the answer", () => {
    const request = (status: "pending" | "approved" | "declined") =>
      updateText(
        update({
          kind: "reschedule_request",
          request_status: status,
          scheduled_at: status === "approved" ? "2026-11-20T04:00:00Z" : null,
        }),
        "en",
        NOW,
      );

    expect(request("pending").title).toBe(
      "We received your request to change the date",
    );
    expect(request("approved").title).toBe("Your new date is confirmed");
    expect(request("approved").body).toMatch(/^Colonoscopy · .*20 Nov/);
    expect(request("declined").title).toBe("We could not change your date");
  });

  it("tells the patient when the procedure moves or is cancelled", () => {
    expect(
      updateText(
        update({
          kind: "appointment_cancelled",
          scheduled_at: "2026-11-13T04:00:00Z",
        }),
        "en",
        NOW,
      ).body,
    ).toMatch(/^Colonoscopy, .*13 Nov.*Please call the hospital/);
    expect(
      updateText(update({ kind: "appointment_moved" }), "hi", NOW).title,
    ).toBe("आपकी प्रक्रिया का समय बदल गया है");
  });
});

describe("update helpers", () => {
  it("picks the newest urgent unread update for the banner", () => {
    const urgent = update({ urgency: "urgent" });
    const items = [
      update({}),
      update({ urgency: "urgent", read: true }),
      urgent,
      update({ urgency: "urgent" }),
    ];

    expect(mostUrgentUnread(items)).toBe(urgent);
    expect(mostUrgentUnread([update({})])).toBeNull();
  });

  it("leads steps to their place in the plan and date changes to Help", () => {
    expect(updateLink(update({}))).toBe(
      "/p/prep#step-11111111-1111-4111-8111-111111111111",
    );
    expect(updateLink(update({ kind: "appointment_moved" }))).toBe("/p/help");
    expect(updateLink(update({ kind: "care_team_message" }))).toBeNull();
  });
});
