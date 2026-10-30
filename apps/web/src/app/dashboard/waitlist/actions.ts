"use server";

import { type ActionResult, refused } from "../action-result";
import { performAction } from "../form-action";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const NOT_FOUND = refused("That record no longer exists.");

export async function findBackfill(slotId: string): Promise<ActionResult> {
  if (!UUID.test(slotId)) return NOT_FOUND;
  return performAction(
    `/waitlist/slots/${slotId}/find-backfill`,
    { method: "POST" },
    "Slot offered to the best-fitting patient",
  );
}

export async function acceptOffer(offerId: string): Promise<ActionResult> {
  if (!UUID.test(offerId)) return NOT_FOUND;
  return performAction(
    `/waitlist/offers/${offerId}/accept`,
    { method: "POST" },
    "Booked into the slot. Their prep plan has started.",
  );
}

export async function declineOffer(offerId: string): Promise<ActionResult> {
  if (!UUID.test(offerId)) return NOT_FOUND;
  return performAction(
    `/waitlist/offers/${offerId}/decline`,
    { method: "POST" },
    "Offer declined. Find backfill offers the next patient.",
  );
}

export async function removeEntry(entryId: string): Promise<ActionResult> {
  if (!UUID.test(entryId)) return NOT_FOUND;
  return performAction(
    `/waitlist/${entryId}/remove`,
    { method: "POST" },
    "Removed from the waitlist",
  );
}

/** The API checks the window, the patient and the procedure; this only checks the shape. */
export async function addEntry(formData: FormData): Promise<ActionResult> {
  const patientId = String(formData.get("patient_id") ?? "");
  const procedureTypeId = String(formData.get("procedure_type_id") ?? "");
  const earliestDate = String(formData.get("earliest_date") ?? "");
  const latestDate = String(formData.get("latest_date") ?? "");
  const priority = Math.min(
    10,
    Math.max(0, Math.trunc(Number(formData.get("priority") ?? 0)) || 0),
  );
  if (!UUID.test(patientId) || !UUID.test(procedureTypeId)) {
    return refused("Choose a patient and a procedure.");
  }
  if (!DATE.test(earliestDate) || !DATE.test(latestDate)) {
    return refused("Choose both dates.");
  }
  return performAction(
    "/waitlist",
    {
      method: "POST",
      body: {
        patient_id: patientId,
        procedure_type_id: procedureTypeId,
        earliest_date: earliestDate,
        latest_date: latestDate,
        priority,
      },
    },
    "Patient added to the waitlist.",
  );
}
