import type { Metadata } from "next";
import { Suspense } from "react";

import { Button } from "@/components/ui/button";
import {
  LANGUAGE_LABELS,
  PORTAL_LANGUAGES,
  PORTAL_TEXT,
  type PortalLang,
  toPortalLang,
} from "@/lib/portal-i18n";
import { getChosenLanguage } from "@/lib/server/patient-session";
import {
  getAssistantHistory,
  getMyAppointments,
  getPatientSelf,
} from "@/lib/server/portal";

import { chooseLanguage, signOut } from "../actions";
import { AppointmentCard } from "./appointment-card";
import { AssistantPanel } from "./assistant-panel";
import { Checklist, PrepTimeline } from "./prep-steps";

export const metadata: Metadata = { title: "My procedure" };

export default function PortalHomePage() {
  return (
    <Suspense fallback={<PortalSkeleton />}>
      <PortalHome />
    </Suspense>
  );
}

function PortalSkeleton() {
  return (
    <div aria-hidden="true" className="flex flex-col gap-4 py-6">
      <div className="h-8 w-48 animate-pulse rounded bg-muted" />
      <div className="h-64 animate-pulse rounded-xl bg-muted" />
      <div className="h-40 animate-pulse rounded-xl bg-muted" />
    </div>
  );
}

async function PortalHome() {
  const [self, chosen] = await Promise.all([
    getPatientSelf(),
    getChosenLanguage(),
  ]);
  const lang = chosen ?? toPortalLang(self.preferred_language);
  const { appointments, fetchedAt: now } = await getMyAppointments(lang);
  const histories = await Promise.all(
    appointments.map((appointment) =>
      getAssistantHistory(appointment.id, lang),
    ),
  );
  const t = PORTAL_TEXT[lang];

  return (
    <main lang={lang} className="flex flex-col gap-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <p className="font-semibold">Prefix AI</p>
        <div className="flex items-center gap-2">
          <LanguageSwitch lang={lang} />
          <form action={signOut}>
            <Button type="submit" variant="ghost" className="h-12 text-base">
              {t.signOut}
            </Button>
          </form>
        </div>
      </header>

      <h1 className="text-2xl font-semibold">{t.greeting(self.first_name)}</h1>

      {appointments.length === 0 ? (
        <p className="rounded-xl border bg-card p-5">{t.noAppointments}</p>
      ) : (
        appointments.map((appointment, index) => (
          <div key={appointment.id} className="flex flex-col gap-5">
            <AppointmentCard appointment={appointment} lang={lang} now={now} />
            <Checklist
              appointmentId={appointment.id}
              steps={appointment.steps}
              lang={lang}
            />
            <AssistantPanel
              appointmentId={appointment.id}
              lang={lang}
              history={histories[index] ?? []}
            />
            <PrepTimeline
              appointmentId={appointment.id}
              steps={appointment.steps}
              timeZone={appointment.facility.timezone}
              lang={lang}
              now={now}
            />
          </div>
        ))
      )}

      <aside
        aria-labelledby="emergency-title"
        className="rounded-xl border-2 border-red-800 bg-card p-5"
      >
        <h2 id="emergency-title" className="text-xl font-semibold text-red-900">
          {t.emergencyTitle}
        </h2>
        <p className="mt-1">{t.emergencyText}</p>
      </aside>
    </main>
  );
}

function LanguageSwitch({ lang }: { lang: PortalLang }) {
  return (
    <form action={chooseLanguage} aria-label={PORTAL_TEXT[lang].language}>
      <div className="flex rounded-lg border bg-background p-1">
        {PORTAL_LANGUAGES.map((option) => (
          <button
            key={option}
            type="submit"
            name="lang"
            value={option}
            lang={option}
            aria-pressed={option === lang}
            className="min-h-10 min-w-12 rounded-md px-3 text-base font-medium focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none aria-pressed:bg-primary aria-pressed:text-primary-foreground"
          >
            {LANGUAGE_LABELS[option]}
          </button>
        ))}
      </div>
    </form>
  );
}
