import type { UpcomingRow } from "@prefix/shared";
import { cn } from "cn";
import {
  CalendarClock,
  CircleCheck,
  HeartPulse,
  ShieldAlert,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { AnimatedNumber, StaggerItem } from "@/components/ui/animated";

export interface Summary {
  procedures: number;
  highRisk: number;
  openEscalations: number;
  readyPercent: number;
}

/** The four numbers a coordinator checks first thing. */
export function summarize(
  rows: UpcomingRow[],
  openEscalations: number,
): Summary {
  const ready = rows.filter((row) => row.readiness >= 100).length;
  return {
    procedures: rows.length,
    highRisk: rows.filter((row) => row.risk_level === "HIGH").length,
    openEscalations,
    readyPercent:
      rows.length === 0 ? 100 : Math.round((100 * ready) / rows.length),
  };
}

const ICON_TONE = {
  primary: "bg-primary-soft text-primary-soft-foreground",
  urgent: "bg-urgent-soft text-urgent-foreground",
  ready: "bg-ready-soft text-ready-foreground",
  attention: "bg-attention-soft text-attention-foreground",
} as const;

function Card({
  index,
  label,
  value,
  suffix,
  detail,
  icon: Icon,
  tone,
}: {
  index: number;
  label: string;
  value: number;
  suffix?: string;
  detail: string;
  icon: LucideIcon;
  tone: keyof typeof ICON_TONE;
}) {
  return (
    <StaggerItem
      index={index}
      as="div"
      className="flex flex-col gap-3 rounded-2xl border bg-card p-4 shadow-card sm:p-5"
    >
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">{label}</p>
        <span
          className={cn(
            "grid size-8 place-items-center rounded-full",
            ICON_TONE[tone],
          )}
        >
          <Icon className="size-4" aria-hidden />
        </span>
      </div>
      <p className="text-3xl font-semibold tracking-tight">
        <AnimatedNumber value={value} suffix={suffix} />
      </p>
      <p className="text-xs text-muted-foreground">{detail}</p>
    </StaggerItem>
  );
}

export function SummaryCards({ summary }: { summary: Summary }) {
  return (
    <section
      aria-label="Summary"
      className="grid grid-cols-2 gap-3 lg:grid-cols-4"
    >
      <Card
        index={0}
        label="Procedures, next 72 hours"
        value={summary.procedures}
        detail="Booked and not cancelled"
        icon={CalendarClock}
        tone="primary"
      />
      <Card
        index={1}
        label="High risk"
        value={summary.highRisk}
        detail="Likely to be cancelled on the day"
        icon={HeartPulse}
        tone={summary.highRisk > 0 ? "urgent" : "ready"}
      />
      <Card
        index={2}
        label="Open escalations"
        value={summary.openEscalations}
        detail="Waiting for a nurse"
        icon={ShieldAlert}
        tone={summary.openEscalations > 0 ? "attention" : "ready"}
      />
      <Card
        index={3}
        label="Ready"
        value={summary.readyPercent}
        suffix="%"
        detail="Every step confirmed"
        icon={CircleCheck}
        tone="ready"
      />
    </section>
  );
}
