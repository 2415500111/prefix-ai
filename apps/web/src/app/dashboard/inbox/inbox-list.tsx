import type { EscalationItem } from "@prefix/shared";
import { cn } from "cn";
import { ShieldAlert } from "lucide-react";

import { ActionButton, ActionForm } from "@/components/action-runner";
import { StaggerItem } from "@/components/ui/animated";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RaisedTime } from "@/components/ui/raised-time";
import { Textarea } from "@/components/ui/textarea";
import { describeUrgency, URGENT_EDGE, UrgentPill } from "@/components/urgency";

import { acknowledgeEscalation, resolveEscalation } from "./actions";

const FALLBACK_TIMEZONE = "UTC";

/** Newest first, exactly as the API orders them. Urgent items are marked, never moved. */
export function InboxList({
  items,
  urgentOnly = false,
}: {
  items: EscalationItem[];
  urgentOnly?: boolean;
}) {
  if (items.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed bg-card px-6 py-12 text-center">
        <p className="font-medium">
          {urgentOnly
            ? "Nothing urgent right now."
            : "Nothing needs a person right now."}
        </p>
        <p className="text-sm text-muted-foreground">
          Red flags and questions the prep plan cannot answer arrive here.
        </p>
      </div>
    );
  }

  return (
    <ul className="flex flex-col gap-3" aria-label="Escalations, newest first">
      {items.map((item, index) => (
        <StaggerItem
          key={item.id}
          index={index}
          className={cn(
            "flex flex-col gap-4 rounded-2xl border bg-card p-5 shadow-card",
            item.urgent && URGENT_EDGE,
          )}
        >
          <div className="flex flex-wrap items-center gap-2">
            <ShieldAlert
              className={cn(
                "size-4",
                item.urgent ? "text-urgent" : "text-muted-foreground",
              )}
              aria-hidden
            />
            {item.urgent ? <UrgentPill /> : null}
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
            {item.urgent ? (
              <span className="text-xs font-medium text-urgent-foreground">
                {describeUrgency(item.urgent_reasons)}
              </span>
            ) : null}
            <RaisedTime
              iso={item.created_at}
              timeZone={item.timezone ?? FALLBACK_TIMEZONE}
              className="ml-auto"
            />
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
      ))}
    </ul>
  );
}
