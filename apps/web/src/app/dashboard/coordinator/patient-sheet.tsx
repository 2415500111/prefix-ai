"use client";

import type { Drawer, DrawerStep, DrawerTask, Role } from "@prefix/shared";
import { cn } from "cn";
import {
  CalendarClock,
  CalendarX,
  CircleCheck,
  Clock,
  ListChecks,
  MessageSquare,
  Phone,
  RotateCcw,
  Send,
  ShieldAlert,
  TriangleAlert,
  UserCheck,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { type ReactNode, useState } from "react";

import { ActionButton, ActionForm } from "@/components/action-runner";
import { ProgressRing, StaggerItem } from "@/components/ui/animated";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Sheet } from "@/components/ui/sheet";
import { Tabs } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";

import {
  approveRequest,
  confirmStep,
  declineRequest,
  logCall,
  messagePatient,
  releaseSlot,
  reschedule,
  resendFailed,
} from "./actions";
import { RescheduleFields } from "./reschedule-fields";
import type { SheetTab } from "./sheet-tabs";
import { type Filter, readinessTone, RiskPill } from "./upcoming-table";

const TIME = new Intl.DateTimeFormat("en-IN", {
  weekday: "short",
  day: "numeric",
  month: "short",
  hour: "numeric",
  minute: "2-digit",
  timeZone: "Asia/Kolkata",
});

function when(iso: string): string {
  return TIME.format(new Date(iso));
}

export const CANCEL_REASONS = [
  ["INADEQUATE_BOWEL_PREP", "Bowel prep not good enough"],
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

const DONE_STATES = new Set(["CONFIRMED", "SKIPPED", "CANCELLED"]);
const PROBLEM_RESPONSES = new Set(["NO", "HELP"]);
const OPEN_TASK = new Set(["OPEN", "IN_PROGRESS"]);

/** What a person in this role may do. The API checks again; this only hides dead buttons. */
export function permissionsFor(role: Role) {
  const canChange = role === "ADMIN" || role === "COORDINATOR";
  return {
    canChange,
    canComplete: canChange || role === "NURSE" || role === "DEMO_VIEWER",
    canMessage: canChange || role === "NURSE",
  };
}

export function stepState(step: DrawerStep): {
  label: string;
  tone: "ready" | "urgent" | "attention" | "neutral";
} {
  if (step.response && PROBLEM_RESPONSES.has(step.response)) {
    return { label: "Problem reported", tone: "urgent" };
  }
  if (step.status === "CONFIRMED") return { label: "Done", tone: "ready" };
  if (step.status === "MISSED") return { label: "Missed", tone: "urgent" };
  if (step.status === "SKIPPED")
    return { label: "Not needed", tone: "neutral" };
  // The same state the patient sees: a step past its time is due, even without a reminder.
  if (step.state === "OVERDUE") return { label: "Overdue", tone: "attention" };
  if (step.state === "DUE") return { label: "Due now", tone: "attention" };
  if (step.state === "ACTIVE") return { label: "In effect", tone: "neutral" };
  if (step.status === "SENT")
    return { label: "Sent, waiting", tone: "attention" };
  return { label: "Coming up", tone: "neutral" };
}

export function escortStep(steps: DrawerStep[]): DrawerStep | undefined {
  return steps.find(
    (step) =>
      step.category === "LOGISTICS" &&
      step.requires_confirmation &&
      /escort/i.test(step.title) &&
      step.status !== "CONFIRMED",
  );
}

export function requestState(
  task: DrawerTask,
): "pending" | "approved" | "declined" {
  if (OPEN_TASK.has(task.status)) return "pending";
  return task.status === "DONE" ? "approved" : "declined";
}

export interface ActivityEntry {
  at: string;
  text: string;
  tone: "ready" | "urgent" | "attention" | "info" | "neutral";
}

/** One feed of what happened, newest first, from the records the sheet already has. */
export function buildActivity(drawer: Drawer): ActivityEntry[] {
  const entries: ActivityEntry[] = [];
  for (const message of drawer.messages) {
    if (message.direction === "INBOUND") {
      entries.push({
        at: message.created_at,
        text: "Patient replied",
        tone: "info",
      });
    } else if (message.provider === "care_team") {
      entries.push({
        at: message.created_at,
        text: "Care team message sent",
        tone: "info",
      });
    } else if (message.status === "FAILED") {
      entries.push({
        at: message.created_at,
        text: "Reminder failed to send",
        tone: "urgent",
      });
    } else {
      entries.push({
        at: message.created_at,
        text: "Reminder sent",
        tone: "neutral",
      });
    }
  }
  for (const step of drawer.steps) {
    if (step.confirmed_at) {
      entries.push({
        at: step.confirmed_at,
        text: `Step done: ${step.title}`,
        tone: "ready",
      });
    }
  }
  for (const escalation of drawer.escalations) {
    entries.push({
      at: escalation.created_at,
      text: `Escalation opened (${escalation.severity.toLowerCase()})`,
      tone: "urgent",
    });
  }
  for (const task of drawer.tasks) {
    const isRequest = task.type === "RESCHEDULE";
    const isCallLog =
      task.type === "CALL_PATIENT" && task.title.endsWith("logged");
    if (task.created_at && !isCallLog) {
      entries.push({
        at: task.created_at,
        text: isRequest
          ? "Patient asked to reschedule"
          : `Task opened: ${task.title}`,
        tone: "attention",
      });
    }
    if (task.completed_at) {
      let text = `Task done: ${task.title}`;
      if (isCallLog) text = "Call with the patient logged";
      else if (isRequest) {
        text =
          requestState(task) === "approved"
            ? "Reschedule approved"
            : "Reschedule declined";
      }
      entries.push({ at: task.completed_at, text, tone: "ready" });
    }
  }
  return entries.sort((a, b) => b.at.localeCompare(a.at));
}

const DOT = {
  ready: "bg-ready",
  urgent: "bg-urgent",
  attention: "bg-attention",
  info: "bg-primary",
  neutral: "bg-muted-foreground/40",
} as const;

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold text-muted-foreground">{title}</h3>
      {children}
    </section>
  );
}

