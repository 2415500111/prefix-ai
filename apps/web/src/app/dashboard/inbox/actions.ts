"use server";

import { type ActionResult, refused } from "../action-result";
import { performAction } from "../form-action";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MAX_NOTE = 1000;

export async function acknowledgeEscalation(id: string): Promise<ActionResult> {
  if (!UUID.test(id)) return refused("That record no longer exists.");
  return performAction(
    `/escalations/${id}/acknowledge`,
    { method: "POST" },
    "Escalation acknowledged. You own it now.",
  );
}

export async function resolveEscalation(
  id: string,
  formData: FormData,
): Promise<ActionResult> {
  const note = String(formData.get("note") ?? "").trim();
  if (!UUID.test(id)) return refused("That record no longer exists.");
  if (!note) return refused("Write what was done before resolving.");
  return performAction(
    `/escalations/${id}/resolve`,
    { method: "POST", body: { note: note.slice(0, MAX_NOTE) } },
    "Escalation resolved",
  );
}
