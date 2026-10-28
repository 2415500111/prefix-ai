"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import { api, ApiError } from "@/lib/server/api";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MAX_NOTE = 1000;

/** A signed-out session goes to login; any other failure reaches the error page. */
async function call(path: string, body?: unknown): Promise<void> {
  try {
    await api(path, { method: "POST", body });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect("/login");
    throw error;
  }
  refresh();
}

export async function acknowledgeEscalation(id: string): Promise<void> {
  if (!UUID.test(id)) return;
  await call(`/escalations/${id}/acknowledge`);
}

export async function resolveEscalation(
  id: string,
  formData: FormData,
): Promise<void> {
  const note = String(formData.get("note") ?? "").trim();
  if (!UUID.test(id) || !note) return;
  await call(`/escalations/${id}/resolve`, { note: note.slice(0, MAX_NOTE) });
}
