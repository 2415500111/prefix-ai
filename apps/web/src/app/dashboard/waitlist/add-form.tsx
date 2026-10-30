import { ActionForm } from "@/components/action-runner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { listPatients, listProcedureTypes } from "@/lib/server/dal";

import { addEntry } from "./actions";

const SELECT_CLASS =
  "h-10 w-full rounded-lg border border-input bg-card px-3 text-[15px] outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30";

/** Adds a patient to the waitlist. Shown to people who can manage it. */
export async function AddForm() {
  const [patients, procedures] = await Promise.all([
    listPatients(),
    listProcedureTypes(),
  ]);
  return (
    <ActionForm
      action={addEntry}
      label="Add a patient to the waitlist"
      className="grid gap-4 rounded-2xl border bg-card p-5 shadow-card sm:grid-cols-2"
    >
      <div className="grid gap-1.5">
        <Label htmlFor="patient_id">Patient</Label>
        <select
          id="patient_id"
          name="patient_id"
          required
          className={SELECT_CLASS}
        >
          {patients.map((patient) => (
            <option key={patient.id} value={patient.id}>
              {patient.first_name} {patient.last_name}
            </option>
          ))}
        </select>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="procedure_type_id">Procedure</Label>
        <select
          id="procedure_type_id"
          name="procedure_type_id"
          required
          className={SELECT_CLASS}
        >
          {procedures.map((procedure) => (
            <option key={procedure.id} value={procedure.id}>
              {procedure.name}
            </option>
          ))}
        </select>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="earliest_date">Can come in from</Label>
        <Input id="earliest_date" name="earliest_date" type="date" required />
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="latest_date">Until</Label>
        <Input id="latest_date" name="latest_date" type="date" required />
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="priority">Priority (0 to 10)</Label>
        <Input
          id="priority"
          name="priority"
          type="number"
          min={0}
          max={10}
          defaultValue={0}
        />
      </div>
      <div className="flex items-end">
        <Button type="submit">Add to waitlist</Button>
      </div>
    </ActionForm>
  );
}
