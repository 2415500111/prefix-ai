import type { Metadata } from "next";
import { Suspense } from "react";

import { getNotifications, getPortalLanguage } from "@/lib/server/portal";

import { PortalSkeleton } from "../../_portal/portal-skeleton";
import { UpdatesList } from "./updates-list";

export const metadata: Metadata = { title: "Updates" };

export default function UpdatesPage({ searchParams }: PageProps<"/p/updates">) {
  return (
    <Suspense fallback={<PortalSkeleton />}>
      <Updates searchParams={searchParams} />
    </Suspense>
  );
}

async function Updates({
  searchParams,
}: {
  searchParams: PageProps<"/p/updates">["searchParams"];
}) {
  const lang = await getPortalLanguage();
  const [feed, params] = await Promise.all([
    getNotifications(lang),
    searchParams,
  ]);
  const open = typeof params.open === "string" ? params.open : null;

  return (
    <main lang={lang} className="flex flex-col gap-4">
      <UpdatesList
        key={open ?? "all"}
        items={feed.items}
        lang={lang}
        now={feed.fetchedAt}
        openKey={open}
      />
    </main>
  );
}
