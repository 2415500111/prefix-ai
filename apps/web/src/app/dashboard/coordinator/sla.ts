import type { Sla } from "@prefix/shared";

/** Words first, colour second: an overdue task is never shown by colour alone. */
export const SLA_LABEL: Record<Sla, string> = {
  overdue: "Overdue",
  due_soon: "Due within an hour",
  on_time: "On time",
};

export const SLA_CLASS: Record<Sla, string> = {
  overdue: "bg-red-100 text-red-900 border-red-800",
  due_soon: "bg-amber-100 text-amber-950 border-amber-800",
  on_time: "bg-muted text-foreground border-border",
};
