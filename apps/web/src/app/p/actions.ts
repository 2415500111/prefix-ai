"use server";

import type { PatientSession } from "@prefix/shared";
import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import { api, ApiError } from "@/lib/server/api";
import {
  clearPatientSession,
  storeChosenLanguage,
  storePatientSession,
} from "@/lib/server/patient-session";
import { EXPIRED_PATH, patientApi } from "@/lib/server/portal";
import { toPortalLang } from "@/lib/portal-i18n";

export interface ActionResult {
  ok: boolean;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MAX_NOTE = 1000;

function note(formData: FormData): string | null {
  const value = String(formData.get("note") ?? "").trim();
  return value ? value.slice(0, MAX_NOTE) : null;
}

/** Exchange the single-use token from the link for an httpOnly session cookie.
 * The caller navigates on success (a redirect here would reject the client's await). */
export async function redeemMagicLink(token: string): Promise<ActionResult> {
  if (!/^[\w-]{20,200}$/.test(token)) return { ok: false };
  let session: PatientSession;
  try {
    session = await api<PatientSession>("/patient/session", {
      method: "POST",
      body: { token },
      token: null,
    });
  } catch (error) {
    if (error instanceof ApiError && error.status < 500) return { ok: false };
    throw error;
  }
  await storePatientSession(session.access_token, session.expires_at);
  return { ok: true };
}

async function run(path: string, body?: unknown): Promise<ActionResult> {
  try {
    await patientApi(path, { method: "POST", body });
  } catch (error) {
    // 401 has already redirected; other client errors (e.g. a step that cannot be
    // confirmed yet) are shown as a generic failure and the page is refreshed.
    if (error instanceof ApiError && error.status < 500) {
      refresh();
      return { ok: false };
    }
    throw error;
  }
  refresh();
  return { ok: true };
}

export async function confirmStep(eventId: string): Promise<ActionResult> {
  if (!UUID.test(eventId)) return { ok: false };
  return run(`/patient/steps/${eventId}/confirm`);
}

export async function reportProblem(
  eventId: string,
  _previous: ActionResult | null,
  formData: FormData,
): Promise<ActionResult> {
  if (!UUID.test(eventId)) return { ok: false };
  return run(`/patient/steps/${eventId}/problem`, { note: note(formData) });
}

export async function requestReschedule(
  appointmentId: string,
  _previous: ActionResult | null,
  formData: FormData,
): Promise<ActionResult> {
  if (!UUID.test(appointmentId)) return { ok: false };
  return run(`/patient/appointments/${appointmentId}/reschedule-request`, {
    note: note(formData),
  });
}

export async function chooseLanguage(formData: FormData): Promise<void> {
  await storeChosenLanguage(toPortalLang(String(formData.get("lang") ?? "")));
  refresh();
}

export async function signOut(): Promise<void> {
  await clearPatientSession();
  redirect(EXPIRED_PATH);
}
