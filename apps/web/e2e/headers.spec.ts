import { expect, test } from "@playwright/test";

const BASE = "http://localhost:3000";

test("pages refuse framing and sniffing, and carry a content security policy", async ({
  request,
}) => {
  const response = await request.get(`${BASE}/login`);

  const headers = response.headers();
  expect(headers["x-frame-options"]).toBe("DENY");
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin");
  expect(headers["content-security-policy"]).toContain(
    "frame-ancestors 'none'",
  );
  expect(headers["content-security-policy"]).toContain("connect-src 'self'");
});
