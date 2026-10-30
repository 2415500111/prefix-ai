import type { Metadata } from "next";
import { connection } from "next/server";
import { Suspense } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/server/api";
import {
  canExportAnalytics,
  getAnalyticsSummary,
  getCurrentUser,
} from "@/lib/server/dal";

import { AnalyticsView } from "./analytics-view";
import { lastThirtyDays } from "./range";
import { PrintButton } from "./print-button";
import { SkeletonList } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Analytics" };

function text(value: string | string[] | undefined): string | undefined {
  return typeof value === "string" && value !== "" ? value : undefined;
}

async function Results({
  searchParams,
}: {
  searchParams: PageProps<"/dashboard/analytics">["searchParams"];
}) {
  const params = await searchParams;
  // The default range depends on today, so the page must render per request, not at build time.
  await connection();
  const defaults = lastThirtyDays();
  const end = text(params.end) ?? defaults.end;
  const start = text(params.start) ?? defaults.start;
  const baselineText = text(params.baseline);
  const baseline =
    baselineText === undefined ? undefined : Number(baselineText);
  const usableBaseline =
    baseline !== undefined &&
    Number.isFinite(baseline) &&
    baseline >= 0 &&
    baseline <= 100
      ? baseline
      : undefined;

  const user = await getCurrentUser();
  let summary;
  try {
    summary = await getAnalyticsSummary(start, end, usableBaseline);
  } catch (error) {
    if (error instanceof ApiError && error.status === 422) {
      return (
        <p role="alert" className="text-sm text-destructive">
          Choose an end date after the start date, within one year.
        </p>
      );
    }
    throw error;
  }

  const exportHref = `/dashboard/analytics/export?start=${start}&end=${end}`;
  return (
    <>
      <div className="flex flex-wrap items-center gap-3 print:hidden">
        <PrintButton />
        {canExportAnalytics(user.role) ? (
          <a
            href={exportHref}
            className={buttonVariants({ variant: "outline" })}
          >
            Download CSV
          </a>
        ) : null}
      </div>
      <AnalyticsView summary={summary} />
    </>
  );
}

export default function AnalyticsPage({
  searchParams,
}: PageProps<"/dashboard/analytics">) {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-4 py-6 sm:px-8 sm:py-8 print:max-w-none print:py-4">
      <div>
        <h1 className="text-[28px] leading-tight font-semibold tracking-tight">
          Analytics
        </h1>
        <p className="text-sm text-muted-foreground">
          How often procedures were cancelled, why, and what it cost in theatre
          time.
        </p>
      </div>

      <form
        method="get"
        className="flex flex-wrap items-end gap-3 print:hidden"
      >
        <div className="flex flex-col gap-1">
          <Label htmlFor="start">From</Label>
          <Input id="start" name="start" type="date" required />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="end">To</Label>
          <Input id="end" name="end" type="date" required />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="baseline">
            Cancellation rate before Prefix AI (%)
          </Label>
          <Input
            id="baseline"
            name="baseline"
            type="number"
            min={0}
            max={100}
            step={0.1}
            placeholder="Optional"
          />
        </div>
        <Button type="submit" variant="secondary">
          Show
        </Button>
      </form>

      <Suspense fallback={<SkeletonList label="Loading" rows={3} />}>
        <Results searchParams={searchParams} />
      </Suspense>
    </main>
  );
}
