import type { AnalyticsSummary } from "@prefix/shared";

const MONEY = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

export function percent(value: number | null): string {
  return value === null ? "No procedures to compare" : `${value}%`;
}

export function money(value: string | null): string {
  return value === null ? "Needs a baseline" : MONEY.format(Number(value));
}

function Metric({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note?: string;
}) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border p-4">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-2xl font-semibold tabular-nums">{value}</dd>
      {note ? <p className="text-xs text-muted-foreground">{note}</p> : null}
    </div>
  );
}

export function AnalyticsView({ summary }: { summary: AnalyticsSummary }) {
  const hasBaseline = summary.baseline_rate !== null;
  return (
    <section
      aria-labelledby="analytics-results"
      className="flex flex-col gap-6"
    >
      <h2 id="analytics-results" className="sr-only">
        Results from {summary.start} to {summary.end}
      </h2>

      <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Metric
          label="Cancellation rate"
          value={percent(summary.cancellation_rate)}
          note={`${summary.cancelled} of ${summary.procedures} procedures cancelled`}
        />
        <Metric
          label="Prep-related cancellations"
          value={String(summary.prep_cancelled)}
          note={
            summary.prep_share === null
              ? "Bowel prep, food and drink, medicines, escort, labs, paperwork"
              : `${summary.prep_share}% of all cancellations`
          }
        />
        <Metric
          label="Check-in response rate"
          value={percent(summary.response_rate)}
          note={`${summary.checkins_answered} of ${summary.checkins_sent} sent check-ins answered`}
        />
        <Metric
          label="Theatre time at risk"
          value={`${summary.or_minutes_at_risk} min`}
          note="Lost to prep-related cancellations"
        />
        <Metric
          label="OR cost at risk"
          value={money(summary.or_cost_at_risk)}
          note="Operating room cost of the same time"
        />
        <Metric
          label="Slots backfilled"
          value="Not tracked yet"
          note="Counted once the waitlist is in use"
        />
      </dl>

      <div className="flex flex-col gap-2 rounded-lg border p-4">
        <h3 className="font-semibold">Estimated savings</h3>
        {hasBaseline ? (
          <p className="text-sm">
            Against a baseline of {summary.baseline_rate}%,{" "}
            <strong>{summary.avoided_estimate ?? 0}</strong> cancellations were
            avoided, about{" "}
            <strong>{summary.or_minutes_saved_estimate ?? 0} minutes</strong> of
            theatre time and{" "}
            <strong>{money(summary.or_cost_saved_estimate)}</strong> of OR cost.
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">
            Enter your cancellation rate from before Prefix AI to estimate what
            was avoided. Without a baseline, nothing is claimed as saved.
          </p>
        )}
      </div>

      <div className="flex flex-col gap-1 text-xs text-muted-foreground">
        <p>
          A procedure counts in the range when it is scheduled inside it (UTC
          dates). OR cost at risk is exposure to the time that prep-related
          cancellations lost. It is not a saving.
        </p>
      </div>
    </section>
  );
}
