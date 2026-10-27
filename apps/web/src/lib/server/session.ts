import "server-only";

import type { TokenPair } from "@prefix/shared";
import { cookies } from "next/headers";

/** httpOnly cookies hold the staff tokens; browser JavaScript can never read them. */
export const ACCESS_COOKIE = "prefix_at";
export const REFRESH_COOKIE = "prefix_rt";

export function cookieOptions(expiresAt: string) {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    expires: new Date(expiresAt),
  };
}

export async function getAccessToken(): Promise<string | undefined> {
  return (await cookies()).get(ACCESS_COOKIE)?.value;
}

export async function getRefreshToken(): Promise<string | undefined> {
  return (await cookies()).get(REFRESH_COOKIE)?.value;
}

/** Only callable from Server Actions and Route Handlers. */
export async function storeSession(tokens: TokenPair): Promise<void> {
  const jar = await cookies();
  jar.set(
    ACCESS_COOKIE,
    tokens.access_token,
    cookieOptions(tokens.access_expires_at),
  );
  jar.set(
    REFRESH_COOKIE,
    tokens.refresh_token,
    cookieOptions(tokens.refresh_expires_at),
  );
}

export async function clearSession(): Promise<void> {
  const jar = await cookies();
  jar.delete(ACCESS_COOKIE);
  jar.delete(REFRESH_COOKIE);
}
