import type { PortalAppointment } from "@prefix/shared";
import type { Metadata } from "next";
import { Suspense } from "react";

import {
  formatDateTime,
  PORTAL_TEXT,
  type PortalLang,
} from "@/lib/portal-i18n";
import {
  getMyAppointments,
  getPatientSelf,
  getPortalLanguage,
} from "@/lib/server/portal";

import { AppointmentCard } from "../../_portal/appointment-card";
import { EmergencyBox } from "../../_portal/emergency";
import { PortalSkeleton } from "../../_portal/portal-skeleton";
import { NextStepCard, ReadinessCard } from "../../_portal/prep-steps";

export const metadata: Metadata = { title: "My procedure" };

export default function PortalHomePage() {
  return (
    <Suspense fallback={<PortalSkeleton />}>
      <PortalHome />
    </Suspense>
  );
}

async function PortalHome() {
  const [self, lang] = await Promise.all([
    getPatientSelf(),
    getPortalLanguage(),
  ]);
  const { appointments, fetchedAt: now } = await getMyAppointments(lang);
  const t = PORTAL_TEXT[lang];
  const [next, ...others] = appointments;

  return (
    <main lang={lang} className="flex flex-col gap-4">
      <h1 className="text-[28px] leading-[34px] font-semibold tracking-tight">
        {t.greeting(self.first_name)}
      </h1>

      {next ? (
        <>
          <AppointmentCard appointment={next} lang={lang} now={now} />
          <ReadinessCard steps={next.steps} lang={lang} />
          <NextStepCard
            steps={next.steps}
            timeZone={next.facility.timezone}
            lang={lang}
            now={now}
          />
          {others.length > 0 ? (
            <OtherProcedures appointments={others} lang={lang} />
          ) : null}
        </>
      ) : (
        <p className="rounded-[20px] border bg-card p-5 shadow-card">
          {t.noAppointments}
        </p>
      )}

      <EmergencyBox lang={lang} compact />
    </main>
  );
}

function OtherProcedures({
  appointments,
  lang,
}: {
  appointments: PortalAppointment[];
  lang: PortalLang;
}) {
  return (
    <section
      aria-labelledby="other-procedures"
      className="flex flex-col gap-2 rounded-[20px] border bg-card p-5 shadow-card"
    >
      <h2 id="other-procedures" className="text-[20px] font-semibold">
        {PORTAL_TEXT[lang].otherProcedures}
      </h2>
      <ul className="flex flex-col divide-y">
        {appointments.map((appointment) => (
          <li key={appointment.id} className="flex flex-col py-2">
            <span className="font-medium">{appointment.procedure_name}</span>
            <span className="text-[15px] text-muted-foreground">
              {formatDateTime(
                appointment.scheduled_at,
                appointment.facility.timezone,
                lang,
              )}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
