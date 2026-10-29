import type { Metadata } from "next";
import { Suspense } from "react";

import {
  canHandleEscalations,
  getCurrentUser,
  listEscalations,
} from "@/lib/server/dal";

import { InboxList } from "./inbox-list";
import { SkeletonList } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Inbox" };

async function Inbox() {
  const user = await getCurrentUser();
  if (!canHandleEscalations(user.role)) {
    return (
      <p className="text-sm text-muted-foreground">
        Your role cannot see the nurse inbox.
      </p>
    );
  }
  const items = await listEscalations("open");
  return <InboxList items={items} />;
}

export default function InboxPage() {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-4 py-6 sm:px-8 sm:py-8">
      <div>
        <h1 className="text-[28px] leading-tight font-semibold tracking-tight">
          Nurse inbox
        </h1>
        <p className="text-sm text-muted-foreground">
          Questions and problems that need a person, most urgent first.
        </p>
      </div>
      <Suspense fallback={<SkeletonList label="Loading" rows={3} />}>
        <Inbox />
      </Suspense>
    </main>
  );
}
