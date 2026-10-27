import type { TokenPair } from "@prefix/shared";
import { NextResponse, type NextRequest } from "next/server";

import { apiBaseUrl } from "@/lib/server/api";
import {
  ACCESS_COOKIE,
  cookieOptions,
  REFRESH_COOKIE,
} from "@/lib/server/session";

/** Refresh this long before the access token expires, so a page never renders with a dead token. */
const REFRESH_MARGIN_MS = 60_000;

/** Reads the `exp` claim without verifying the signature: the API verifies every request;
 * this only decides when to refresh. */
export function accessTokenExpiresSoon(
  token: string,
  now = Date.now(),
): boolean {
  const payload = token.split(".")[1];
  if (!payload) return true;
  try {
    const json = JSON.parse(
      Buffer.from(payload, "base64url").toString("utf8"),
    ) as { exp?: unknown };
    return (
      typeof json.exp !== "number" || json.exp * 1000 - now < REFRESH_MARGIN_MS
    );
  } catch {
    return true;
  }
}

function toLogin(request: NextRequest): NextResponse {
  const response = NextResponse.redirect(new URL("/login", request.url));
  response.cookies.delete(ACCESS_COOKIE);
  response.cookies.delete(REFRESH_COOKIE);
  return response;
}

export async function proxy(request: NextRequest): Promise<NextResponse> {
  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  if (access && !accessTokenExpiresSoon(access)) return NextResponse.next();

  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;
  if (!refresh) return toLogin(request);

  let tokens: TokenPair;
  try {
    const response = await fetch(`${apiBaseUrl()}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
      cache: "no-store",
    });
    if (!response.ok) return toLogin(request);
    tokens = (await response.json()) as TokenPair;
  } catch {
    return toLogin(request);
  }

  // Forward the new tokens to this render (request) and store them in the browser (response).
  request.cookies.set(ACCESS_COOKIE, tokens.access_token);
  request.cookies.set(REFRESH_COOKIE, tokens.refresh_token);
  const response = NextResponse.next({ request: { headers: request.headers } });
  response.cookies.set(
    ACCESS_COOKIE,
    tokens.access_token,
    cookieOptions(tokens.access_expires_at),
  );
  response.cookies.set(
    REFRESH_COOKIE,
    tokens.refresh_token,
    cookieOptions(tokens.refresh_expires_at),
  );
  return response;
}

export const config = {
  matcher: ["/dashboard/:path*"],
};
