import type { EscalationItem, EscalationSeverity } from "@prefix/shared";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

import { acknowledgeEscalation, resolveEscalation } from "./actions";

/** Words as well as colour: a severity is never shown by colour alone. */
const SEVERITY_LABEL: Record<EscalationSeverity, string> = {
  URGENT: "Urgent",
  HIGH: "High",
  NORMAL: "Normal",
};

const SEVERITY_CLASS: Record<EscalationSeverity, string> = {
  URGENT: "bg-red-100 text-red-900 border-red-800",
  HIGH: "bg-amber-100 text-amber-950 border-amber-800",
  NORMAL: "bg-muted text-foreground border-border",
};

function when(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function InboxList({ items }: { items: EscalationItem[] }) {
  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Nothing needs a person right now.
      </p>
    );
  }

  return (
    <ul className="flex flex-col gap-4">
      {items.map((item) => (
        <li key={item.id}>
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded-full border px-2.5 py-0.5 text-sm font-medium ${SEVERITY_CLASS[item.severity]}`}
                >
                  {SEVERITY_LABEL[item.severity]}
                </span>
                <span className="text-sm text-muted-foreground">
                  {item.status === "OPEN"
                    ? "Waiting"
                    : item.status === "ACKNOWLEDGED"
                      ? "In hand"
                      : "Resolved"}
                </span>
              </div>
              <CardTitle className="text-lg">
                {item.patient_name}
                {item.procedure_name ? ` · ${item.procedure_name}` : ""}
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                <time dateTime={item.created_at}>{when(item.created_at)}</time>
              </p>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <p className="text-sm whitespace-pre-line">{item.summary}</p>

              {item.status !== "RESOLVED" ? (
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
                  {item.status === "OPEN" ? (
                    <form action={acknowledgeEscalation.bind(null, item.id)}>
                      <Button type="submit" variant="outline">
                        I have this
                      </Button>
                    </form>
                  ) : null}
                  <form
                    action={resolveEscalation.bind(null, item.id)}
                    className="flex flex-1 flex-col gap-2"
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
                  </form>
                </div>
              ) : (
                <p className="text-sm">
                  <span className="font-medium">Resolution: </span>
                  {item.resolution_note}
                </p>
              )}
            </CardContent>
          </Card>
        </li>
      ))}
    </ul>
  );
}
