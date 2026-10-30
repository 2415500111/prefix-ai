"use server";

import { ApiError } from "@/lib/server/api";
import {
  listEscalations,
  listRequests,
  listTaskQueue,
  listUpcoming,
} from "@/lib/server/dal";

export interface PatientHit {
  appointment_id: string;
  patient_name: string;
  procedure_name: string;
  scheduled_at: string;
}

const SEARCH_HOURS = 168;
const MAX_HITS = 8;

/**
 * Finds patients among the procedures in the next seven days, by name or procedure. Names are
 * encrypted at rest, so the search runs over the list the dashboard is allowed to read anyway.
 */
export async function searchPatients(query: string): Promise<PatientHit[]> {
  const words = query
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 4);
  if (words.length === 0 || query.length > 100) return [];
  const rows = await listUpcoming(SEARCH_HOURS);
  return rows
    .filter((row) => {
      const text = `${row.patient_name} ${row.procedure_name}`.toLowerCase();
      return words.every((word) => text.includes(word));
    })
    .slice(0, MAX_HITS)
    .map((row) => ({
      appointment_id: row.appointment_id,
      patient_name: row.patient_name,
      procedure_name: row.procedure_name,
      scheduled_at: row.scheduled_at,
    }));
}

export interface StaffNotification {
  id: string;
  kind: "escalation" | "task" | "request";
  tone: "urgent" | "attention" | "info";
  title: string;
  detail: string;
  href: string;
  at: string;
}

async function orEmpty<T>(load: () => Promise<T[]>): Promise<T[]> {
  try {
    return await load();
  } catch (error) {
    // A role that cannot see one of these lists simply gets no items from it.
    if (error instanceof ApiError && error.status === 403) return [];
    throw error;
  }
}

/** What needs a person's attention: open escalations, overdue tasks, pending requests. */
export async function loadNotifications(): Promise<StaffNotification[]> {
  const [escalations, tasks, requests] = await Promise.all([
    orEmpty(() => listEscalations("open")),
    orEmpty(() => listTaskQueue()),
    orEmpty(() => listRequests()),
  ]);
  const items: StaffNotification[] = [
    ...escalations.map((item) => ({
      id: `escalation-${item.id}`,
      kind: "escalation" as const,
      tone:
        item.severity === "URGENT" || item.severity === "HIGH"
          ? ("urgent" as const)
          : ("attention" as const),
      title: `Escalation: ${item.patient_name}`,
      detail: item.procedure_name ?? "Needs a nurse",
      href: "/dashboard/inbox",
      at: item.created_at,
    })),
    ...tasks
      .filter((task) => task.sla !== "on_time" && task.type !== "RESCHEDULE")
      .map((task) => ({
        id: `task-${task.id}`,
        kind: "task" as const,
        tone:
          task.sla === "overdue" ? ("urgent" as const) : ("attention" as const),
        title: task.title,
        detail: `${task.patient_name} · ${task.sla === "overdue" ? "Overdue" : "Due soon"}`,
        href: task.appointment_id
          ? `/dashboard?appointment=${task.appointment_id}`
          : "/dashboard/tasks",
        at: task.due_at ?? new Date(0).toISOString(),
      })),
    ...requests
      .filter((request) => request.status === "pending")
      .map((request) => ({
        id: `request-${request.id}`,
        kind: "request" as const,
        tone: "info" as const,
        title: `Reschedule request: ${request.patient_name}`,
        detail: request.procedure_name,
        href: "/dashboard/requests",
        at: request.created_at,
      })),
  ];
  return items.sort((a, b) => b.at.localeCompare(a.at)).slice(0, 15);
}
