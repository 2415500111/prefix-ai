import type { PortalAppointment } from "@prefix/shared";
import { CalendarClock, CalendarPlus, MapPin, Phone } from "lucide-react";
import type { ReactNode } from "react";

import {
  formatDateTime,
  formatRelative,
  formatTime,
  PORTAL_TEXT,
  type PortalLang,
} from "@/lib/portal-i18n";

const TILE =
  "pressable flex min-h-[72px] flex-col items-center justify-center gap-1 rounded-2xl bg-muted px-2 text-center text-[15px] leading-5 font-medium text-foreground hover:bg-[color-mix(in_oklab,var(--muted),var(--foreground)_6%)] focus-visible:ring-3 focus-visible:ring-ring/40 focus-visible:outline-none";

function Tile({
  href,
  icon,
  children,
  external = false,
  download = false,
}: {
  href: string;
  icon: ReactNode;
  children: ReactNode;
  external?: boolean;
  download?: boolean;
}) {
  return (
    <a
      className={TILE}
      href={href}
      {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
      {...(download ? { download: true } : {})}
    >
      <span aria-hidden className="text-primary">
        {icon}
      </span>
      {children}
    </a>
  );
}

/** The procedure: a countdown, when and where, and one-tap maps, call and calendar. */
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
      className="flex flex-col gap-4 rounded-[20px] border bg-card p-5 shadow-card"
    >
      <div className="flex flex-col gap-1">
        <p className="text-[15px] text-muted-foreground">{t.yourProcedure}</p>
        <h2
          id={`procedure-${appointment.id}`}
          className="text-[28px] leading-[34px] font-semibold tracking-tight"
        >
          {appointment.procedure_name}
        </h2>
        <p className="mt-1 inline-flex items-center gap-2 self-start rounded-full bg-primary-soft px-3 py-1 font-medium text-primary-soft-foreground">
          <CalendarClock aria-hidden className="size-5" />
          {t.countdown(formatRelative(appointment.scheduled_at, now, lang))}
        </p>
      </div>

      {appointment.status === "AT_RISK" ? (
        <p
          role="status"
          className="rounded-2xl bg-attention-soft p-4 text-attention-foreground"
        >
          {t.atRisk}
        </p>
      ) : null}

      <dl className="grid gap-3 sm:grid-cols-2">
        <div>
          <dt className="text-[15px] text-muted-foreground">{t.when}</dt>
          <dd className="font-medium">
            {formatDateTime(appointment.scheduled_at, tz, lang)}
          </dd>
        </div>
        {appointment.arrival_at ? (
          <div>
            <dt className="text-[15px] text-muted-foreground">{t.arriveBy}</dt>
            <dd className="font-medium">
              {formatTime(appointment.arrival_at, tz, lang)}
            </dd>
          </div>
        ) : null}
        <div className="sm:col-span-2">
          <dt className="text-[15px] text-muted-foreground">{t.where}</dt>
          <dd className="font-medium">
            {facility.name}
            {facility.address ? (
              <span className="block font-normal text-muted-foreground">
                {facility.address}
              </span>
            ) : null}
          </dd>
        </div>
      </dl>

      <div className="grid grid-cols-3 gap-2">
        {facility.maps_url ? (
          <Tile
            href={facility.maps_url}
            external
            icon={<MapPin className="size-6" strokeWidth={1.75} />}
          >
            {t.openMap}
          </Tile>
        ) : null}
        {facility.phone ? (
          <Tile
            href={`tel:${facility.phone}`}
            icon={<Phone className="size-6" strokeWidth={1.75} />}
          >
            {t.callHospital}
          </Tile>
        ) : null}
        <Tile
          href={`/p/calendar/${appointment.id}`}
          download
          icon={<CalendarPlus className="size-6" strokeWidth={1.75} />}
        >
          {t.addToCalendar}
        </Tile>
      </div>
    </section>
  );
}
