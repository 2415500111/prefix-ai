import "server-only";

import type { PatientSelf, PortalAppointment } from "@prefix/shared";
import { redirect } from "next/navigation";

import { api, ApiError } from "./api";
import { getPatientToken } from "./patient-session";

/** Data Access Layer for the patient portal: every call uses the patient's own session. */

export const EXPIRED_PATH = "/p/expired";

async function patientToken(): Promise<string> {
  const token = await getPatientToken();
  if (!token) redirect(EXPIRED_PATH);
  return token;
}

/** Call the API as the patient; a dead session sends them to the expired-link page. */
export async function patientApi<T>(
  path: string,
  options: { method?: "GET" | "POST"; body?: unknown } = {},
): Promise<T> {
  const token = await patientToken();
  try {
    return await api<T>(path, { ...options, token });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401)
      redirect(EXPIRED_PATH);
    throw error;
  }
}

export function getPatientSelf(): Promise<PatientSelf> {
  return patientApi<PatientSelf>("/patient/me");
}

export interface MyAppointments {
  appointments: PortalAppointment[];
  /** When the data was fetched (ms since epoch): the "now" for countdowns. */
  fetchedAt: number;
}

export async function getMyAppointments(lang: string): Promise<MyAppointments> {
  const appointments = await patientApi<PortalAppointment[]>(
    `/patient/appointments?lang=${encodeURIComponent(lang)}`,
  );
  return { appointments, fetchedAt: Date.now() };
}
