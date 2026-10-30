import { CalendarSync, Phone } from "lucide-react";
import type { Metadata } from "next";
import { Suspense } from "react";

import { PORTAL_TEXT } from "@/lib/portal-i18n";
import {
  getAssistantHistory,
  getMyAppointments,
  getPortalLanguage,
} from "@/lib/server/portal";

import { AssistantPanel } from "../../_portal/assistant-panel";
import { EmergencyBox } from "../../_portal/emergency";
import { PortalSkeleton } from "../../_portal/portal-skeleton";
import { RescheduleForm } from "../../_portal/reschedule-form";

export const metadata: Metadata = { title: "Help" };

const CALL =
  "pressable inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-[17px] font-semibold text-primary-foreground shadow-card hover:bg-[color-mix(in_oklab,var(--primary),black_12%)] focus-visible:ring-3 focus-visible:ring-ring/40 focus-visible:outline-none";

export default function HelpPage() {
  return (
    <Suspense fallback={<PortalSkeleton />}>
      <Help />
    </Suspense>
  );
}

async function Help() {
  const lang = await getPortalLanguage();
  const { appointments } = await getMyAppointments(lang);
  const t = PORTAL_TEXT[lang];
  const [next] = appointments;
  const history = next ? await getAssistantHistory(next.id, lang) : [];
  const phone = appointments.find((item) => item.facility.phone)?.facility
    .phone;

  return (
    <main lang={lang} className="flex flex-col gap-4">
      <h1 className="text-[28px] leading-[34px] font-semibold tracking-tight">
        {t.helpTitle}
      </h1>

      <EmergencyBox lang={lang} />

      <section
        aria-labelledby="call-hospital"
        className="flex flex-col gap-3 rounded-[20px] border bg-card p-5 shadow-card"
      >
        <div className="flex items-start gap-3">
          <span
            aria-hidden
            className="grid size-10 shrink-0 place-items-center rounded-full bg-primary-soft text-primary-soft-foreground"
          >
            <Phone className="size-5" strokeWidth={1.75} />
          </span>
          <div>
            <h2 id="call-hospital" className="text-[20px] font-semibold">
              {t.callHospital}
            </h2>
            <p className="text-[15px] text-muted-foreground">
              {phone ? t.callHospitalHint : t.noHospitalPhone}
            </p>
          </div>
        </div>
        {phone ? (
          <a href={`tel:${phone}`} className={`${CALL} self-start`}>
            <Phone aria-hidden className="size-5" />
            <span className="tabular-nums">{phone}</span>
          </a>
        ) : null}
      </section>

      {appointments.length > 0 ? (
        <section
          aria-labelledby="change-date"
          className="flex flex-col gap-3 rounded-[20px] border bg-card p-5 shadow-card"
        >
          <div className="flex items-start gap-3">
            <span
              aria-hidden
              className="grid size-10 shrink-0 place-items-center rounded-full bg-primary-soft text-primary-soft-foreground"
            >
              <CalendarSync className="size-5" strokeWidth={1.75} />
            </span>
            <div>
              <h2 id="change-date" className="text-[20px] font-semibold">
                {t.rescheduleTitle}
              </h2>
              <p className="text-[15px] text-muted-foreground">
                {t.rescheduleHint}
              </p>
            </div>
          </div>
          {appointments.map((appointment) => (
            <div key={appointment.id} className="flex flex-col gap-2">
              {appointments.length > 1 ? (
                <p className="font-medium">{appointment.procedure_name}</p>
              ) : null}
              {appointment.reschedule_requested ? (
                <p role="status" className="rounded-2xl bg-muted p-4">
                  {t.rescheduleRequested}
                </p>
              ) : (
                <RescheduleForm
                  appointmentId={appointment.id}
                  procedureName={appointment.procedure_name}
                  lang={lang}
                />
              )}
            </div>
          ))}
        </section>
      ) : null}

      {next ? (
        <AssistantPanel appointmentId={next.id} lang={lang} history={history} />
      ) : null}
    </main>
  );
}
