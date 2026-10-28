import "server-only";

import type {
  AnalyticsSummary,
  Drawer,
  EscalationItem,
  Me,
  ProcedureType,
  Protocol,
  ProtocolSummary,
  QueueItem,
  Role,
  UpcomingRow,
} from "@prefix/shared";
import { notFound, redirect } from "next/navigation";

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

export function getCurrentUser(): Promise<Me> {
  return guarded(api<Me>("/auth/me"));
}

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
