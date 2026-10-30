import type { Metadata } from "next";
import { Suspense } from "react";

import {
  canManageWaitlist,
  getCurrentUser,
  listReleasedSlots,
  listWaitlist,
} from "@/lib/server/dal";

import { AddForm } from "./add-form";
import { ReleasedSlotCard } from "./released-slot";
import { WaitlistTable } from "./waitlist-table";
import { SkeletonList } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Waitlist" };

const NOTICES: Record<string, string> = {
  failed: "That did not work. Check the details and try again.",
  added: "Patient added to the waitlist.",
};

function notice(value: string | string[] | undefined): string | undefined {
  return typeof value === "string" ? NOTICES[value] : undefined;
}

async function Board({
  searchParams,
}: {
  searchParams: PageProps<"/dashboard/waitlist">["searchParams"];
}) {
  const params = await searchParams;
  const message = notice(params.notice);
  const user = await getCurrentUser();
  const canManage = canManageWaitlist(user.role);
  const [slots, entries] = await Promise.all([
    listReleasedSlots(),
    listWaitlist(),
  ]);

  return (
    <>
      {message ? (
        <p
          role="status"
          className={`rounded-md px-3 py-2 text-sm ${
            params.notice === "failed"
              ? "bg-destructive/10 text-destructive"
              : "bg-muted"
          }`}
        >
          {message}
        </p>
      ) : null}

      <section aria-labelledby="slots-heading" className="grid gap-3">
        <h2 id="slots-heading" className="text-lg font-semibold">
          Released slots
        </h2>
        {slots.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No released slots in the next week. A cancellation shows up here.
          </p>
        ) : (
          <ul className="grid gap-4">
            {slots.map((slot) => (
              <li key={slot.appointment_id}>
                <ReleasedSlotCard slot={slot} canManage={canManage} />
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="waiting-heading" className="grid gap-3">
        <h2 id="waiting-heading" className="text-lg font-semibold">
          Waiting list
        </h2>
        <WaitlistTable entries={entries} canManage={canManage} />
      </section>

      {canManage ? (
        <section aria-labelledby="add-heading" className="grid gap-3">
          <h2 id="add-heading" className="text-lg font-semibold">
            Add a patient
          </h2>
          <Suspense
            fallback={<SkeletonList label="Loading patients" rows={3} />}
          >
            <AddForm />
          </Suspense>
        </section>
      ) : null}
    </>
  );
}

export default function WaitlistPage(props: PageProps<"/dashboard/waitlist">) {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-8 px-4 py-6 sm:px-8 sm:py-8">
      <div>
        <h1 className="text-[28px] leading-tight font-semibold tracking-tight">
          Waitlist
        </h1>
        <p className="text-sm text-muted-foreground">
          A cancelled slot is offered to one patient at a time, the best fit
          first. Each offer waits for a reply before the next patient is
          considered.
        </p>
      </div>
      <Suspense
        fallback={<SkeletonList label="Loading the waitlist" rows={3} />}
      >
        <Board searchParams={props.searchParams} />
      </Suspense>
    </main>
  );
}
