import { describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({ cookies: vi.fn() }));

const { accessTokenExpiresSoon } = await import("./proxy");

function token(exp: unknown): string {
  const payload = Buffer.from(JSON.stringify({ exp })).toString("base64url");
  return `header.${payload}.signature`;
}

describe("accessTokenExpiresSoon", () => {
  const now = Date.UTC(2026, 9, 27, 12, 0, 0);

  it("keeps a token with plenty of time left", () => {
    expect(accessTokenExpiresSoon(token(now / 1000 + 600), now)).toBe(false);
  });

  it("refreshes a token about to expire or already expired", () => {
    expect(accessTokenExpiresSoon(token(now / 1000 + 30), now)).toBe(true);
    expect(accessTokenExpiresSoon(token(now / 1000 - 1), now)).toBe(true);
  });

  it("treats malformed tokens as expired", () => {
    expect(accessTokenExpiresSoon("not-a-jwt", now)).toBe(true);
    expect(accessTokenExpiresSoon("a.###.b", now)).toBe(true);
    expect(accessTokenExpiresSoon(token("soon"), now)).toBe(true);
  });
});
