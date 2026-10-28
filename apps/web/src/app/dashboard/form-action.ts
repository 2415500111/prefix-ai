import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import { api, ApiError } from "@/lib/server/api";

/**
 * Runs one API call for a form action. Form actions return nothing: on success the page
 * refreshes (or moves to `onSuccess`, which also resets its form), and on failure the user is
 * sent back to `back` with a notice. A signed-out session goes to login.
 */
export async function performFormAction(
  back: string,
  path: string,
  options?: { method: "POST"; body?: unknown },
  onSuccess?: string,
): Promise<void> {
  try {
    await api(path, options);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect("/login");
    const separator = back.includes("?") ? "&" : "?";
    redirect(`${back}${separator}notice=failed`);
  }
  if (onSuccess) redirect(onSuccess);
  refresh();
}
