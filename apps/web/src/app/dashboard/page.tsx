import type { Metadata } from "next";
import { Suspense } from "react";

import {
  getCurrentUser,
  getPatientDrawer,
  listUpcoming,
} from "@/lib/server/dal";

import { PatientDrawer } from "./coordinator/patient-drawer";
import {
  type Filter,
  filterRows,
  UpcomingTable,
} from "./coordinator/upcoming-table";
import { DemoControls } from "./demo/demo-controls";

export const metadata: Metadata = {
  title: "Dashboard",
};

const NOTICES: Record<string, string> = {
  failed: "That did not work. Please try again.",
};

async function Board({
  searchParams,
}: {
  searchParams: PageProps<"/dashboard">["searchParams"];
}) {
  const params = await searchParams;
  const filter: Filter = params.filter === "attention" ? "attention" : "all";
  const appointment =
    typeof params.appointment === "string" ? params.appointment : undefined;
  const notice =
    typeof params.notice === "string" ? NOTICES[params.notice] : undefined;

  const [rows, drawer] = await Promise.all([
    listUpcoming(72),
    appointment ? getPatientDrawer(appointment) : null,
  ]);

  return (
    <>
      {notice ? (
        <p role="alert" className="text-sm text-destructive">
          {notice}
        </p>
      ) : null}
      <div className={`grid gap-6 ${drawer ? "lg:grid-cols-[1fr_26rem]" : ""}`}>
        <UpcomingTable
          rows={filterRows(rows, filter)}
          filter={filter}
          selectedId={appointment}
        />
        {drawer ? <PatientDrawer drawer={drawer} filter={filter} /> : null}
      </div>
    </>
  );
}

async function Demo() {
  const user = await getCurrentUser();
  return <DemoControls isAdmin={user.role === "ADMIN"} />;
}

export default function DashboardPage({
  searchParams,
}: PageProps<"/dashboard">) {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-4 py-10 sm:px-6">
      <h1 className="text-2xl font-semibold tracking-tight">
        Coordinator dashboard
      </h1>
      <Suspense
        fallback={
          <p className="text-sm text-muted-foreground">Loading procedures…</p>
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
