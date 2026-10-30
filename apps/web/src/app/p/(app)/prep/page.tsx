import type { Metadata } from "next";
import { Suspense } from "react";

import { PORTAL_TEXT } from "@/lib/portal-i18n";
import { getMyAppointments, getPortalLanguage } from "@/lib/server/portal";

import { EmergencyBox } from "../../_portal/emergency";
import { PortalSkeleton } from "../../_portal/portal-skeleton";
import { PrepProgress, PrepTimeline } from "../../_portal/prep-steps";

export const metadata: Metadata = { title: "My prep" };

export default function PrepPage() {
  return (
    <Suspense fallback={<PortalSkeleton />}>
      <Prep />
    </Suspense>
  );
}

async function Prep() {
  const lang = await getPortalLanguage();
  const { appointments, fetchedAt: now } = await getMyAppointments(lang);
  const t = PORTAL_TEXT[lang];
  const several = appointments.length > 1;

  return (
    <main lang={lang} className="flex flex-col gap-4">
      <h1 className="text-[28px] leading-[34px] font-semibold tracking-tight">
        {t.prepTitle}
      </h1>
      {appointments.length === 0 ? (
        <p className="rounded-[20px] border bg-card p-5 shadow-card">
          {t.noAppointments}
        </p>
      ) : (
        appointments.map((appointment) => (
          <section
            key={appointment.id}
            aria-labelledby={`plan-${appointment.id}`}
            className="flex flex-col gap-3"
          >
            <h2
              id={`plan-${appointment.id}`}
              className={several ? "text-[20px] font-semibold" : "sr-only"}
            >
              {several
                ? appointment.procedure_name
                : `${t.timelineTitle}: ${appointment.procedure_name}`}
            </h2>
            <PrepProgress steps={appointment.steps} lang={lang} />
            <PrepTimeline
              steps={appointment.steps}
              timeZone={appointment.facility.timezone}
              lang={lang}
              now={now}
            />
          </section>
        ))
      )}
      <EmergencyBox lang={lang} compact />
    </main>
  );
}
