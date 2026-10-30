import type { PortalStep, StepState } from "@prefix/shared";
import {
  ChevronRight,
  CircleAlert,
  CircleCheck,
  CircleDot,
  Clock,
  Info,
  ShieldAlert,
  TriangleAlert,
} from "lucide-react";
import Link from "next/link";
import type { ComponentType, SVGProps } from "react";

import { ProgressBar, ProgressRing, type Tone } from "@/components/ui/animated";
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
  DONE: { className: "bg-ready-soft text-ready-foreground", Icon: CircleCheck },
  DUE: {
    className: "bg-primary-soft text-primary-soft-foreground",
    Icon: CircleDot,
  },
  UPCOMING: { className: "bg-muted text-muted-foreground", Icon: Clock },
  OVERDUE: {
    className: "bg-attention-soft text-attention-foreground",
    Icon: TriangleAlert,
  },
  ACTIVE: {
    className: "bg-primary-soft text-primary-soft-foreground",
    Icon: Info,
  },
  PROBLEM: {
    className: "bg-urgent-soft text-urgent-foreground",
    Icon: CircleAlert,
  },
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
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[15px] leading-5 font-medium ${className}`}
    >
      <Icon aria-hidden className="size-4" />
      {PORTAL_TEXT[lang].states[state]}
    </span>
  );
}

function ImportantPill({ lang }: { lang: PortalLang }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-urgent/40 px-3 py-1 text-[15px] leading-5 font-medium text-urgent-foreground">
      <ShieldAlert aria-hidden className="size-4" />
      {PORTAL_TEXT[lang].important}
    </span>
  );
}

/** Steps the patient confirms, and how many are done. */
export function readiness(steps: PortalStep[]): {
  done: number;
  total: number;
} {
  const confirmable = steps.filter((step) => step.requires_confirmation);
  return {
    done: confirmable.filter((step) => step.state === "DONE").length,
    total: confirmable.length,
  };
}

function readinessTone(steps: PortalStep[]): Tone {
  const { done, total } = readiness(steps);
  if (steps.some((step) => step.state === "PROBLEM")) return "urgent";
  if (steps.some((step) => step.state === "OVERDUE")) return "attention";
  return total > 0 && done === total ? "ready" : "primary";
}

/**
 * The step to show on Home: one to do now (the earliest), else the next one coming up, else the
 * latest instruction in effect. Steps arrive in time order.
 */
export function pickNextStep(steps: PortalStep[]): PortalStep | null {
  return (
    steps.find((step) => step.state === "OVERDUE" || step.state === "DUE") ??
    steps.find((step) => step.state === "UPCOMING") ??
    steps.findLast((step) => step.state === "ACTIVE") ??
    null
  );
}

/** The readiness ring on Home. */
export function ReadinessCard({
  steps,
  lang,
}: {
  steps: PortalStep[];
  lang: PortalLang;
}) {
  const t = PORTAL_TEXT[lang];
  const { done, total } = readiness(steps);
  const summary =
    total === 0
      ? t.readinessNothing
      : done === total
        ? t.readinessAllDone
        : t.checklistProgress(done, total);

  return (
    <section
      aria-labelledby="readiness-title"
      className="flex items-center gap-5 rounded-[20px] border bg-card p-5 shadow-card"
    >
      <ProgressRing
        value={total === 0 ? 0 : (done / total) * 100}
        label={t.readinessTitle}
        tone={readinessTone(steps)}
        size={96}
      >
        <span className="text-[22px] leading-none font-semibold tabular-nums">
          {done}/{total}
        </span>
      </ProgressRing>
      <div className="flex min-w-0 flex-col gap-1">
        <h2 id="readiness-title" className="text-[20px] font-semibold">
          {t.readinessTitle}
        </h2>
        <p className="text-muted-foreground">{summary}</p>
      </div>
    </section>
  );
}

/** The next step, highlighted, with its actions. */
export function NextStepCard({
  steps,
  timeZone,
  lang,
  now,
}: {
  steps: PortalStep[];
  timeZone: string;
  lang: PortalLang;
  now: number;
}) {
  const t = PORTAL_TEXT[lang];
  const step = pickNextStep(steps);

  return (
    <section
      aria-labelledby="next-step-title"
      className="flex flex-col gap-2 rounded-[20px] border border-primary/30 bg-primary-soft/60 p-5"
    >
      <h2
        id="next-step-title"
        className="text-[15px] font-semibold tracking-wide text-primary-soft-foreground uppercase"
      >
        {t.nextStepTitle}
      </h2>
      {step ? (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <StateBadge state={step.state} lang={lang} />
            {step.is_critical ? <ImportantPill lang={lang} /> : null}
          </div>
          <h3
            className="text-[22px] leading-7 font-semibold"
            lang={step.language}
          >
            {step.title}
          </h3>
          <p className="text-[15px] text-muted-foreground">
            <time dateTime={step.due_at}>
              {formatDateTime(step.due_at, timeZone, lang)}
            </time>{" "}
            · {formatRelative(step.due_at, now, lang)}
          </p>
          <p className="whitespace-pre-line" lang={step.language}>
            {step.instruction}
          </p>
          <StepActions
            eventId={step.event_id}
            title={step.title}
            canConfirm={step.can_confirm}
            canReportProblem={step.can_report_problem}
            lang={lang}
          />
        </>
      ) : (
        <p>{t.noNextStep}</p>
      )}
      <Link
        href="/p/prep"
        className="mt-1 inline-flex min-h-12 items-center gap-1 self-start font-medium text-primary-soft-foreground underline-offset-4 hover:underline focus-visible:ring-3 focus-visible:ring-ring/40 focus-visible:outline-none"
      >
        {t.seeFullPlan}
        <ChevronRight aria-hidden className="size-5" />
      </Link>
    </section>
  );
}

/** Progress for one procedure's plan, at the top of My prep. */
export function PrepProgress({
  steps,
  lang,
}: {
  steps: PortalStep[];
  lang: PortalLang;
}) {
  const t = PORTAL_TEXT[lang];
  const { done, total } = readiness(steps);
  if (total === 0)
    return <p className="text-muted-foreground">{t.checklistEmpty}</p>;
  return (
    <div className="flex flex-col gap-2 rounded-[20px] border bg-card p-4 shadow-card">
      <p className="font-medium">{t.checklistProgress(done, total)}</p>
      <ProgressBar
        value={(done / total) * 100}
        label={t.checklistTitle}
        tone={readinessTone(steps)}
      />
    </div>
  );
}

export function PrepTimeline({
  steps,
  timeZone,
  lang,
  now,
}: {
  steps: PortalStep[];
  timeZone: string;
  lang: PortalLang;
  now: number;
}) {
  const t = PORTAL_TEXT[lang];
  const untranslated =
    lang !== "en" && steps.some((step) => step.language === "en");

  return (
    <div className="flex flex-col gap-3">
      {untranslated ? (
        <p className="rounded-2xl bg-muted p-4 text-[15px]">
          {t.notTranslated}
        </p>
      ) : null}
      <ol className="flex flex-col gap-3">
        {steps.map((step) => (
          <li
            key={step.event_id}
            id={`step-${step.event_id}`}
            className={`scroll-mt-24 rounded-[20px] border bg-card p-5 shadow-card ${
              step.state === "DUE" || step.state === "OVERDUE"
                ? "ring-2 ring-primary/40"
                : ""
            }`}
          >
            <div className="flex flex-wrap items-center gap-2">
              <StateBadge state={step.state} lang={lang} />
              {step.is_critical ? <ImportantPill lang={lang} /> : null}
            </div>
            <p className="mt-3 text-[15px] text-muted-foreground">
              <time dateTime={step.due_at}>
                {formatDateTime(step.due_at, timeZone, lang)}
              </time>{" "}
              · {formatRelative(step.due_at, now, lang)}
            </p>
            <h3
              className="mt-1 text-[20px] leading-[26px] font-semibold"
              lang={step.language}
            >
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
              lang={lang}
            />
          </li>
        ))}
      </ol>
    </div>
  );
}
