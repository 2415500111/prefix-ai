import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import { api, ApiError } from "@/lib/server/api";

import type { ActionResult } from "./action-result";

function failure(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 403) return "Your role cannot do this.";
    if (error.status === 404) return "That record no longer exists.";
    if (error.status === 429) return "Too many requests. Please wait a moment.";
    if (error.status < 500 && error.message) return error.message;
  }
  return "Something went wrong. Please try again.";
}

/**
 * Runs one API call for a staff action and says how it went, for a toast. On success the page
 * refreshes so counts and lists are current. A signed-out session goes to login.
 */
export async function performAction(
  path: string,
  options: { method: "POST"; body?: unknown },
  success: string,
): Promise<ActionResult> {
  try {
    await api(path, options);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect("/login");
    return { ok: false, message: failure(error) };
  }
  refresh();
  return { ok: true, message: success };
}
