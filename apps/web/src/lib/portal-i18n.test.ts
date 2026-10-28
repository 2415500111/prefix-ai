import { describe, expect, it } from "vitest";

import {
  formatDateTime,
  formatRelative,
  formatTime,
  PORTAL_TEXT,
  toPortalLang,
} from "./portal-i18n";

const NOW = Date.parse("2026-11-10T06:30:00Z");
const DAY = 24 * 60 * 60 * 1000;

function keysOf(value: object): string[] {
  return Object.keys(value).sort();
}

describe("portal text", () => {
  it("has every string in both languages", () => {
    expect(keysOf(PORTAL_TEXT.hi)).toEqual(keysOf(PORTAL_TEXT.en));
    expect(keysOf(PORTAL_TEXT.hi.states)).toEqual(
      keysOf(PORTAL_TEXT.en.states),
    );
    for (const value of Object.values(PORTAL_TEXT.hi)) {
      if (typeof value === "string") expect(value).not.toBe("");
    }
  });

  it("keeps the emergency number in both languages", () => {
    expect(PORTAL_TEXT.en.emergencyText).toContain("112");
    expect(PORTAL_TEXT.hi.emergencyText).toContain("112");
  });

  it.each([
    ["hi", "hi"],
    ["hi-IN", "hi"],
    ["en", "en"],
    ["ta", "en"],
    [undefined, "en"],
  ])("maps %s to the %s portal language", (input, expected) => {
    expect(toPortalLang(input)).toBe(expected);
  });
});

describe("formatting", () => {
  it("shows times in the facility's timezone", () => {
    // 06:30 UTC is 12:00 in India.
    expect(formatTime("2026-11-10T06:30:00Z", "Asia/Kolkata", "en")).toMatch(
      /12:00/,
    );
    expect(
      formatDateTime("2026-11-10T06:30:00Z", "America/New_York", "en"),
    ).toMatch(/1:30/);
  });

  it("formats dates in Hindi", () => {
    expect(
      formatDateTime("2026-11-10T06:30:00Z", "Asia/Kolkata", "hi"),
    ).toMatch(/नव॰|नवं/);
  });

  it.each([
    [3 * DAY, "en", "in 3 days"],
    [-2 * DAY, "en", "2 days ago"],
    [5 * 60 * 60 * 1000, "en", "in 5 hours"],
    [20 * 60 * 1000, "en", "in 20 minutes"],
    [3 * DAY, "hi", "3 दिन में"],
  ] as const)("relative time %d ms in %s", (offset, lang, expected) => {
    expect(
      formatRelative(new Date(NOW + offset).toISOString(), NOW, lang),
    ).toBe(expected);
  });
});
