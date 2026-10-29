import type { Sla } from "@prefix/shared";

/** Words first, colour second: an overdue task is never shown by colour alone. */
export const SLA_LABEL: Record<Sla, string> = {
  overdue: "Overdue",
  due_soon: "Due within an hour",
  on_time: "On time",
};

/** The status colour for each SLA state (docs/DESIGN.md). */
export const SLA_TONE: Record<Sla, "urgent" | "attention" | "neutral"> = {
  overdue: "urgent",
  due_soon: "attention",
  on_time: "neutral",
};
