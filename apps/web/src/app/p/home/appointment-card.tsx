import type { PortalAppointment } from "@prefix/shared";
import { CalendarPlus, MapPin, Phone } from "lucide-react";

import {
  formatDateTime,
  formatRelative,
  formatTime,
  PORTAL_TEXT,
  type PortalLang,
} from "@/lib/portal-i18n";

import { RescheduleForm } from "./reschedule-form";

const LINK =
  "inline-flex min-h-12 items-center gap-2 rounded-lg border bg-background px-4 font-medium underline-offset-4 hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none";

export function AppointmentCard({
  appointment,
  lang,
  now,
}: {
  appointment: PortalAppointment;
  lang: PortalLang;
  now: number;
}) {
  const t = PORTAL_TEXT[lang];
  const { facility } = appointment;
  const tz = facility.timezone;

  return (
    <section
      aria-labelledby={`procedure-${appointment.id}`}
      className="flex flex-col gap-4 rounded-xl border bg-card p-5 shadow-sm"
    >
      <div>
        <p className="text-base text-muted-foreground">{t.yourProcedure}</p>
        <h2
          id={`procedure-${appointment.id}`}
          className="text-2xl font-semibold"
        >
          {appointment.procedure_name}
        </h2>
        <p className="mt-1 font-medium">
          {t.countdown(formatRelative(appointment.scheduled_at, now, lang))}
        </p>
      </div>

      {appointment.status === "AT_RISK" ? (
        <p
          role="status"
          className="rounded-lg bg-amber-100 p-3 text-base text-amber-950"
        >
          {t.atRisk}
        </p>
      ) : null}

      <dl className="grid gap-3">
        <div>
          <dt className="text-base text-muted-foreground">{t.when}</dt>
          <dd className="font-medium">
            {formatDateTime(appointment.scheduled_at, tz, lang)}
          </dd>
        </div>
        {appointment.arrival_at ? (
          <div>
            <dt className="text-base text-muted-foreground">{t.arriveBy}</dt>
            <dd className="font-medium">
              {formatTime(appointment.arrival_at, tz, lang)}
            </dd>
          </div>
        ) : null}
        <div>
          <dt className="text-base text-muted-foreground">{t.where}</dt>
          <dd className="font-medium">
            {facility.name}
            {facility.address ? (
              <span className="block font-normal">{facility.address}</span>
            ) : null}
          </dd>
        </div>
      </dl>

      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        {facility.maps_url ? (
          <a
            className={LINK}
            href={facility.maps_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            <MapPin aria-hidden="true" className="size-5" />
            {t.openMap}
          </a>
        ) : null}
        {facility.phone ? (
          <a className={LINK} href={`tel:${facility.phone}`}>
            <Phone aria-hidden="true" className="size-5" />
            {t.callHospital}
          </a>
        ) : null}
        <a className={LINK} href={`/p/calendar/${appointment.id}`} download>
          <CalendarPlus aria-hidden="true" className="size-5" />
          {t.addToCalendar}
        </a>
      </div>

      {appointment.reschedule_requested ? (
        <p role="status" className="rounded-lg bg-muted p-3 text-base">
          {t.rescheduleRequested}
        </p>
      ) : (
        <RescheduleForm
          appointmentId={appointment.id}
          text={{
            reschedule: t.reschedule,
            rescheduleNoteLabel: t.rescheduleNoteLabel,
            rescheduleSend: t.rescheduleSend,
            sending: t.sending,
            cancel: t.cancel,
            actionFailed: t.actionFailed,
          }}
        />
      )}
    </section>
  );
}
