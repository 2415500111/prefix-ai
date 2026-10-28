import type { UpcomingRow } from "@prefix/shared";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

export type Filter = "all" | "attention";

/** Rows that need a coordinator's attention: an open escalation, a reported problem, or
 * steps still not confirmed. */
export function filterRows(rows: UpcomingRow[], filter: Filter): UpcomingRow[] {
  if (filter === "all") return rows;
  return rows.filter(
    (row) =>
      row.open_escalations > 0 || row.problem_steps > 0 || row.readiness < 100,
  );
}

/** Words for the risk level; the reasons are shown next to them. */
const RISK_WORDS: Record<UpcomingRow["risk_level"], string> = {
  LOW: "Low risk",
  MEDIUM: "Medium risk",
  HIGH: "High risk",
};

const TIME = new Intl.DateTimeFormat("en-IN", {
  weekday: "short",
  day: "numeric",
  month: "short",
  hour: "numeric",
  minute: "2-digit",
  timeZone: "Asia/Kolkata",
});

export function ReadinessBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2">
      <div
        role="progressbar"
        aria-label="Readiness"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value}
        className="h-2 w-24 overflow-hidden rounded-full bg-muted"
      >
        <div
          className="h-full rounded-full bg-emerald-700"
          style={{ width: `${value}%` }}
        />
      </div>
      <span className="text-sm tabular-nums">{value}%</span>
    </div>
  );
}

export function UpcomingTable({
  rows,
  filter,
  selectedId,
}: {
  rows: UpcomingRow[];
  filter: Filter;
  selectedId?: string;
}) {
  return (
    <section aria-labelledby="upcoming-title" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="upcoming-title" className="text-lg font-semibold">
          Next 72 hours
        </h2>
        <nav aria-label="Filter procedures" className="flex gap-2 text-sm">
          <Link
            href="/dashboard?filter=all"
            aria-current={filter === "all" ? "page" : undefined}
            className="rounded-md border px-3 py-1 aria-[current=page]:bg-primary aria-[current=page]:text-primary-foreground"
          >
            All
          </Link>
          <Link
            href="/dashboard?filter=attention"
            aria-current={filter === "attention" ? "page" : undefined}
            className="rounded-md border px-3 py-1 aria-[current=page]:bg-primary aria-[current=page]:text-primary-foreground"
          >
            Needs attention
          </Link>
        </nav>
      </div>

      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {filter === "attention"
            ? "Nobody needs attention right now."
            : "No procedures in the next 72 hours."}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] text-left text-sm">
            <thead className="text-muted-foreground">
              <tr>
                <th scope="col" className="py-2 pr-3 font-medium">
                  When
                </th>
                <th scope="col" className="py-2 pr-3 font-medium">
                  Patient
                </th>
                <th scope="col" className="py-2 pr-3 font-medium">
                  Procedure
                </th>
                <th scope="col" className="py-2 pr-3 font-medium">
                  Readiness
                </th>
                <th scope="col" className="py-2 pr-3 font-medium">
                  Risk
                </th>
                <th scope="col" className="py-2 pr-3 font-medium">
                  Open
                </th>
                <th scope="col" className="py-2 font-medium">
                  <span className="sr-only">Details</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.appointment_id}
                  className={`border-t ${row.appointment_id === selectedId ? "bg-muted/60" : ""}`}
                >
                  <td className="py-2 pr-3">
                    <time dateTime={row.scheduled_at}>
                      {TIME.format(new Date(row.scheduled_at))}
                    </time>
                  </td>
                  <td className="py-2 pr-3">{row.patient_name}</td>
                  <td className="py-2 pr-3">{row.procedure_name}</td>
                  <td className="py-2 pr-3">
                    <ReadinessBar value={row.readiness} />
                  </td>
                  <td className="py-2 pr-3">
                    <span className="font-medium">
                      {RISK_WORDS[row.risk_level]}
                    </span>
                    <span className="ml-2 text-muted-foreground">
                      {row.risk_score}
                    </span>
                    {row.risk_reasons.length > 0 ? (
                      <span className="block text-xs text-muted-foreground">
                        {row.risk_reasons.slice(0, 2).join(" · ")}
                      </span>
                    ) : null}
                  </td>
                  <td className="py-2 pr-3">
                    {row.open_escalations > 0 ? (
                      <span className="mr-2 rounded-full border border-red-800 px-2 py-0.5 text-red-900">
                        {row.open_escalations} escalation
                        {row.open_escalations === 1 ? "" : "s"}
                      </span>
                    ) : null}
                    {row.open_tasks > 0
                      ? `${row.open_tasks} task${row.open_tasks === 1 ? "" : "s"}`
                      : null}
                    {row.open_escalations === 0 && row.open_tasks === 0
                      ? "None"
                      : null}
                  </td>
                  <td className="py-2">
                    <Link
                      href={`/dashboard?filter=${filter}&appointment=${row.appointment_id}`}
                      aria-label={`Open ${row.patient_name}`}
                      className={buttonVariants({
                        variant:
                          row.appointment_id === selectedId
                            ? "secondary"
                            : "outline",
                        size: "sm",
                      })}
                    >
                      Open
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
