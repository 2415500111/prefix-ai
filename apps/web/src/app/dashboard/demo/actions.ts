"use server";

import type { DemoPatientLink } from "@prefix/shared";
import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import { api, ApiError } from "@/lib/server/api";

export type DemoActionResult =
  { ok: true; message: string; url?: string } | { ok: false; message: string };

/** A signed-out session goes to login; the API's own message is shown for anything else. */
function failure(error: unknown): DemoActionResult {
  if (error instanceof ApiError && error.status === 401) redirect("/login");
  if (error instanceof ApiError && error.status === 403) {
    return { ok: false, message: "Your role cannot do this." };
  }
  if (error instanceof ApiError && error.status === 429) {
    return { ok: false, message: "Too many requests. Please wait a moment." };
  }
  return { ok: false, message: "The demo could not do that right now." };
}

/** A fresh single-use portal link to a demo patient who speaks the given language. */
export async function openDemoPatient(
  lang: "en" | "hi",
): Promise<DemoActionResult> {
  try {
    const link = await api<DemoPatientLink>(`/demo/patient-link?lang=${lang}`, {
      method: "POST",
    });
    return {
      ok: true,
      url: link.url,
      message: `Opened a demo patient (${link.patient_name}) in a new tab.`,
    };
  } catch (error) {
    return failure(error);
  }
}

/** Admins of the demo hospital regenerate its synthetic patients. */
export async function resetDemo(): Promise<DemoActionResult> {
  try {
    const counts = await api<{ patients: number; appointments: number }>(
      "/demo/reset",
      { method: "POST" },
    );
    refresh();
    return {
      ok: true,
      message: `Demo reset: ${counts.patients} patients and ${counts.appointments} bookings.`,
    };
  } catch (error) {
    return failure(error);
  }
}
