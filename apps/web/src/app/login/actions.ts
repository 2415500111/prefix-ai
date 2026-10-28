"use server";

import type { TokenPair } from "@prefix/shared";
import { redirect } from "next/navigation";

import { api, ApiError } from "@/lib/server/api";
import {
  clearSession,
  getRefreshToken,
  storeSession,
} from "@/lib/server/session";

export interface LoginState {
  error: string | null;
}

export async function login(
  _previous: LoginState,
  formData: FormData,
): Promise<LoginState> {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  if (!email || !password) {
    return { error: "Enter your email and password." };
  }

  let tokens: TokenPair;
  try {
    tokens = await api<TokenPair>("/auth/login", {
      method: "POST",
      body: { email, password },
      token: null,
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return { error: "Invalid email or password." };
    }
    return { error: "Sign-in is unavailable right now. Please try again." };
  }

  await storeSession(tokens);
  redirect("/dashboard");
}

/** Sign in to the synthetic demo hospital. The API decides whether guests are allowed. */
export async function loginAsGuest(): Promise<void> {
  let tokens: TokenPair;
  try {
    tokens = await api<TokenPair>("/auth/guest", {
      method: "POST",
      token: null,
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      redirect("/login?guest=unavailable");
    }
    if (error instanceof ApiError && error.status === 429) {
      redirect("/login?guest=busy");
    }
    redirect("/login?guest=error");
  }

  await storeSession(tokens);
  redirect("/dashboard");
}

export async function logout(): Promise<void> {
  const refreshToken = await getRefreshToken();
  if (refreshToken) {
    await api("/auth/logout", {
      method: "POST",
      body: { refresh_token: refreshToken },
      token: null,
    }).catch(() => undefined);
  }
  await clearSession();
  redirect("/login");
}
