import type { EscalationItem, EscalationSeverity } from "@prefix/shared";
import { ShieldAlert } from "lucide-react";

import { ActionButton, ActionForm } from "@/components/action-runner";
import { StaggerItem } from "@/components/ui/animated";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

import { acknowledgeEscalation, resolveEscalation } from "./actions";

/** Words as well as colour: a severity is never shown by colour alone. */
const SEVERITY: Record<
  EscalationSeverity,
  { label: string; tone: "urgent" | "attention" | "neutral" }
> = {
  URGENT: { label: "Urgent", tone: "urgent" },
  HIGH: { label: "High", tone: "attention" },
  NORMAL: { label: "Normal", tone: "neutral" },
};

const WHEN = new Intl.DateTimeFormat("en-IN", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Asia/Kolkata",
});

export function InboxList({ items }: { items: EscalationItem[] }) {
  if (items.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed bg-card px-6 py-12 text-center">
        <p className="font-medium">Nothing needs a person right now.</p>
        <p className="text-sm text-muted-foreground">
          Red flags and questions the prep plan cannot answer arrive here.
        </p>
      </div>
    );
  }

  return (
    <ul className="flex flex-col gap-3">
      {items.map((item, index) => {
        const severity = SEVERITY[item.severity];
        return (
          <StaggerItem
            key={item.id}
            index={index}
            className="flex flex-col gap-4 rounded-2xl border bg-card p-5 shadow-card"
          >
            <div className="flex flex-wrap items-center gap-2">
              <ShieldAlert
                className={
                  item.severity === "NORMAL"
                    ? "size-4 text-muted-foreground"
                    : "size-4 text-urgent"
                }
                aria-hidden
              />
              <Badge variant={severity.tone}>{severity.label}</Badge>
              <Badge
                variant={
                  item.status === "RESOLVED"
                    ? "ready"
                    : item.status === "ACKNOWLEDGED"
                      ? "info"
                      : "neutral"
                }
              >
                {item.status === "OPEN"
                  ? "Waiting"
                  : item.status === "ACKNOWLEDGED"
                    ? "In hand"
                    : "Resolved"}
              </Badge>
              <time
                dateTime={item.created_at}
                className="ml-auto text-xs text-muted-foreground"
              >
                {WHEN.format(new Date(item.created_at))}
              </time>
            </div>
            <h2 className="text-lg font-semibold tracking-tight">
              {item.patient_name}
              {item.procedure_name ? " " : null}
              {item.procedure_name ? (
                <span className="font-normal text-muted-foreground">
                  · {item.procedure_name}
                </span>
              ) : null}
            </h2>
            <p className="text-sm whitespace-pre-line">{item.summary}</p>

            {item.status !== "RESOLVED" ? (
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
                {item.status === "OPEN" ? (
                  <ActionButton
                    variant="outline"
                    action={acknowledgeEscalation.bind(null, item.id)}
                  >
                    I have this
                  </ActionButton>
                ) : null}
                <ActionForm
                  action={resolveEscalation.bind(null, item.id)}
                  className="flex flex-1 flex-col gap-2"
                  label={`Resolve the escalation for ${item.patient_name}`}
                >
                  <label
                    htmlFor={`note-${item.id}`}
                    className="text-sm font-medium"
                  >
                    What did you do?
                  </label>
                  <Textarea
                    id={`note-${item.id}`}
                    name="note"
                    required
                    maxLength={1000}
                    rows={2}
                  />
                  <div>
                    <Button type="submit">Mark resolved</Button>
                  </div>
                </ActionForm>
              </div>
            ) : (
              <p className="text-sm">
                <span className="font-medium">Resolution: </span>
                {item.resolution_note}
              </p>
            )}
          </StaggerItem>
        );
      })}
    </ul>
  );
}
