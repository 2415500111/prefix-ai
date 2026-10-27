import "server-only";

import type {
  Me,
  ProcedureType,
  Protocol,
  ProtocolSummary,
  Role,
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
