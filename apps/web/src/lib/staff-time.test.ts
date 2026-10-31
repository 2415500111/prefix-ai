import { describe, expect, it } from "vitest";

import { raisedAt, timeAgo } from "./staff-time";

const RAISED = "2026-10-30T07:32:00Z";
const at = (minutes: number) => Date.parse(RAISED) + minutes * 60_000;

describe("staff times", () => {
  it("shows when it was raised in the facility's time zone", () => {
    expect(raisedAt(RAISED, "Asia/Kolkata")).toBe("30 Oct, 1:02 pm");
    expect(raisedAt(RAISED, "America/New_York")).toBe("30 Oct, 3:32 am");
  });

  it("says how long ago in plain words", () => {
    expect(timeAgo(RAISED, at(0.5))).toBe("just now");
    expect(timeAgo(RAISED, at(2))).toBe("2 min ago");
    expect(timeAgo(RAISED, at(59))).toBe("59 min ago");
    expect(timeAgo(RAISED, at(3 * 60 + 5))).toBe("3 h ago");
    expect(timeAgo(RAISED, at(26 * 60))).toBe("yesterday");
    expect(timeAgo(RAISED, at(4 * 24 * 60))).toBe("4 days ago");
  });

  it("never says a time is in the future", () => {
    expect(timeAgo(RAISED, at(-5))).toBe("just now");
  });
});
