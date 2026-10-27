import "server-only";

import { cookies } from "next/headers";

import { type PortalLang, toPortalLang } from "@/lib/portal-i18n";

/** The patient's portal session: separate from staff cookies and scoped to /p. */
export const PATIENT_COOKIE = "prefix_pt";
/** The language the patient picked in the portal (not a secret). */
export const LANG_COOKIE = "prefix_lang";
const PORTAL_PATH = "/p";
const YEAR_SECONDS = 365 * 24 * 60 * 60;

export async function getPatientToken(): Promise<string | undefined> {
  return (await cookies()).get(PATIENT_COOKIE)?.value;
}

/** Only callable from Server Actions and Route Handlers. */
export async function storePatientSession(
  token: string,
  expiresAt: string,
): Promise<void> {
  (await cookies()).set(PATIENT_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: PORTAL_PATH,
    expires: new Date(expiresAt),
  });
}

export async function clearPatientSession(): Promise<void> {
  (await cookies()).delete({ name: PATIENT_COOKIE, path: PORTAL_PATH });
}

/** The chosen language, if the patient picked one. */
export async function getChosenLanguage(): Promise<PortalLang | undefined> {
  const value = (await cookies()).get(LANG_COOKIE)?.value;
  return value ? toPortalLang(value) : undefined;
}

export async function storeChosenLanguage(lang: PortalLang): Promise<void> {
  (await cookies()).set(LANG_COOKIE, lang, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: PORTAL_PATH,
    maxAge: YEAR_SECONDS,
  });
}
