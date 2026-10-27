import type { PortalStep, StepState } from "@prefix/shared";
import {
  CircleAlert,
  CircleCheck,
  CircleDot,
  Clock,
  Info,
  TriangleAlert,
} from "lucide-react";
import type { ComponentType, SVGProps } from "react";

import {
  formatDateTime,
  formatRelative,
  PORTAL_TEXT,
  type PortalLang,
} from "@/lib/portal-i18n";

import { StepActions } from "./step-actions";

/** Colour is never the only signal: every state also has an icon and a word. */
const STATE_STYLE: Record<
  StepState,
  { className: string; Icon: ComponentType<SVGProps<SVGSVGElement>> }
> = {
  DONE: { className: "bg-emerald-100 text-emerald-900", Icon: CircleCheck },
  DUE: { className: "bg-blue-100 text-blue-950", Icon: CircleDot },
  UPCOMING: { className: "bg-muted text-foreground", Icon: Clock },
  OVERDUE: { className: "bg-amber-100 text-amber-950", Icon: TriangleAlert },
  ACTIVE: { className: "bg-sky-100 text-sky-950", Icon: Info },
  PROBLEM: { className: "bg-red-100 text-red-900", Icon: CircleAlert },
};

export function StateBadge({
  state,
  lang,
}: {
  state: StepState;
  lang: PortalLang;
}) {
  const { className, Icon } = STATE_STYLE[state];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-base font-medium ${className}`}
    >
      <Icon aria-hidden="true" className="size-4" />
      {PORTAL_TEXT[lang].states[state]}
    </span>
  );
}

export function Checklist({
  appointmentId,
  steps,
  lang,
}: {
  appointmentId: string;
  steps: PortalStep[];
  lang: PortalLang;
}) {
  const t = PORTAL_TEXT[lang];
  const items = steps.filter((step) => step.requires_confirmation);
  const done = items.filter((step) => step.state === "DONE").length;

  return (
    <section
      aria-labelledby={`checklist-${appointmentId}`}
      className="flex flex-col gap-3 rounded-xl border bg-card p-5 shadow-sm"
    >
      <h2 id={`checklist-${appointmentId}`} className="text-xl font-semibold">
        {t.checklistTitle}
      </h2>
      {items.length === 0 ? (
        <p>{t.checklistEmpty}</p>
      ) : (
        <>
          <p className="font-medium">
            {t.checklistProgress(done, items.length)}
          </p>
          <div
            role="progressbar"
            aria-label={t.checklistTitle}
            aria-valuemin={0}
            aria-valuemax={items.length}
            aria-valuenow={done}
            className="h-3 overflow-hidden rounded-full bg-muted"
          >
            <div
              className="h-full rounded-full bg-emerald-700"
              style={{ width: `${(done / items.length) * 100}%` }}
            />
          </div>
          <ul className="flex flex-col gap-2">
            {items.map((step) => (
              <li
                key={step.event_id}
                className="flex flex-wrap items-center justify-between gap-2"
              >
                <a
                  href={`#step-${step.event_id}`}
                  className="underline-offset-4 hover:underline"
                >
                  {step.title}
                </a>
                <StateBadge state={step.state} lang={lang} />
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

export function PrepTimeline({
  appointmentId,
  steps,
  timeZone,
  lang,
  now,
}: {
  appointmentId: string;
  steps: PortalStep[];
  timeZone: string;
  lang: PortalLang;
  now: number;
}) {
  const t = PORTAL_TEXT[lang];
  const untranslated =
    lang !== "en" && steps.some((step) => step.language === "en");
  const actionText = {
    confirm: t.confirm,
    confirming: t.confirming,
    problem: t.problem,
    problemNoteLabel: t.problemNoteLabel,
    sendProblem: t.sendProblem,
    sending: t.sending,
    cancel: t.cancel,
    actionFailed: t.actionFailed,
  };

  return (
    <section
      aria-labelledby={`timeline-${appointmentId}`}
      className="flex flex-col gap-3"
    >
      <h2 id={`timeline-${appointmentId}`} className="text-xl font-semibold">
        {t.timelineTitle}
      </h2>
      {untranslated ? (
        <p className="rounded-lg bg-muted p-3 text-base">{t.notTranslated}</p>
      ) : null}
      <ol className="flex flex-col gap-3">
        {steps.map((step) => (
          <li
            key={step.event_id}
            id={`step-${step.event_id}`}
            className="scroll-mt-4 rounded-xl border bg-card p-5 shadow-sm"
          >
            <div className="flex flex-wrap items-center gap-2">
              <StateBadge state={step.state} lang={lang} />
              {step.is_critical ? (
                <span className="rounded-full border border-red-800 px-3 py-1 text-base font-medium text-red-900">
                  {t.important}
                </span>
              ) : null}
            </div>
            <p className="mt-2 text-base text-muted-foreground">
              <time dateTime={step.due_at}>
                {formatDateTime(step.due_at, timeZone, lang)}
              </time>{" "}
              · {formatRelative(step.due_at, now, lang)}
            </p>
            <h3 className="mt-1 text-xl font-semibold" lang={step.language}>
              {step.title}
            </h3>
            <p className="mt-1 whitespace-pre-line" lang={step.language}>
              {step.instruction}
            </p>
            <StepActions
              eventId={step.event_id}
              title={step.title}
              canConfirm={step.can_confirm}
              canReportProblem={step.can_report_problem}
              text={actionText}
            />
          </li>
        ))}
      </ol>
    </section>
  );
}
