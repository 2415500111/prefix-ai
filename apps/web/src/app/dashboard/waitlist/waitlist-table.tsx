import type { WaitlistEntry } from "@prefix/shared";

import { Button } from "@/components/ui/button";

import { removeEntry } from "./actions";

const DAY = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  timeZone: "UTC",
});

function day(iso: string): string {
  return DAY.format(new Date(`${iso}T00:00:00Z`));
}

/** Patients waiting for a procedure, highest priority first. */
export function WaitlistTable({
  entries,
  canManage,
}: {
  entries: WaitlistEntry[];
  canManage: boolean;
}) {
  if (entries.length === 0) {
    return <p className="text-sm text-muted-foreground">Nobody is waiting.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[36rem] text-left text-sm">
        <thead className="text-muted-foreground">
          <tr>
            <th scope="col" className="py-2 pr-3 font-medium">
              Patient
            </th>
            <th scope="col" className="py-2 pr-3 font-medium">
              Procedure
            </th>
            <th scope="col" className="py-2 pr-3 font-medium">
              Can come in
            </th>
            <th scope="col" className="py-2 pr-3 font-medium">
              Priority
            </th>
            <th scope="col" className="py-2 font-medium">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={entry.id} className="border-t">
              <td className="py-2 pr-3">{entry.patient_name}</td>
              <td className="py-2 pr-3">{entry.procedure_name}</td>
              <td className="py-2 pr-3">
                {day(entry.earliest_date)} to {day(entry.latest_date)}
              </td>
              <td className="py-2 pr-3">{entry.priority}</td>
              <td className="py-2">
                {canManage ? (
                  <form action={removeEntry.bind(null, entry.id)}>
                    <Button type="submit" variant="outline" size="sm">
                      Remove
                    </Button>
                  </form>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
