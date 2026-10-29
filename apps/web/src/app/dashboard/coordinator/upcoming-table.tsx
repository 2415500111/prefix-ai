import type { UpcomingRow } from "@prefix/shared";
import { cn } from "cn";
import { ChevronRight, ListChecks, ShieldAlert } from "lucide-react";
import Link from "next/link";

import { ProgressBar, StaggerItem } from "@/components/ui/animated";
import { Badge } from "@/components/ui/badge";

export type Filter = "all" | "attention" | "high";

export const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "attention", label: "Needs attention" },
  { value: "high", label: "High risk" },
];

/** Rows that need a coordinator's attention: an open escalation, a reported problem, or
 * steps still not confirmed. High risk is the risk score's own HIGH level. */
export function filterRows(rows: UpcomingRow[], filter: Filter): UpcomingRow[] {
  if (filter === "all") return rows;
  if (filter === "high") return rows.filter((row) => row.risk_level === "HIGH");
  return rows.filter(
    (row) =>
      row.open_escalations > 0 || row.problem_steps > 0 || row.readiness < 100,
  );
}

/** Words and colours for the risk level, the same everywhere. */
export const RISK: Record<
  UpcomingRow["risk_level"],
  { label: string; tone: "urgent" | "attention" | "ready" }
> = {
  HIGH: { label: "High risk", tone: "urgent" },
  MEDIUM: { label: "Medium risk", tone: "attention" },
  LOW: { label: "Low risk", tone: "ready" },
};

export function RiskPill({
  level,
  score,
}: {
  level: UpcomingRow["risk_level"];
  score: number;
}) {
  const risk = RISK[level];
  return (
    <Badge variant={risk.tone}>
      <span aria-hidden className="size-1.5 rounded-full bg-current" />
      {risk.label}
      <span className="font-normal opacity-80">{score}</span>
    </Badge>
  );
}

const TIME = new Intl.DateTimeFormat("en-IN", {
  weekday: "short",
  day: "numeric",
  month: "short",
  hour: "numeric",
  minute: "2-digit",
  timeZone: "Asia/Kolkata",
});

export function readinessTone(value: number): "ready" | "attention" | "urgent" {
  if (value >= 100) return "ready";
  return value >= 50 ? "attention" : "urgent";
}

export function ReadinessBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2">
      <ProgressBar
        value={value}
        label="Readiness"
        tone={readinessTone(value)}
        className="w-24"
      />
      <span className="w-9 text-sm tabular-nums">{value}%</span>
    </div>
  );
}

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
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
  if (rows.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed bg-card px-6 py-12 text-center">
        <p className="font-medium">
          {filter === "all"
            ? "No procedures in the next 72 hours."
            : "Nothing needs attention right now."}
        </p>
        <p className="text-sm text-muted-foreground">
          New bookings appear here automatically.
        </p>
      </div>
    );
  }

  return (
    <ul className="flex flex-col gap-2" aria-label="Procedures">
      {rows.map((row, index) => {
        const selected = row.appointment_id === selectedId;
        return (
          <StaggerItem key={row.appointment_id} index={index}>
            <div
              className={cn(
                "group relative flex flex-wrap items-center gap-x-5 gap-y-3 rounded-2xl border bg-card px-4 py-3.5 shadow-card transition-shadow hover:shadow-raised",
                selected && "ring-2 ring-primary",
              )}
            >
              <time
                dateTime={row.scheduled_at}
                className="w-28 shrink-0 text-sm text-muted-foreground"
              >
                {TIME.format(new Date(row.scheduled_at))}
              </time>
              <div className="min-w-40 flex-1">
                <Link
                  href={`/dashboard?filter=${filter}&appointment=${row.appointment_id}`}
                  scroll={false}
                  className="font-semibold outline-none after:absolute after:inset-0 after:rounded-2xl focus-visible:after:ring-3 focus-visible:after:ring-ring/40"
                >
                  <span className="sr-only">Open</span> {row.patient_name}
                </Link>
                <p className="text-sm text-muted-foreground">
                  {row.procedure_name}
                </p>
              </div>
              <ReadinessBar value={row.readiness} />
              <div className="flex w-64 flex-col gap-1">
                <RiskPill level={row.risk_level} score={row.risk_score} />
                {row.risk_reasons.length > 0 ? (
                  <p className="line-clamp-1 text-xs text-muted-foreground">
                    {row.risk_reasons.slice(0, 2).join(" · ")}
                  </p>
                ) : null}
              </div>
              <div className="flex w-36 flex-wrap gap-1.5">
                {row.open_escalations > 0 ? (
                  <Badge variant="urgent">
                    <ShieldAlert aria-hidden />
                    {plural(row.open_escalations, "escalation", "escalations")}
                  </Badge>
                ) : null}
                {row.open_tasks > 0 ? (
                  <Badge variant="neutral">
                    <ListChecks aria-hidden />
                    {plural(row.open_tasks, "task", "tasks")}
                  </Badge>
                ) : null}
                {row.open_escalations === 0 && row.open_tasks === 0 ? (
                  <span className="text-xs text-muted-foreground">
                    Nothing open
                  </span>
                ) : null}
              </div>
              <ChevronRight
                className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                aria-hidden
              />
            </div>
          </StaggerItem>
        );
      })}
    </ul>
  );
}
