"use server";

import { type ActionResult, refused } from "../action-result";
import { performAction } from "../form-action";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const LOCAL_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/;
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
const MAX_TEXT = 1000;
const NOT_FOUND = refused("That record no longer exists.");

/**
 * Times are entered in India time (the demo hospitals' timezone). Other timezones need the
 * facility's own offset; see the known issues in PROGRESS.md.
 */
function indiaTime(local: string): string {
  return `${local}:00+05:30`;
}

export async function resendFailed(
  appointmentId: string,
): Promise<ActionResult> {
  if (!UUID.test(appointmentId)) return NOT_FOUND;
  return performAction(
    `/dashboard/appointments/${appointmentId}/resend-failed`,
    { method: "POST" },
    "Failed reminders will be sent again",
  );
}

export async function confirmStep(
  appointmentId: string,
  eventId: string,
): Promise<ActionResult> {
  if (!UUID.test(appointmentId) || !UUID.test(eventId)) return NOT_FOUND;
  return performAction(
    `/appointments/${appointmentId}/steps/${eventId}/confirm`,
    { method: "POST" },
    "Step marked done for the patient",
  );
}

export async function completeTask(taskId: string): Promise<ActionResult> {
  if (!UUID.test(taskId)) return NOT_FOUND;
  return performAction(
    `/tasks/${taskId}/complete`,
    { method: "POST" },
    "Task done",
  );
}

export async function logCall(appointmentId: string): Promise<ActionResult> {
  if (!UUID.test(appointmentId)) return NOT_FOUND;
  return performAction(
    `/appointments/${appointmentId}/calls`,
    { method: "POST" },
    "Call logged",
  );
}

export async function releaseSlot(
  appointmentId: string,
  formData: FormData,
): Promise<ActionResult> {
  if (!UUID.test(appointmentId)) return NOT_FOUND;
  const reason = String(formData.get("reason") ?? "");
  if (!(CANCEL_REASONS as readonly string[]).includes(reason)) {
    return refused("Choose why the procedure is cancelled.");
  }
  const note = String(formData.get("note") ?? "")
    .trim()
    .slice(0, MAX_TEXT);
  return performAction(
    `/appointments/${appointmentId}/cancel`,
    { method: "POST", body: { reason, note: note || null } },
    "Procedure cancelled. The slot is released for the waitlist.",
  );
}

export async function reschedule(
  appointmentId: string,
  formData: FormData,
): Promise<ActionResult> {
  if (!UUID.test(appointmentId)) return NOT_FOUND;
  const local = String(formData.get("scheduled_at") ?? "");
  if (!LOCAL_TIME.test(local)) return refused("Choose the new date and time.");
  return performAction(
    `/appointments/${appointmentId}/reschedule`,
    { method: "POST", body: { scheduled_at: indiaTime(local) } },
    "Procedure moved. The prep plan follows the new time.",
  );
}

export async function messagePatient(
  appointmentId: string,
  formData: FormData,
): Promise<ActionResult> {
  if (!UUID.test(appointmentId)) return NOT_FOUND;
  const body = String(formData.get("body") ?? "")
    .trim()
    .slice(0, MAX_TEXT);
  if (!body) return refused("Write a message first.");
  return performAction(
    `/appointments/${appointmentId}/messages`,
    { method: "POST", body: { body } },
    "Message sent. The patient sees it under Updates.",
  );
}

export async function approveRequest(
  taskId: string,
  formData: FormData,
): Promise<ActionResult> {
  if (!UUID.test(taskId)) return NOT_FOUND;
  const local = String(formData.get("scheduled_at") ?? "");
  if (!LOCAL_TIME.test(local)) return refused("Choose the new date and time.");
  return performAction(
    `/requests/${taskId}/approve`,
    { method: "POST", body: { scheduled_at: indiaTime(local) } },
    "Request approved. The procedure has moved.",
  );
}

export async function declineRequest(taskId: string): Promise<ActionResult> {
  if (!UUID.test(taskId)) return NOT_FOUND;
  return performAction(
    `/requests/${taskId}/decline`,
    { method: "POST" },
    "Request declined. The patient is told to call the hospital.",
  );
}
