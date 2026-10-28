"use server";

import { performFormAction } from "../form-action";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const CANCEL_REASONS = [
  "INADEQUATE_BOWEL_PREP",
  "ATE_OR_DRANK",
  "MEDICATION_NOT_STOPPED",
  "NO_ESCORT",
  "MISSING_LABS",
  "MISSING_PAPERWORK",
  "PATIENT_NO_SHOW",
  "PATIENT_REQUESTED",
  "CLINICAL_REASON",
  "FACILITY_OR_STAFF",
] as const;

export async function resendFailed(appointmentId: string): Promise<void> {
  if (!UUID.test(appointmentId)) return;
  await performFormAction(
    `/dashboard?appointment=${appointmentId}`,
    `/dashboard/appointments/${appointmentId}/resend-failed`,
    { method: "POST" },
  );
}

export async function confirmStep(
  appointmentId: string,
  eventId: string,
): Promise<void> {
  if (!UUID.test(appointmentId) || !UUID.test(eventId)) return;
  await performFormAction(
    `/dashboard?appointment=${appointmentId}`,
    `/appointments/${appointmentId}/steps/${eventId}/confirm`,
    { method: "POST" },
  );
}

export async function completeTask(
  taskId: string,
  back: string,
): Promise<void> {
  if (!UUID.test(taskId) || !back.startsWith("/dashboard")) return;
  await performFormAction(back, `/tasks/${taskId}/complete`, {
    method: "POST",
  });
}

export async function releaseSlot(
  appointmentId: string,
  formData: FormData,
): Promise<void> {
  if (!UUID.test(appointmentId)) return;
  const reason = String(formData.get("reason") ?? "");
  if (!(CANCEL_REASONS as readonly string[]).includes(reason)) return;
  const note = String(formData.get("note") ?? "")
    .trim()
    .slice(0, 1000);
  await performFormAction(
    `/dashboard?appointment=${appointmentId}`,
    `/appointments/${appointmentId}/cancel`,
    { method: "POST", body: { reason, note: note || null } },
  );
}

/**
 * The time is entered in India time (the demo hospitals' timezone). Other timezones need the
 * facility's own offset; see the known issues in PROGRESS.md.
 */
export async function reschedule(
  appointmentId: string,
  formData: FormData,
): Promise<void> {
  if (!UUID.test(appointmentId)) return;
  const local = String(formData.get("scheduled_at") ?? "");
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(local)) return;
  await performFormAction(
    `/dashboard?appointment=${appointmentId}`,
    `/appointments/${appointmentId}/reschedule`,
    { method: "POST", body: { scheduled_at: `${local}:00+05:30` } },
  );
}