function OverviewTab({ drawer }: { drawer: Drawer }) {
  const row = drawer.appointment;
  const next = drawer.steps.find(
    (step) => step.requires_confirmation && !DONE_STATES.has(step.status),
  );
  const openEscalations = drawer.escalations.filter(
    (item) => item.status !== "RESOLVED",
  );
  const openTasks = drawer.tasks.filter(
    (task) => OPEN_TASK.has(task.status) && task.type !== "RESCHEDULE",
  );
  return (
    <div className="flex flex-col gap-6 p-5">
      <div className="flex items-center gap-5">
        <ProgressRing
          value={row.readiness}
          label="Readiness"
          tone={readinessTone(row.readiness)}
          size={96}
        >
          <span className="text-xl font-semibold tabular-nums">
            {row.readiness}%
          </span>
        </ProgressRing>
        <div className="flex flex-col gap-1.5">
          <p className="text-sm text-muted-foreground">
            {row.confirmed_steps} of {row.required_steps} steps confirmed
          </p>
          <RiskPill level={row.risk_level} score={row.risk_score} />
          {row.risk_reasons.length > 0 ? (
            <ul className="list-disc pl-4 text-sm text-muted-foreground">
              {row.risk_reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>

      <Section title="Next step to confirm">
        {next ? (
          <div className="flex items-start gap-3 rounded-xl border bg-primary-soft/40 p-3">
            <Clock className="mt-0.5 size-4 text-primary" aria-hidden />
            <div className="flex-1">
              <p className="font-medium">{next.title}</p>
              <p className="text-sm text-muted-foreground">
                Due {when(next.due_at)}
              </p>
            </div>
            <Badge variant={stepState(next).tone}>
              {stepState(next).label}
            </Badge>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            Every step that needs confirming is done.
          </p>
        )}
      </Section>

      <Section title="Escalations">
        {openEscalations.length > 0 ? (
          <ul className="flex flex-col gap-2">
            {openEscalations.map((item) => (
              <li key={item.id} className="rounded-xl border p-3">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="size-4 text-urgent" aria-hidden />
                  <Badge
                    variant={
                      item.severity === "NORMAL" ? "attention" : "urgent"
                    }
                  >
                    {item.severity.toLowerCase()}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {when(item.created_at)}
                  </span>
                </div>
                <p className="mt-1 text-sm">{item.summary}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">None open.</p>
        )}
      </Section>

      <Section title="Open tasks">
        {openTasks.length > 0 ? (
          <ul className="flex flex-col gap-1.5">
            {openTasks.map((task) => (
              <li key={task.id} className="flex items-center gap-2 text-sm">
                <ListChecks
                  className="size-4 text-muted-foreground"
                  aria-hidden
                />
                {task.title}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">None open.</p>
        )}
      </Section>
    </div>
  );
}

function TimelineTab({
  drawer,
  canComplete,
}: {
  drawer: Drawer;
  canComplete: boolean;
}) {
  const id = drawer.appointment.appointment_id;
  return (
    <ol className="flex flex-col p-5" aria-label="Prep steps">
      {drawer.steps.map((step, index) => {
        const state = stepState(step);
        const last = index === drawer.steps.length - 1;
        return (
          <StaggerItem
            key={step.event_id}
            index={index}
            className="relative flex gap-3 pb-5"
          >
            {!last ? (
              <span
                aria-hidden
                className="absolute top-4 left-[7px] h-full w-px bg-border"
              />
            ) : null}
            <span
              aria-hidden
              className={cn(
                "relative mt-1.5 size-3.5 shrink-0 rounded-full ring-4 ring-card",
                DOT[state.tone],
              )}
            />
            <div className="flex flex-1 flex-col gap-1.5">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-medium">{step.title}</p>
                {step.is_critical ? (
                  <Badge variant="urgent">Important</Badge>
                ) : null}
              </div>
              <p className="text-sm text-muted-foreground">
                Due {when(step.due_at)}
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={state.tone}>{state.label}</Badge>
                {canComplete &&
                step.requires_confirmation &&
                step.status !== "CONFIRMED" ? (
                  <ActionButton
                    variant="outline"
                    size="sm"
                    action={() => confirmStep(id, step.event_id)}
                  >
                    <CircleCheck aria-hidden />
                    Mark done for patient
                  </ActionButton>
                ) : null}
              </div>
            </div>
          </StaggerItem>
        );
      })}
    </ol>
  );
}

function MessagesTab({
  drawer,
  canMessage,
}: {
  drawer: Drawer;
  canMessage: boolean;
}) {
  const id = drawer.appointment.appointment_id;
  const failed = drawer.messages.some((message) => message.status === "FAILED");
  return (
    <div className="flex flex-col gap-4 p-5">
      {failed ? (
        <div className="flex items-center gap-3 rounded-xl bg-urgent-soft p-3 text-sm text-urgent-foreground">
          <TriangleAlert className="size-4" aria-hidden />
          <span className="flex-1">A reminder failed to send.</span>
          <ActionButton
            variant="outline"
            size="sm"
            action={() => resendFailed(id)}
          >
            <RotateCcw aria-hidden />
            Resend failed
          </ActionButton>
        </div>
      ) : null}
      {canMessage ? (
        <ActionForm
          action={(form) => messagePatient(id, form)}
          className="flex flex-col gap-2"
          label="Message the patient"
        >
          <Label htmlFor={`message-${id}`}>Message the patient</Label>
          <Textarea
            id={`message-${id}`}
            name="body"
            maxLength={1000}
            rows={3}
            required
            placeholder="Shown in the patient's portal under Updates. Do not give new medical instructions here."
          />
          <div className="flex justify-end">
            <Button type="submit" size="sm">
              <Send aria-hidden />
              Send
            </Button>
          </div>
        </ActionForm>
      ) : null}
      {drawer.messages.length === 0 ? (
        <p className="text-sm text-muted-foreground">No messages yet.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {drawer.messages.map((message, index) => {
            const inbound = message.direction === "INBOUND";
            const careTeam = message.provider === "care_team";
            return (
              <StaggerItem
                key={message.id}
                index={index}
                className={cn(
                  "flex max-w-[85%] flex-col gap-1 rounded-2xl px-3.5 py-2.5 text-sm",
                  inbound ? "self-start bg-muted" : "self-end bg-primary-soft",
                )}
              >
                <span className="text-xs font-medium text-muted-foreground">
                  {inbound
                    ? "Patient"
                    : careTeam
                      ? "Care team"
                      : `Reminder · ${message.channel.toLowerCase()}`}
                  {" · "}
                  {when(message.created_at)}
                </span>
                <span className="whitespace-pre-line">{message.body}</span>
                {message.status === "FAILED" ? (
                  <span className="text-xs text-urgent">
                    Not delivered{message.error ? `: ${message.error}` : ""}
                  </span>
                ) : null}
              </StaggerItem>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function RequestsTab({
  drawer,
  canChange,
}: {
  drawer: Drawer;
  canChange: boolean;
}) {
  const requests = drawer.tasks.filter((task) => task.type === "RESCHEDULE");
  const name = drawer.appointment.patient_name;
  if (requests.length === 0) {
    return (
      <p className="p-5 text-sm text-muted-foreground">
        No reschedule requests.
      </p>
    );
  }
  return (
    <ul className="flex flex-col gap-2 p-5">
      {requests.map((task) => {
        const state = requestState(task);
        return (
          <li
            key={task.id}
            className="flex flex-col gap-3 rounded-xl border p-3"
          >
            <div className="flex items-center gap-2">
              <CalendarClock
                className="size-4 text-muted-foreground"
                aria-hidden
              />
              <span className="flex-1 text-sm font-medium">
                Asked to reschedule
              </span>
              <Badge
                variant={
                  state === "pending"
                    ? "attention"
                    : state === "approved"
                      ? "ready"
                      : "neutral"
                }
              >
                {state === "pending"
                  ? "Waiting for an answer"
                  : state === "approved"
                    ? "Approved"
                    : "Declined"}
              </Badge>
            </div>
            {task.created_at ? (
              <p className="text-xs text-muted-foreground">
                Asked {when(task.created_at)}
              </p>
            ) : null}
            {state === "pending" && canChange ? (
              <div className="flex flex-wrap gap-2">
                <ActionButton
                  size="sm"
                  action={(form) => approveRequest(task.id, form)}
                  confirm={{
                    title: `Move ${name}'s procedure?`,
                    description:
                      "The prep plan follows the new time, and the patient sees the answer in their portal.",
                    confirmLabel: "Approve and move",
                    fields: <RescheduleFields />,
                  }}
                >
                  Approve
                </ActionButton>
                <ActionButton
                  size="sm"
                  variant="outline"
                  action={() => declineRequest(task.id)}
                  confirm={{
                    title: "Decline this request?",
                    description:
                      "The procedure stays at its current time. The patient is asked to call the hospital.",
                    confirmLabel: "Decline",
                    tone: "danger",
                  }}
                >
                  Decline
                </ActionButton>
              </div>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

function ActivityTab({ drawer }: { drawer: Drawer }) {
  const entries = buildActivity(drawer);
  if (entries.length === 0) {
    return (
      <p className="p-5 text-sm text-muted-foreground">
        Nothing has happened yet.
      </p>
    );
  }
  return (
    <ol className="flex flex-col gap-3 p-5" aria-label="Activity">
      {entries.map((entry, index) => (
        <StaggerItem
          key={`${entry.at}-${index}`}
          index={index}
          className="flex items-start gap-3"
        >
          <span
            aria-hidden
            className={cn(
              "mt-1.5 size-2 shrink-0 rounded-full",
              DOT[entry.tone],
            )}
          />
          <div className="flex-1">
            <p className="text-sm">{entry.text}</p>
            <p className="text-xs text-muted-foreground">{when(entry.at)}</p>
          </div>
        </StaggerItem>
      ))}
    </ol>
  );
}

function ActionBar({ drawer, role }: { drawer: Drawer; role: Role }) {
  const { canChange, canComplete } = permissionsFor(role);
  const row = drawer.appointment;
  const id = row.appointment_id;
  const closed = row.status === "CANCELLED" || row.status === "COMPLETED";
  const escort = escortStep(drawer.steps);

  return (
    <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:justify-end">
      <ActionButton
        variant="outline"
        disabled={!canComplete || closed}
        action={() => logCall(id)}
        confirm={{
          title: `Log a call with ${row.patient_name}?`,
          description:
            "Use this after you have spoken to the patient. Open “call the patient” tasks for this procedure are closed.",
          confirmLabel: "Log call",
        }}
      >
        <Phone aria-hidden />
        Call logged
      </ActionButton>
      <ActionButton
        variant="outline"
        disabled={!canComplete || closed || !escort}
        title={escort ? undefined : "No escort step is waiting in this plan"}
        action={() =>
          escort
            ? confirmStep(id, escort.event_id)
            : Promise.resolve({
                ok: false,
                message: "No escort step to confirm.",
              })
        }
        confirm={{
          title: "Confirm the escort?",
          description: escort
            ? `${row.patient_name} has someone to take them home after sedation. This marks “${escort.title}” done.`
            : undefined,
          confirmLabel: "Confirm escort",
        }}
      >
        <UserCheck aria-hidden />
        Confirm escort
      </ActionButton>
      <ActionButton
        variant="outline"
        disabled={!canChange || closed}
        action={(form) => reschedule(id, form)}
        confirm={{
          title: `Reschedule ${row.patient_name}?`,
          description:
            "The prep plan is rebuilt for the new time, and reminders follow it.",
          confirmLabel: "Reschedule",
          fields: <RescheduleFields />,
        }}
      >
        <CalendarClock aria-hidden />
        Reschedule
      </ActionButton>
      <ActionButton
        variant="destructive-soft"
        disabled={!canChange || closed}
        action={(form) => releaseSlot(id, form)}
        confirm={{
          title: `Cancel ${row.patient_name}'s procedure?`,
          description:
            "Reminders stop, and the slot is released for the waitlist.",
          confirmLabel: "Cancel procedure",
          tone: "danger",
          fields: (
            <>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="cancel-reason">Reason</Label>
                <select
                  id="cancel-reason"
                  name="reason"
                  required
                  defaultValue=""
                  className="h-10 rounded-lg border border-input bg-card px-3 text-[15px]"
                >
                  <option value="" disabled>
                    Choose a reason
                  </option>
                  {CANCEL_REASONS.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="cancel-note">Note (optional)</Label>
                <Textarea
                  id="cancel-note"
                  name="note"
                  maxLength={1000}
                  rows={2}
                />
              </div>
            </>
          ),
        }}
      >
        <CalendarX aria-hidden />
        Cancel
      </ActionButton>
    </div>
  );
}

/** The patient's details in a sheet over the list; closing it goes back to the list. */
export function PatientSheet({
  drawer,
  filter,
  role,
  tab = "overview",
}: {
  drawer: Drawer;
  filter: Filter;
  role: Role;
  /** The tab to open on, e.g. the prep timeline for a reported problem. */
  tab?: SheetTab;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(true);
  const { canChange, canComplete, canMessage } = permissionsFor(role);
  const row = drawer.appointment;
  const requests = drawer.tasks.filter((task) => task.type === "RESCHEDULE");
  const pending = requests.filter(
    (task) => requestState(task) === "pending",
  ).length;

  function onOpenChange(next: boolean): void {
    setOpen(next);
    if (!next) {
      // Let the sheet slide away before the list's URL changes.
      window.setTimeout(
        () => router.push(`/dashboard?filter=${filter}`, { scroll: false }),
        220,
      );
    }
  }

  return (
    <Sheet
      open={open}
      onOpenChange={onOpenChange}
      title={row.patient_name}
      description={`${row.procedure_name} · ${when(row.scheduled_at)} · ${row.facility_name}`}
      headerActions={<RiskPill level={row.risk_level} score={row.risk_score} />}
      footer={<ActionBar drawer={drawer} role={role} />}
    >
      <Tabs
        label="Patient details"
        defaultValue={tab}
        tabs={[
          {
            value: "overview",
            label: "Overview",
            content: <OverviewTab drawer={drawer} />,
          },
          {
            value: "timeline",
            label: "Prep timeline",
            content: <TimelineTab drawer={drawer} canComplete={canComplete} />,
          },
          {
            value: "messages",
            label: (
              <span className="flex items-center gap-1.5">
                <MessageSquare className="size-3.5" aria-hidden />
                Messages
              </span>
            ),
            content: <MessagesTab drawer={drawer} canMessage={canMessage} />,
          },
          {
            value: "requests",
            label: pending > 0 ? `Requests (${pending})` : "Requests",
            content: <RequestsTab drawer={drawer} canChange={canChange} />,
          },
          {
            value: "activity",
            label: "Activity",
            content: <ActivityTab drawer={drawer} />,
          },
        ]}
      />
    </Sheet>
  );
}
