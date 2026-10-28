"use server";

import { performFormAction } from "../form-action";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const BACK = "/dashboard/waitlist";

export async function findBackfill(slotId: string): Promise<void> {
  if (!UUID.test(slotId)) return;
  await performFormAction(BACK, `/waitlist/slots/${slotId}/find-backfill`, {
    method: "POST",
  });
}

export async function acceptOffer(offerId: string): Promise<void> {
  if (!UUID.test(offerId)) return;
  await performFormAction(BACK, `/waitlist/offers/${offerId}/accept`, {
    method: "POST",
  });
}

export async function declineOffer(offerId: string): Promise<void> {
  if (!UUID.test(offerId)) return;
  await performFormAction(BACK, `/waitlist/offers/${offerId}/decline`, {
    method: "POST",
  });
}

export async function removeEntry(entryId: string): Promise<void> {
  if (!UUID.test(entryId)) return;
  await performFormAction(BACK, `/waitlist/${entryId}/remove`, {
    method: "POST",
  });
}

/** The API checks the window, the patient and the procedure; this only checks the shape. */
export async function addEntry(formData: FormData): Promise<void> {
  const patientId = String(formData.get("patient_id") ?? "");
  const procedureTypeId = String(formData.get("procedure_type_id") ?? "");
  const earliestDate = String(formData.get("earliest_date") ?? "");
  const latestDate = String(formData.get("latest_date") ?? "");
  const priority = Math.min(
    10,
    Math.max(0, Math.trunc(Number(formData.get("priority") ?? 0)) || 0),
  );
  if (!UUID.test(patientId) || !UUID.test(procedureTypeId)) return;
  if (!DATE.test(earliestDate) || !DATE.test(latestDate)) return;
  await performFormAction(
    BACK,
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
    `${BACK}?notice=added`,
  );
}
