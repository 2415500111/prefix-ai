import type { Metadata } from "next";
import { Suspense } from "react";

import { SegmentedControl } from "@/components/ui/segmented-control";
import { SkeletonCards, SkeletonList } from "@/components/ui/skeleton";
import {
  getBadges,
  getCurrentUser,
  getPatientDrawer,
  listUpcoming,
} from "@/lib/server/dal";

import { PatientSheet } from "./coordinator/patient-sheet";
import { readSheetTab } from "./coordinator/sheet-tabs";
import { SummaryCards, summarize } from "./coordinator/summary-cards";
import {
  type Filter,
  FILTERS,
  filterRows,
  UpcomingTable,
} from "./coordinator/upcoming-table";
import { DemoControls } from "./demo/demo-controls";

export const metadata: Metadata = {
  title: "Overview",
};

function readFilter(value: string | string[] | undefined): Filter {
  return value === "attention" || value === "high" ? value : "all";
}

async function Board({
  searchParams,
}: {
  searchParams: PageProps<"/dashboard">["searchParams"];
}) {
  const params = await searchParams;
  const filter = readFilter(params.filter);
  const appointment =
    typeof params.appointment === "string" ? params.appointment : undefined;
  const tab = readSheetTab(params.tab);

  const [rows, drawer, user, badges] = await Promise.all([
    listUpcoming(72),
    appointment ? getPatientDrawer(appointment) : null,
    getCurrentUser(),
    getBadges(),
  ]);
  const counts: Record<Filter, number> = {
    all: rows.length,
    attention: filterRows(rows, "attention").length,
    high: filterRows(rows, "high").length,
  };

  return (
    <>
      <SummaryCards summary={summarize(rows, badges.open_escalations)} />
      <section aria-labelledby="next-heading" className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2
            id="next-heading"
            className="text-lg font-semibold tracking-tight"
          >
            Next 72 hours
          </h2>
          <SegmentedControl
            label="Filter procedures"
            value={filter}
            items={FILTERS.map((item) => ({
              value: item.value,
              label: item.label,
              count: counts[item.value],
              href: `/dashboard?filter=${item.value}`,
            }))}
          />
        </div>
        <UpcomingTable
          rows={filterRows(rows, filter)}
          filter={filter}
          selectedId={appointment}
        />
      </section>
      {drawer ? (
        <PatientSheet
          // A link to another tab of the same patient opens the sheet afresh on that tab.
          key={`${drawer.appointment.appointment_id}:${tab}`}
          drawer={drawer}
          filter={filter}
          role={user.role}
          tab={tab}
        />
      ) : null}
    </>
  );
}

async function Demo() {
  const user = await getCurrentUser();
  if (user.role !== "DEMO_VIEWER" && user.role !== "ADMIN") return null;
  // Resetting the demo lives in the sidebar's Admin group now.
  return <DemoControls isAdmin={false} />;
}

export default function DashboardPage({
  searchParams,
}: PageProps<"/dashboard">) {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-4 py-6 sm:px-8 sm:py-8">
      <header className="flex flex-col gap-1">
        <h1 className="text-[28px] leading-tight font-semibold tracking-tight">
          Overview
        </h1>
        <p className="text-muted-foreground">
          Procedures in the next 72 hours, least ready first.
        </p>
      </header>
      <Suspense
        fallback={
          <>
            <SkeletonCards />
            <SkeletonList label="Loading procedures" />
          </>
        }
      >
        <Board searchParams={searchParams} />
      </Suspense>
      <Suspense fallback={null}>
        <Demo />
      </Suspense>
    </main>
  );
}
