import type { Drawer } from "@prefix/shared";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

import {
  completeTask,
  confirmStep,
  releaseSlot,
  reschedule,
  resendFailed,
} from "./actions";
import { ReadinessBar } from "./upcoming-table";

const REASONS = [
  ["INADEQUATE_BOWEL_PREP", "Bowel prep not finished"],
  ["ATE_OR_DRANK", "Ate or drank too close to the procedure"],
  ["MEDICATION_NOT_STOPPED", "Medicine not stopped in time"],
  ["NO_ESCORT", "No escort home"],
  ["MISSING_LABS", "Required test missing"],
  ["MISSING_PAPERWORK", "Paperwork missing"],
  ["PATIENT_NO_SHOW", "Patient did not come"],
  ["PATIENT_REQUESTED", "Patient asked to cancel"],
  ["CLINICAL_REASON", "Clinical reason"],
  ["FACILITY_OR_STAFF", "Facility or staff reason"],
] as const;

/** Words for each reminder or step state; never colour alone. */
const STEP_WORDS: Record<string, string> = {
  PENDING: "Waiting",
  SENDING: "Sending",
  SENT: "Sent",
  CONFIRMED: "Done",
  MISSED: "Missed",
  SKIPPED: "Not sent",
  CANCELLED: "Cancelled",
  FAILED: "Failed to send",
};

const SEVERITY_WORDS: Record<string, string> = {
  URGENT: "Urgent",
  HIGH: "High",
  NORMAL: "Normal",
};

const TIME = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  hour: "numeric",
  minute: "2-digit",
  timeZone: "Asia/Kolkata",
});

export function PatientDrawer({
  drawer,
  filter,
}: {
  drawer: Drawer;
  filter: string;
}) {
  const { appointment } = drawer;
  const id = appointment.appointment_id;
  const back = `/dashboard?filter=${filter}&appointment=${id}`;
  const hasFailed = drawer.steps.some((step) => step.status === "FAILED");
  const openTasks = drawer.tasks.filter(
    (task) => task.status === "OPEN" || task.status === "IN_PROGRESS",
  );

  return (
    <aside
      aria-labelledby="drawer-title"
      className="flex flex-col gap-5 rounded-xl border bg-card p-5 shadow-sm"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 id="drawer-title" className="text-lg font-semibold">
            {appointment.patient_name}
          </h2>
          <p className="text-sm text-muted-foreground">
            {appointment.procedure_name} ·{" "}
            {TIME.format(new Date(appointment.scheduled_at))}
          </p>
        </div>
        <Link
          href={`/dashboard?filter=${filter}`}
          className="text-sm underline underline-offset-4"
        >
          Close
        </Link>
      </div>

      <div className="flex flex-col gap-1">
        <p className="text-sm font-medium">Readiness</p>
        <ReadinessBar value={appointment.readiness} />
      </div>

      {drawer.escalations.length > 0 ? (
        <section
          aria-labelledby="drawer-escalations"
          className="flex flex-col gap-2"
        >
          <h3 id="drawer-escalations" className="text-sm font-semibold">
            Escalations
          </h3>
          <ul className="flex flex-col gap-2 text-sm">
            {drawer.escalations.map((item) => (
              <li key={item.id} className="rounded-md border p-2">
                <span className="font-medium">
                  {SEVERITY_WORDS[item.severity] ?? item.severity}
                </span>
                {" · "}
                {item.status === "RESOLVED" ? "Resolved" : "Open"}
                <p className="whitespace-pre-line text-muted-foreground">
                  {item.summary}
                </p>
                <Link
                  href="/dashboard/inbox"
                  className="underline underline-offset-4"
                >
                  Go to the nurse inbox
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section aria-labelledby="drawer-steps" className="flex flex-col gap-2">
        <h3 id="drawer-steps" className="text-sm font-semibold">
          Prep steps
        </h3>
        <ul className="flex flex-col gap-2 text-sm">
          {drawer.steps.map((step) => {
            const canConfirm =
              step.requires_confirmation &&
              step.status !== "CONFIRMED" &&
              step.status !== "CANCELLED";
            return (
              <li
                key={step.event_id}
                className="flex flex-col gap-1 rounded-md border p-2"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium">
                    {step.title}
                    {step.is_critical ? " (important)" : ""}
                  </span>
                  <span className="text-muted-foreground">
                    {STEP_WORDS[step.status] ?? step.status}
                  </span>
                </div>
                {step.response ? (
                  <span className="text-muted-foreground">
                    Patient replied: {step.response}
                  </span>
                ) : null}
                {canConfirm ? (
                  <form action={confirmStep.bind(null, id, step.event_id)}>
                    <Button type="submit" variant="outline" size="sm">
                      Mark done for patient
                    </Button>
                  </form>
                ) : null}
              </li>
            );
          })}
        </ul>
      </section>

      {openTasks.length > 0 ? (
        <section aria-labelledby="drawer-tasks" className="flex flex-col gap-2">
          <h3 id="drawer-tasks" className="text-sm font-semibold">
            Open tasks
          </h3>
          <ul className="flex flex-col gap-2 text-sm">
            {openTasks.map((task) => (
              <li
                key={task.id}
                className="flex flex-wrap items-center justify-between gap-2"
              >
                <span>{task.title}</span>
                <form action={completeTask.bind(null, task.id, back)}>
                  <Button type="submit" variant="outline" size="sm">
                    Log done
                  </Button>
                </form>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {drawer.messages.length > 0 ? (
        <section
          aria-labelledby="drawer-messages"
          className="flex flex-col gap-2"
        >
          <h3 id="drawer-messages" className="text-sm font-semibold">
            Recent messages
          </h3>
          <ul className="flex flex-col gap-2 text-sm">
            {drawer.messages.map((message) => (
              <li key={message.id} className="rounded-md border p-2">
                <span className="text-muted-foreground">
                  {message.direction === "INBOUND"
                    ? "From patient"
                    : "To patient"}{" "}
                  · {message.status}
                </span>
                <p className="whitespace-pre-line">{message.body}</p>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section
        aria-labelledby="drawer-actions"
        className="flex flex-col gap-4 border-t pt-4"
      >
        <h3 id="drawer-actions" className="text-sm font-semibold">
          Actions
        </h3>
        {hasFailed ? (
          <form action={resendFailed.bind(null, id)}>
            <Button type="submit" variant="outline">
              Resend failed reminders
            </Button>
          </form>
        ) : null}

        <form
          action={reschedule.bind(null, id)}
          className="flex flex-col gap-2"
        >
          <Label htmlFor={`resched-${id}`}>New time (India time)</Label>
          <Input
            id={`resched-${id}`}
            name="scheduled_at"
            type="datetime-local"
            required
          />
          <Button type="submit" variant="outline">
            Reschedule
          </Button>
        </form>

        <form
          action={releaseSlot.bind(null, id)}
          className="flex flex-col gap-2"
        >
          <Label htmlFor={`reason-${id}`}>Release the slot: reason</Label>
          <select
            id={`reason-${id}`}
            name="reason"
            required
            defaultValue=""
            className="h-9 rounded-md border bg-background px-2 text-sm"
          >
            <option value="" disabled>
              Choose a reason
            </option>
            {REASONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <Label htmlFor={`note-${id}`}>Note (optional)</Label>
          <Textarea id={`note-${id}`} name="note" maxLength={1000} rows={2} />
          <Button type="submit" variant="destructive">
            Release slot
          </Button>
        </form>
      </section>
    </aside>
  );
}
