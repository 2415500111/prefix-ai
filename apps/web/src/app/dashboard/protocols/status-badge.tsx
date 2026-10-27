import type { ProtocolStatus } from "@prefix/shared";

import { Badge } from "@/components/ui/badge";

const VARIANT: Record<ProtocolStatus, "default" | "secondary" | "outline"> = {
  APPROVED: "default",
  DRAFT: "secondary",
  RETIRED: "outline",
};

export function StatusBadge({ status }: { status: ProtocolStatus }) {
  return <Badge variant={VARIANT[status]}>{status.toLowerCase()}</Badge>;
}

export function SampleBadge() {
  return (
    <Badge
      variant="outline"
      className="border-amber-500 text-amber-700 dark:text-amber-400"
    >
      sample
    </Badge>
  );
}
