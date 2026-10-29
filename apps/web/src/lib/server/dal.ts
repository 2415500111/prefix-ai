import "server-only";

import type {
  AnalyticsSummary,
  Badges,
  Drawer,
  EscalationItem,
  Me,
  PatientSummary,
  ProcedureType,
  Protocol,
  ProtocolSummary,
  QueueItem,
  ReleasedSlot,
  RescheduleRequest,
  Role,
  UpcomingRow,
  WaitlistEntry,
} from "@prefix/shared";
import { notFound, redirect } from "next/navigation";
import { cache } from "react";

import { api, ApiError } from "./api";

/** Data Access Layer: every server-side read of API data goes through here. */

async function guarded<T>(request: Promise<T>): Promise<T> {
  try {
    return await request;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect("/login");
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
}

/** Cached for the request, since the shell and the page both need it. */
export const getCurrentUser = cache((): Promise<Me> =>
  guarded(api<Me>("/auth/me")),
);

export function listProtocols(): Promise<ProtocolSummary[]> {
  return guarded(api<ProtocolSummary[]>("/protocols"));
}

export function getProtocol(id: string): Promise<Protocol> {
  return guarded(api<Protocol>(`/protocols/${encodeURIComponent(id)}`));
}

export function listProtocolVersions(id: string): Promise<ProtocolSummary[]> {
  return guarded(
    api<ProtocolSummary[]>(`/protocols/${encodeURIComponent(id)}/versions`),
  );
}

export function listProcedureTypes(): Promise<ProcedureType[]> {
  return guarded(api<ProcedureType[]>("/procedure-types"));
}

const EDITORS: ReadonlySet<Role> = new Set(["ADMIN", "CLINICIAN"]);

/** Mirrors the API's permission table; the API remains the authority. */
export function canEditProtocols(role: Role): boolean {
  return EDITORS.has(role);
}

export function canApproveProtocols(role: Role): boolean {
  return EDITORS.has(role);
}

export type InboxFilter = "open" | "resolved" | "all";

export function listEscalations(
  status: InboxFilter = "open",
): Promise<EscalationItem[]> {
  return guarded(api<EscalationItem[]>(`/escalations?status=${status}`));
}

const HANDLERS: ReadonlySet<Role> = new Set([
  "ADMIN",
  "COORDINATOR",
  "NURSE",
  "CLINICIAN",
  "DEMO_VIEWER",
]);

/** Mirrors the API's ESCALATION_HANDLE permission; the API remains the authority. */
export function canHandleEscalations(role: Role): boolean {
  return HANDLERS.has(role);
}

/** Procedures in the next `hours` hours, least ready first (escalations before everything). */
export function listUpcoming(hours = 72): Promise<UpcomingRow[]> {
  return guarded(api<UpcomingRow[]>(`/dashboard/upcoming?hours=${hours}`));
}

export function getPatientDrawer(appointmentId: string): Promise<Drawer> {
  return guarded(
    api<Drawer>(`/dashboard/appointments/${encodeURIComponent(appointmentId)}`),
  );
}

export function listTaskQueue(): Promise<QueueItem[]> {
  return guarded(api<QueueItem[]>("/dashboard/queue"));
}

export function getAnalyticsSummary(
  start: string,
  end: string,
  baselineRate?: number,
): Promise<AnalyticsSummary> {
  const query = new URLSearchParams({ start, end });
  if (baselineRate !== undefined)
    query.set("baseline_rate", String(baselineRate));
  return guarded(
    api<AnalyticsSummary>(`/analytics/summary?${query.toString()}`),
  );
}

const EXPORTERS: ReadonlySet<Role> = new Set(["ADMIN", "COORDINATOR"]);

/** Mirrors the API's ANALYTICS_EXPORT permission; the API remains the authority. */
export function canExportAnalytics(role: Role): boolean {
  return EXPORTERS.has(role);
}

/** Patients to choose from when adding someone to the waitlist. */
export function listPatients(): Promise<PatientSummary[]> {
  return guarded(api<PatientSummary[]>("/patients?limit=100"));
}

/** Patients still waiting for a procedure, highest priority first. */
export function listWaitlist(): Promise<WaitlistEntry[]> {
  return guarded(api<WaitlistEntry[]>("/waitlist?status=ACTIVE"));
}

/** Cancelled slots that are still ahead and not yet filled, with any open offer. */
export function listReleasedSlots(): Promise<ReleasedSlot[]> {
  return guarded(api<ReleasedSlot[]>("/waitlist/slots"));
}

const WAITLIST_MANAGERS: ReadonlySet<Role> = new Set(["ADMIN", "COORDINATOR"]);

/** Mirrors the API's APPOINTMENT_WRITE permission; the API remains the authority. */
export function canManageWaitlist(role: Role): boolean {
  return WAITLIST_MANAGERS.has(role);
}

/** Mirrors the API's PATIENT_WRITE and APPOINTMENT_WRITE permissions for CSV imports. */
export function canImportRecords(role: Role): boolean {
  return WAITLIST_MANAGERS.has(role);
}

const NO_BADGES: Badges = {
  open_tasks: 0,
  open_escalations: 0,
  pending_requests: 0,
};

/** Sidebar counts. Roles that cannot see appointments get zeros rather than an error. */
export const getBadges = cache(async (): Promise<Badges> => {
  try {
    return await guarded(api<Badges>("/dashboard/badges"));
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) return NO_BADGES;
    throw error;
  }
});

/** Reschedule requests: pending first, then those answered in the last week. */
export function listRequests(): Promise<RescheduleRequest[]> {
  return guarded(api<RescheduleRequest[]>("/requests"));
}

/** Mirrors the API's APPOINTMENT_WRITE permission for answering reschedule requests. */
export function canAnswerRequests(role: Role): boolean {
  return WAITLIST_MANAGERS.has(role);
}

const MESSENGERS: ReadonlySet<Role> = new Set([
  "ADMIN",
  "COORDINATOR",
  "NURSE",
]);

/** Mirrors the API's MESSAGE_SEND permission. */
export function canMessagePatients(role: Role): boolean {
  return MESSENGERS.has(role);
}
