import { Siren } from "lucide-react";
import type { Metadata } from "next";
import { Suspense } from "react";

import { FilterChipLink } from "@/components/ui/filter-chip";
import { SkeletonList } from "@/components/ui/skeleton";
import {
  canHandleEscalations,
  getCurrentUser,
  listEscalations,
} from "@/lib/server/dal";

import { InboxList } from "./inbox-list";

export const metadata: Metadata = { title: "Inbox" };

type SearchParams = PageProps<"/dashboard/inbox">["searchParams"];

async function Inbox({ searchParams }: { searchParams: SearchParams }) {
  const [user, params] = await Promise.all([getCurrentUser(), searchParams]);
  if (!canHandleEscalations(user.role)) {
    return (
      <p className="text-sm text-muted-foreground">
        Your role cannot see the nurse inbox.
      </p>
    );
  }
  const urgentOnly = params.urgent === "1";
  const items = await listEscalations("open");
  const urgent = items.filter((item) => item.urgent);
  return (
    <>
      <div className="flex items-center gap-2">
        <FilterChipLink
          active={urgentOnly}
          href={urgentOnly ? "/dashboard/inbox" : "/dashboard/inbox?urgent=1"}
        >
          <Siren className="size-3.5" aria-hidden />
          Urgent only
          <span className="text-xs tabular-nums">{urgent.length}</span>
        </FilterChipLink>
      </div>
      <InboxList items={urgentOnly ? urgent : items} urgentOnly={urgentOnly} />
    </>
  );
}

export default function InboxPage({
  searchParams,
}: PageProps<"/dashboard/inbox">) {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-4 py-6 sm:px-8 sm:py-8">
      <div>
        <h1 className="text-[28px] leading-tight font-semibold tracking-tight">
          Nurse inbox
        </h1>
        <p className="text-sm text-muted-foreground">
          Questions and problems that need a person, newest first.
        </p>
      </div>
      <Suspense fallback={<SkeletonList label="Loading" rows={3} />}>
        <Inbox searchParams={searchParams} />
      </Suspense>
    </main>
  );
}
