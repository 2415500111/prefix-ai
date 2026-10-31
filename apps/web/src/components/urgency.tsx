import type { UrgentReason } from "@prefix/shared";
import { Siren } from "lucide-react";

import { Badge } from "@/components/ui/badge";

/**
 * How staff lists show urgency. The API decides it from fixed rules (a red flag, a problem with
 * a critical step, a procedure within 24 hours); lists stay newest first either way.
 */
export const URGENT_REASON: Record<UrgentReason, string> = {
  red_flag: "Red flag",
  critical_step: "Critical step",
  procedure_soon: "Procedure within 24 h",
};

export function describeUrgency(reasons: UrgentReason[]): string {
  return reasons.map((reason) => URGENT_REASON[reason]).join(" · ");
}

/** The red left edge of an urgent card. Normal cards keep their neutral border. */
export const URGENT_EDGE = "border-l-4 border-l-urgent";

/** Words as well as colour: an urgent item always says so. */
export function UrgentPill() {
  return (
    <Badge variant="urgent">
      <Siren aria-hidden />
      Urgent
    </Badge>
  );
}
