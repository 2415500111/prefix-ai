import type { PortalNotification } from "@prefix/shared";

import { formatDateTime, formatRelative, type PortalLang } from "./portal-i18n";

/**
 * The sentence for each update, from fixed templates. The API sends only the kind and its
 * fields, so no AI writes what the patient reads here (safety rule a). Step titles are the
 * approved protocol text; care-team messages were written by a person.
 */

export interface UpdateText {
  title: string;
  body: string | null;
}

interface Templates {
  stepNow: (step: string) => string;
  stepDone: (step: string) => string;
  stepSoon: (step: string) => string;
  message: string;
  requestPending: string;
  requestPendingBody: string;
  requestApproved: string;
  requestDeclined: string;
  requestDeclinedBody: string;
  moved: string;
  cancelled: string;
  cancelledBody: (procedure: string, when: string) => string;
}

const TEMPLATES: Record<PortalLang, Templates> = {
  en: {
    stepNow: (step) => `Do this now: ${step}`,
    stepDone: (step) => `Done: ${step}`,
    stepSoon: (step) => `Coming up: ${step}`,
    message: "Message from your care team",
    requestPending: "We received your request to change the date",
    requestPendingBody: "Your care team will call you about a new date.",
    requestApproved: "Your new date is confirmed",
    requestDeclined: "We could not change your date",
    requestDeclinedBody:
      "Your procedure stays as planned. Please call the hospital to talk about it.",
    moved: "Your procedure has a new time",
    cancelled: "Your procedure was cancelled",
    cancelledBody: (procedure, when) =>
      `${procedure}, ${when}. Please call the hospital if you have questions.`,
  },
  hi: {
    stepNow: (step) => `अभी करें: ${step}`,
    stepDone: (step) => `पूरा हुआ: ${step}`,
    stepSoon: (step) => `जल्द ही: ${step}`,
    message: "आपकी देखभाल टीम का संदेश",
    requestPending: "तारीख बदलने का आपका अनुरोध हमें मिल गया है",
    requestPendingBody: "आपकी देखभाल टीम नई तारीख के लिए आपको फ़ोन करेगी।",
    requestApproved: "आपकी नई तारीख पक्की हो गई है",
    requestDeclined: "हम आपकी तारीख नहीं बदल पाए",
    requestDeclinedBody:
      "आपकी प्रक्रिया पहले की तरह ही होगी। इसके बारे में बात करने के लिए कृपया अस्पताल को फ़ोन करें।",
    moved: "आपकी प्रक्रिया का समय बदल गया है",
    cancelled: "आपकी प्रक्रिया रद्द कर दी गई है",
    cancelledBody: (procedure, when) =>
      `${procedure}, ${when}। कोई सवाल हो तो कृपया अस्पताल को फ़ोन करें।`,
  },
};

/** Used only when an update has no procedure attached (a general care-team message). */
const FALLBACK_TIMEZONE = "Asia/Kolkata";

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function updateText(
  item: PortalNotification,
  lang: PortalLang,
  now: number,
): UpdateText {
  const t = TEMPLATES[lang];
  const timeZone = item.timezone ?? FALLBACK_TIMEZONE;
  const when = (iso: string | null) =>
    iso ? formatDateTime(iso, timeZone, lang) : "";
  const procedure = item.procedure_name ?? "";
  const step = item.step_title ?? "";
  const withProcedure = (text: string) =>
    procedure ? `${procedure} · ${text}` : text;

  switch (item.kind) {
    case "step_now":
      return {
        title: item.step_done ? t.stepDone(step) : t.stepNow(step),
        body: withProcedure(when(item.due_at)),
      };
    case "step_soon":
      return {
        title: t.stepSoon(step),
        body: item.due_at
          ? `${capitalize(formatRelative(item.due_at, now, lang))} · ${when(item.due_at)}`
          : null,
      };
    case "care_team_message":
      return { title: t.message, body: item.message };
    case "reschedule_request":
      if (item.request_status === "approved") {
        return {
          title: t.requestApproved,
          body: withProcedure(when(item.scheduled_at)),
        };
      }
      if (item.request_status === "declined") {
        return { title: t.requestDeclined, body: t.requestDeclinedBody };
      }
      return { title: t.requestPending, body: t.requestPendingBody };
    case "appointment_moved":
      return { title: t.moved, body: withProcedure(when(item.scheduled_at)) };
    case "appointment_cancelled":
      return {
        title: t.cancelled,
        body: t.cancelledBody(procedure, when(item.scheduled_at)),
      };
  }
}

/** The update for the banner: the newest urgent one the patient has not read. */
export function mostUrgentUnread(
  items: PortalNotification[],
): PortalNotification | null {
  return items.find((item) => item.urgency === "urgent" && !item.read) ?? null;
}

/** Where an update leads: its step in the plan, or Help for anything about the date. */
export function updateLink(item: PortalNotification): string | null {
  if (item.kind === "step_now" || item.kind === "step_soon") {
    return item.event_id ? `/p/prep#step-${item.event_id}` : "/p/prep";
  }
  if (item.kind === "care_team_message") return null;
  return "/p/help";
}
