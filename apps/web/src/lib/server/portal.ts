import "server-only";

import type {
  AssistantReply,
  NotificationFeed,
  PatientSelf,
  PortalAppointment,
} from "@prefix/shared";
import { redirect } from "next/navigation";
import { cache } from "react";

import { type PortalLang, toPortalLang } from "@/lib/portal-i18n";

import { api, ApiError } from "./api";
import { getChosenLanguage, getPatientToken } from "./patient-session";

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

/** Cached for the request, since the portal shell and the page both need it. */
export const getPatientSelf = cache((): Promise<PatientSelf> =>
  patientApi<PatientSelf>("/patient/me"),
);

/** The language the portal is shown in: the patient's pick, else their preferred language. */
export const getPortalLanguage = cache(async (): Promise<PortalLang> => {
  const [self, chosen] = await Promise.all([
    getPatientSelf(),
    getChosenLanguage(),
  ]);
  return chosen ?? toPortalLang(self.preferred_language);
});

export interface MyAppointments {
  appointments: PortalAppointment[];
  /** When the data was fetched (ms since epoch): the "now" for countdowns. */
  fetchedAt: number;
}

export const getMyAppointments = cache(
  async (lang: string): Promise<MyAppointments> => {
    const appointments = await patientApi<PortalAppointment[]>(
      `/patient/appointments?lang=${encodeURIComponent(lang)}`,
    );
    return { appointments, fetchedAt: Date.now() };
  },
);

export interface MyUpdates extends NotificationFeed {
  /** When the feed was fetched (ms since epoch): the "now" for relative times. */
  fetchedAt: number;
}

/** The patient's Updates, newest first. */
export const getNotifications = cache(
  async (lang: string): Promise<MyUpdates> => {
    const feed = await patientApi<NotificationFeed>(
      `/patient/notifications?lang=${encodeURIComponent(lang)}`,
    );
    return { ...feed, fetchedAt: Date.now() };
  },
);

export function getAssistantHistory(
  appointmentId: string,
  lang: string,
): Promise<AssistantReply[]> {
  return patientApi<AssistantReply[]>(
    `/patient/assistant/questions?appointment_id=${encodeURIComponent(appointmentId)}&lang=${encodeURIComponent(lang)}`,
  );
}
