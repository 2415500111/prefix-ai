import type { Metadata } from "next";
import { Suspense } from "react";

import { canImportRecords, getCurrentUser } from "@/lib/server/dal";

import { ImportForm } from "./import-form";
import { SkeletonList } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Import" };

async function Board() {
  const user = await getCurrentUser();
  if (!canImportRecords(user.role)) {
    return (
      <p className="text-sm text-muted-foreground">
        Only coordinators and admins can import records.
      </p>
    );
  }
  return <ImportForm />;
}

export default function ImportPage() {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-8 px-4 py-6 sm:px-8 sm:py-8">
      <div>
        <h1 className="text-[28px] leading-tight font-semibold tracking-tight">
          Import records
        </h1>
        <p className="text-sm text-muted-foreground">
          Check a file first. Nothing is saved until every row is valid, and
          each row is checked with the same rules as a record typed in by hand.
        </p>
      </div>

      <Suspense fallback={<SkeletonList label="Loading" rows={3} />}>
        <Board />
      </Suspense>

      <section aria-labelledby="columns-heading" className="grid gap-3 text-sm">
        <h2 id="columns-heading" className="text-lg font-semibold">
          Columns
        </h2>
        <p>
          The first line is the header. Column names are matched to fields
          ignoring case and spaces; any other column is listed as not imported.
        </p>
        <div>
          <p className="font-medium">Patients</p>
          <p className="text-muted-foreground">
            Required: first_name, last_name, date_of_birth (YYYY-MM-DD).
            Optional: phone (with country code, e.g. +919812300001), email, mrn,
            preferred_language, preferred_channel (SMS, WHATSAPP, EMAIL or
            PORTAL), consent_to_message (yes or no), and the condition flags
            on_anticoagulant, diabetic_on_insulin, on_glp1_agonist,
            has_contrast_allergy, has_metal_implant (yes or no), and egfr_value.
          </p>
        </div>
        <div>
          <p className="font-medium">Appointments</p>
          <p className="text-muted-foreground">
            Required: scheduled_at (with its UTC offset, e.g.
            2026-11-02T09:00:00+05:30), facility (the facility name),
            procedure_code, and either patient_mrn or patient_phone to find the
            patient. Optional: arrival_at and duration_minutes.
          </p>
        </div>
      </section>
    </main>
  );
}
